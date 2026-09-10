from __future__ import annotations

import argparse
from pathlib import Path

from .interchange import (
    canonical_report, load_interchange_profile, write_cue_sheet, write_smf,
)
from .model import ValidationError, canonical_json, load_json, load_registry, validate_score
from .playback import load_playback_registry, write_wav
from .render import render_svg
from .soundpack import load_sound_pack
from .visual import COLOR_MODES, load_visual_profile, render_glyph_sheet


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="esn", description="Emoji Sound Notation tools")
    sub = parser.add_subparsers(dest="command", required=True)

    score_commands = ("validate", "canonicalize", "render", "audio", "midi-export", "cue-export")
    for name in score_commands:
        cmd = sub.add_parser(name)
        cmd.add_argument("score")
        cmd.add_argument("--registry", required=True)
        if name != "validate":
            cmd.add_argument("-o", "--output", required=True)
        if name == "audio":
            cmd.add_argument("--playback", required=True)
            cmd.add_argument("--sound-pack")
        if name == "render":
            cmd.add_argument("--visual")
            cmd.add_argument("--color-mode", choices=sorted(COLOR_MODES))
        if name in {"midi-export", "cue-export"}:
            cmd.add_argument("--interchange", required=True)
        if name == "midi-export":
            cmd.add_argument("--report")

    visual_validate = sub.add_parser("visual-validate")
    visual_validate.add_argument("visual_path", nargs="?")
    visual_validate.add_argument("--visual")
    visual_validate.add_argument("--registry", required=True)

    interchange_validate = sub.add_parser("interchange-validate")
    interchange_validate.add_argument("interchange_path", nargs="?")
    interchange_validate.add_argument("--interchange")
    interchange_validate.add_argument("--registry", required=True)

    sound_pack_validate = sub.add_parser("sound-pack-validate")
    sound_pack_validate.add_argument("sound_pack_path", nargs="?")
    sound_pack_validate.add_argument("--sound-pack")
    sound_pack_validate.add_argument("--registry", required=True)

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
        if args.command == "interchange-validate":
            interchange_path = args.interchange or args.interchange_path
            if not interchange_path:
                raise ValidationError("interchange-validate requires --interchange PROFILE")
            profile = load_interchange_profile(interchange_path, registry)
            print(f"valid esn-interchange/1: {len(profile['mappings'])} MIDI mappings")
            return 0
        if args.command == "sound-pack-validate":
            sound_pack_path = args.sound_pack or args.sound_pack_path
            if not sound_pack_path:
                raise ValidationError("sound-pack-validate requires --sound-pack PACK")
            sound_pack = load_sound_pack(sound_pack_path, registry)
            print(
                f"valid esn-sound-pack/1: {len(sound_pack['bindings'])} sample bindings, "
                f"{len(sound_pack['missing_assets'])} missing assets"
            )
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
                encoding="utf-8", newline="\n",
            )
        elif args.command == "audio":
            playback = load_playback_registry(args.playback, registry)
            sound_pack = load_sound_pack(args.sound_pack, registry) if args.sound_pack else None
            write_wav(args.output, score, registry, playback, sound_pack)
        elif args.command == "midi-export":
            interchange = load_interchange_profile(args.interchange, registry)
            report = write_smf(args.output, score, registry, interchange)
            if args.report:
                Path(args.report).write_text(canonical_report(report), encoding="utf-8", newline="\n")
            print(f"MIDI export: {report['midi_notes']} notes, {report['cue_only']} cue-only, {report['events_total']} semantic cues")
        else:
            interchange = load_interchange_profile(args.interchange, registry)
            write_cue_sheet(args.output, score, registry, interchange)
            print(f"cue sheet: {len(score['events'])} events")
        return 0
    except (OSError, ValueError, ValidationError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
