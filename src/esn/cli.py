from __future__ import annotations

import argparse
from pathlib import Path

from .model import ValidationError, canonical_json, load_json, load_registry, validate_score
from .render import render_svg


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="esn", description="Emoji Sound Notation tools")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "canonicalize", "render"):
        cmd = sub.add_parser(name)
        cmd.add_argument("score")
        cmd.add_argument("--registry", required=True)
        if name in {"canonicalize", "render"}:
            cmd.add_argument("-o", "--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        registry = load_registry(args.registry)
        score = load_json(args.score)
        validate_score(score, registry)
        if args.command == "validate":
            print(f"valid esn/1: {len(score['events'])} events")
        elif args.command == "canonicalize":
            Path(args.output).write_text(canonical_json(score), encoding="utf-8", newline="\n")
        else:
            Path(args.output).write_text(render_svg(score, registry), encoding="utf-8", newline="\n")
        return 0
    except (OSError, ValueError, ValidationError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
