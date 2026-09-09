from __future__ import annotations

import argparse
from pathlib import Path

from .model import ValidationError, canonical_json, load_json, load_registry, validate_score
from .playback import load_playback_registry, write_wav
from .render import render_svg
from .visual import COLOR_MODES, load_visual_profile, render_glyph_sheet


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="esn", description="Emoji Sound Notation tools")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("validate", "canonicalize", "render", "audio"):
        cmd = sub.add_parser(name)
        cmd.add_argument("score")
        cmd.add_argument("--registry", required=True)
        if name in {"canonicalize", "render", "audio"}:
            cmd.add_argument("-o", "--output", required=True)
        if name == "audio":
            cmd.add_argument("--playback", required=True)
        if name == "render":
            cmd.add_argument("--visual")
            cmd.add_argument("--color-mode", choices=sorted(COLOR_MODES))

    visual_validate = sub.add_parser("visual-validate")
    visual_validate.add_argument("visual_path", nargs="?")
    visual_validate.add_argument("--visual")
    visual_validate.add_argument("--registry", required=True)

    glyph_sheet = sub.add_parser("glyph-sheet")
    glyph_sheet.add_argument("--visual", required=True)
    glyph_sheet.add_argument("--registry", required=True)
    glyph_sheet.add_argument("-o", "--output", required=True)
    return parser

def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        registry = load_registry(args.registry)
        if args.command == "visual-validate":
            visual_path = args.visual or args.visual_path
            if not visual_path:
                raise ValidationError("visual-validate requires --visual VISUAL (or legacy positional VISUAL)")
            visual = load_visual_profile(visual_path, registry)
            print(f"valid esn-visual/1: {len(visual['glyphs'])} glyphs")
            return 0
        if args.command == "glyph-sheet":
            visual = load_visual_profile(args.visual, registry)
            Path(args.output).write_text(render_glyph_sheet(visual, registry), encoding="utf-8", newline="\n")
            return 0

        score = load_json(args.score)
        validate_score(score, registry)
        if args.command == "validate":
            print(f"valid esn/1: {len(score['events'])} events")
        elif args.command == "canonicalize":
            Path(args.output).write_text(canonical_json(score), encoding="utf-8", newline="\n")
        elif args.command == "render":
            visual = load_visual_profile(args.visual, registry) if args.visual else None
            if args.color_mode and visual is None:
                raise ValidationError("--color-mode requires --visual")
            Path(args.output).write_text(
                render_svg(score, registry, visual=visual, color_mode=args.color_mode),
                encoding="utf-8",
                newline="\n",
            )
        else:
            playback = load_playback_registry(args.playback, registry)
            write_wav(args.output, score, registry, playback)
        return 0
    except (OSError, ValueError, ValidationError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
