"""Generate English visual steps from user-supplied reference videos.

Only video-derived RGB images and their camera/timestamp labels reach the model.
This command creates text and a visual-input audit; existing provenance, when
provided, is updated after success. No dataset or trajectory is required.
Existing annotations and failed attempts are never overwritten or retried.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys

from demonstrations.prepare_reference_text import ANNOTATION_BENCHMARKS, CODEX_TIMEOUT, annotation_settings, generate
from demonstrations.media import positive_fps, scan_videos
from demonstrations.common import sha256_file
from execution.artifacts import write_json

def _load_provenance(source: Path, output: Path) -> tuple[Path | None, dict | None]:
    source_meta = source / "provenance.json"
    target_meta = output / "provenance.json"
    if source_meta.is_file() and output != source:
        if target_meta.exists() or target_meta.is_symlink():
            raise FileExistsError(f"Preserve prior provenance evidence; use a fresh output directory: {output}")
        shutil.copy2(source_meta, target_meta)
    if target_meta.is_file():
        return target_meta, json.loads(target_meta.read_text())
    return None, None


def _record_text_failure(path: Path | None, error: str) -> None:
    if path is None:
        return
    data = json.loads(path.read_text())
    text = dict(data.get("text") or {})
    text.update(status="failed", error=error)
    data["text"] = text
    write_json(path, data)


def _publish_text_provenance(path: Path | None, output: Path, fps: float) -> None:
    if path is None:
        return
    data = json.loads(path.read_text())
    data["text"] = {
        "status": "complete",
        "file": "steps.txt",
        "language": "English",
        "sha256": sha256_file(output / "steps.txt"),
        "annotation_audit": "annotation/audit.json",
        "sampling_fps": fps,
        "source": "visual-only Codex annotation from user-supplied reference videos",
    }
    write_json(path, data)


def describe(folder, *, output=None, model=None, timeout=CODEX_TIMEOUT, benchmark='robodojo', fps=1.0):
    folder = Path(folder).expanduser().resolve()
    output = Path(output).expanduser().resolve() if output is not None else folder
    videos = scan_videos(folder, benchmark=benchmark)
    annotation_settings(benchmark, videos)
    if output != folder and output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Preserve prior annotations; use a fresh output directory: {output}")
    output.mkdir(parents=True, exist_ok=True)

    markers = (
        "steps.txt",
        "steps.json",
        "annotation_audit.json",
        "annotation_response.txt",
        "annotation",
    )
    if any((output / name).exists() or (output / name).is_symlink() for name in markers):
        raise FileExistsError(f"Preserve prior annotations; use a fresh output directory: {output}")
    provenance, metadata = _load_provenance(folder, output)
    if provenance is not None:
        previous = metadata.get("text") or {}
        if previous.get("status") in {"complete", "failed"} or previous.get("sha256"):
            raise FileExistsError(f"Preserve prior text status/evidence; use a fresh output directory: {output}")

    try:
        path = generate(
            folder,
            output / "steps.txt",
            model=model,
            timeout=timeout,
            audit_directory=output / "annotation",
            benchmark=benchmark,
            fps=fps,
        )
        _publish_text_provenance(provenance, output, fps)
    except Exception as exc:
        # Do not silently leave a retryable-looking pending record.  The
        # directory remains intact and a later invocation must choose a fresh
        # output directory, preserving the failed attempt for diagnosis.
        _record_text_failure(provenance, f"{type(exc).__name__}: {exc}")
        raise
    print(f"{folder.name}: saved English numbered steps to {path}", flush=True)
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--benchmark", choices=ANNOTATION_BENCHMARKS, default='robodojo')
    parser.add_argument("folders", type=Path, nargs="+")
    parser.add_argument("--output-root", type=Path, help="save each source under a fresh <root>/<folder.name>")
    parser.add_argument("--codex-model")
    parser.add_argument("--reference-fps", type=positive_fps, default=1.0,
                        help="independent video sampling rate (default: 1 FPS); retains first/last frames")
    parser.add_argument("--timeout", type=float, default=CODEX_TIMEOUT)
    args = parser.parse_args(argv)
    if len({folder.name for folder in args.folders}) != len(args.folders):
        parser.error("folder names must be unique within one batch")
    try:
        for folder in args.folders:
            output = args.output_root / folder.name if args.output_root is not None else None
            describe(folder, output=output, model=args.codex_model, timeout=args.timeout,
                     benchmark=args.benchmark, fps=args.reference_fps)
    except Exception as exc:
        print(f"Visual step generation failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
