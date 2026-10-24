#!/usr/bin/env python3
"""Generate English visual steps with a fresh read-only Codex CLI session.

Adapted from scripts/prepare_reference_text.py in
codex_control_docs_and_core_20260925.zip (see NOTICE).
Operator-only: importing/testing this module never invokes a model.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
from importlib.resources import files
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from demonstrations.media import image_labels, positive_fps, prepare_images, scan_videos
from demonstrations.common import finite_number, read_text
from environments import environment_package

CODEX_TIMEOUT = 600.0
ANNOTATION_BENCHMARKS = ('robodojo', 'libero-plus', 'libero-geomotion', 'univtac', 'robocasa-gr1', 'robotwin')
AUDIT_FORMAT = "robodojo-visual-steps-v2"


def annotation_settings(benchmark, cameras):
    """Environment-owned annotation constraints, shared by both entrypoints."""
    if benchmark not in ANNOTATION_BENCHMARKS:
        raise ValueError(f"Unsupported annotation benchmark: {benchmark}")
    settings = importlib.import_module(environment_package(benchmark) + '.reference')
    expected = set(settings.ANNOTATION_CAMERAS)
    if set(cameras) != expected:
        raise ValueError(
            f"Expected one {benchmark} demonstration with cameras {sorted(expected)}; "
            "do not mix source and replay"
        )
    return settings


def validate_result(path):
    raw, text = read_text(path)
    # Syntax + obvious CJK rejection only; NOT semantic review, proof of English,
    # successful task execution or human approval. Never translate/repair output.
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines or "```" in text or re.search(r"[\u3400-\u9fff\uf900-\ufaff]", text):
        raise ValueError("Codex result must be plain English numbered steps")
    numbers = []
    for line in lines:
        match = re.fullmatch(r"(\d+)\.\s+\S.*", line)
        if match is None:
            raise ValueError("Each nonempty line must be one numbered step; no headers, JSON or checklist")
        numbers.append(int(match[1]))
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError("Codex step numbers must be consecutive starting with 1")
    return raw


def codex_command(executable, workspace, result, images, model=None):
    command = [
        executable,
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--cd",
        str(workspace),
        "--sandbox",
        "read-only",
        "-c",
        'approval_policy="never"',
        "-c",
        "mcp_servers={}",
        "-c",
        'web_search="disabled"',
        "-c",
        "features.shell_tool=false",
        "-c",
        "features.apps=false",
        "-c",
        "features.multi_agent=false",
        "-c",
        "project_doc_max_bytes=0",
        "--color",
        "never",
        "--output-last-message",
        str(result),
    ]
    if model:
        command += ["--model", model]
    for image in images:
        command += ["--image", str(image)]
    # Terminate variadic --image arguments; prompt goes through stdin.
    return command + ["--", "-"]


def invoke(command, prompt, workspace, timeout):
    """Inherit the caller's network settings and invoke the model once."""
    with subprocess.Popen(
        command, cwd=workspace, stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", start_new_session=True,
    ) as process:
        try:
            process.communicate(prompt, timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.communicate()
            raise  # Timeout/interruption: unknown outcome, never retry.
        if process.returncode != 0:
            # CLI stderr may contain credentials or URLs; do not publish it.
            raise ValueError(f"Codex failed; no text published (exit {process.returncode})")


def generate(video, output, *, model=None, timeout=CODEX_TIMEOUT, audit_directory=None,
             benchmark='robodojo', fps=1.0):
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be finite and positive")
    if not finite_number(fps) or fps <= 0:
        raise ValueError("reference-fps must be a finite positive number")
    output = Path(output).expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"refusing to overwrite {output}")
    if not output.parent.is_dir():
        raise ValueError("output parent directory must already exist")
    audit_directory = Path(audit_directory).expanduser().absolute() if audit_directory is not None else None
    if audit_directory is not None:
        if (
            audit_directory == output
            or audit_directory.is_relative_to(output)
            or output.is_relative_to(audit_directory)
        ):
            raise ValueError("audit directory and output must be separate paths")
        if audit_directory.exists() or audit_directory.is_symlink():
            raise FileExistsError(f"refusing to overwrite {audit_directory}")
        if not audit_directory.parent.is_dir():
            raise ValueError("audit parent directory must already exist")
    settings = annotation_settings(benchmark, scan_videos(video, benchmark=benchmark))
    executable = shutil.which("codex")
    if executable is None:
        raise ValueError("codex CLI not found on PATH")
    with tempfile.TemporaryDirectory(prefix=".reference-text-", dir=output.parent) as tmp:
        workspace = Path(tmp)
        frames = workspace / "frames"
        manifest = prepare_images(video, frames, mode="sequence", fps=fps, benchmark=benchmark)
        image_limit = getattr(settings, 'ANNOTATION_IMAGE_LIMIT', None)
        if image_limit is not None and manifest["image_count"] > image_limit:
            raise ValueError(
                f"{benchmark} reference exceeds the {image_limit}-image annotation budget "
                f"({manifest['image_count']} images); use a lower --reference-fps"
            )
        images, labels, inputs = [], [], []
        for index, (image, label) in enumerate(image_labels(manifest), 1):
            images.append(frames / image["file"])
            labels.append(dict(attachment=index, **label))
            inputs.append(dict(file="frames/" + image["file"], sha256=image["sha256"], **labels[-1]))
        specific = files(environment_package(benchmark)).joinpath('prompts/annotation.md')
        prompt = specific.read_text(encoding="utf-8")
        prompt += f"\n\nReference sampling rate: {fps} FPS."
        prompt += "\n\nImage attachment index (in order):\n" + json.dumps(labels, ensure_ascii=False)
        result = workspace / "result.txt"
        start = time.monotonic()
        invoke(codex_command(executable, workspace, result, images, model), prompt, workspace, timeout)
        if result.is_symlink() or not result.is_file():
            raise ValueError("Codex did not produce a regular result file")
        raw = validate_result(result)
        staged = workspace / "publish.txt"
        with staged.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # Output text is the final no-replace publication. Optional evidence is
        # local-only and contains the EXACT image attachments, prompt and response.
        audit_created = False
        try:
            if audit_directory is not None:
                audit_directory.mkdir(exist_ok=False)
                audit_created = True
                shutil.copytree(frames, audit_directory / "frames")
                (audit_directory / "response.txt").write_bytes(raw)
                (audit_directory / "prompt.txt").write_text(prompt, encoding="utf-8")
                audit = dict(
                    format=AUDIT_FORMAT if benchmark == 'robodojo' else 'sim-visual-steps-v1',
                    benchmark=benchmark,
                    model_override=model,
                    model_selection="explicit override" if model else "inherited local Codex CLI configuration",
                    inputs=inputs,
                    sampling=manifest,
                    prompt=prompt,
                    elapsed_s=time.monotonic() - start,
                    output_sha256=hashlib.sha256(raw).hexdigest(),
                    input_modalities=["video-derived images"],
                    used_task_source=False,
                    used_trajectory=False,
                    used_simulator_state=False,
                    used_rewards=False,
                    validation="numbered-line syntax and CJK rejection only; no semantic or human review",
                )
                (audit_directory / "audit.json").write_text(
                    json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            os.link(staged, output)  # Atomic no-replace, including publication races.
        except BaseException:
            if audit_created:
                shutil.rmtree(audit_directory)
            raise
    return output


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--benchmark", choices=ANNOTATION_BENCHMARKS, default='robodojo')
    parser.add_argument("--reference-video", required=True, type=Path,
                        help="video directory with videos.json or benchmark-specific filenames")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--codex-model")
    parser.add_argument("--reference-fps", type=positive_fps, default=1.0,
                        help="independent video sampling rate (default: 1 FPS); retains first/last frames")
    parser.add_argument("--timeout", type=float, default=CODEX_TIMEOUT)
    parser.add_argument("--audit-directory", type=Path)
    argv = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(argv)
    try:
        path = generate(
            args.reference_video,
            args.output,
            model=args.codex_model,
            timeout=args.timeout,
            audit_directory=args.audit_directory,
            benchmark=args.benchmark,
            fps=args.reference_fps,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"Reference text generation failed: {exc}", file=sys.stderr)
        return 2
    print(f"Saved UTF-8 reference steps: {path} (format checked; not semantically or human reviewed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
