"""Offline CLI for preparing RGB, trajectory and optional text references."""
import argparse
import json
from pathlib import Path
import sys

from environments.benchmarks import BENCHMARKS
from .cache import prepare
from .media import positive_fps


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--benchmark", choices=BENCHMARKS, required=True)
    parser.add_argument("--reference-video", type=Path)
    parser.add_argument("--reference-text", type=Path)
    parser.add_argument("--trajectory", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--reference-mode", choices=("endpoints", "sequence"), default=None)
    parser.add_argument("--reference-fps", type=positive_fps, default=None)
    argv = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(argv)
    if args.reference_video is None and (args.reference_mode is not None or args.reference_fps is not None):
        parser.error("reference sampling options require --reference-video")
    args.reference_mode = args.reference_mode or "sequence"
    if args.reference_fps is not None and args.reference_mode != "sequence":
        parser.error("--reference-fps is only valid with --reference-mode sequence")
    args.reference_fps = args.reference_fps if args.reference_fps is not None else 1.0
    try:
        manifest = prepare(
            args.reference_video,
            args.output, benchmark=args.benchmark,
            trajectory=args.trajectory,
            text=args.reference_text,
            mode=args.reference_mode,
            fps=args.reference_fps,
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.error(f"reference preparation failed: {exc}")
    print(json.dumps(manifest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
