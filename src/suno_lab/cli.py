import argparse
import json
from pathlib import Path
from .analysis import analyze
from .annotations import annotate
from .report import write_report


def main():
    parser = argparse.ArgumentParser(description="ADAD · TMiPvLE + RI local analysis")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("compare", help="Compare two or more audio files")
    p.add_argument("files", nargs="+", type=Path)
    p.add_argument("--out", type=Path, default=Path("reports"))
    p.add_argument("--window", type=float, default=5.0)
    p.add_argument("--event-radius", type=float, default=30.0)
    p.add_argument("--annotations", type=Path, help="Optional JSON annotation file")
    p = sub.add_parser("annotate", help="Listen locally and enter human phase annotations")
    p.add_argument("file", type=Path)
    p.add_argument("--annotations", type=Path, required=True)
    p.add_argument("--play", action="store_true", help="Play original WAV asynchronously on Windows")
    args = parser.parse_args()
    try:
        if args.command == "annotate":
            annotate(args.file, args.annotations, args.play)
        elif args.command == "compare":
            if len(args.files) < 2:
                raise ValueError("compare requires at least two files")
            if len({f.name for f in args.files}) != len(args.files):
                raise ValueError("Track basenames must be unique for annotation matching")
            annotations = json.loads(args.annotations.read_text(encoding="utf-8")) if args.annotations else {}
            data = [analyze(f, args.window, annotations=annotations.get("tracks", {}).get(f.name, {}),
                            event_radius=args.event_radius) for f in args.files]
            write_report(data, annotations, args.out)
            print(f"Saved {args.out / 'report.md'}, analysis.json, rms_comparison.png, spectral_comparison.png")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
