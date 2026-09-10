from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from esn.model import ValidationError, load_json, load_registry, validate_score
from esn.render import render_svg
from esn.visual import color_cue_for_midi, glyph_svg, load_visual_profile, render_glyph_sheet

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "registries" / "core.json"
VISUAL_PATH = ROOT / "visual" / "core.json"
SCORE_PATH = ROOT / "examples" / "first-score.esn.json"


class VisualBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = load_registry(REGISTRY_PATH)
        self.visual = load_visual_profile(VISUAL_PATH, self.registry)
        self.score = load_json(SCORE_PATH)
        validate_score(self.score, self.registry)

    def test_core_profile_covers_every_source(self) -> None:
        self.assertEqual(set(self.visual["glyphs"]), set(self.registry))
        self.assertEqual(len(self.visual["palettes"]["pitch_class"]), 12)
        self.assertEqual(len(self.visual["palettes"]["scale_degree"]), 7)

    def test_pitch_class_color_is_absolute(self) -> None:
        c4, cue_c = color_cue_for_midi(self.visual, 60, "pitch_class")
        c5, cue_c5 = color_cue_for_midi(self.visual, 72, "pitch_class")
        self.assertEqual(c4, c5)
        self.assertEqual(cue_c, "pitch class C")
        self.assertEqual(cue_c5, "pitch class C")

    def test_scale_degree_color_transposes_with_tonic(self) -> None:
        c_color, c_cue = color_cue_for_midi(self.visual, 60, "scale_degree")
        shifted = dict(self.visual)
        shifted["scale"] = {"tonic": "D", "intervals": list(self.visual["scale"]["intervals"])}
        d_color, d_cue = color_cue_for_midi(shifted, 62, "scale_degree")
        self.assertEqual(c_color, d_color)
        self.assertEqual(c_cue, "scale degree 1")
        self.assertEqual(d_cue, "scale degree 1")

    def test_scale_degree_chromatic_fallback_is_explicit(self) -> None:
        color, cue = color_cue_for_midi(self.visual, 61, "scale_degree")
        self.assertEqual(color, self.visual["palettes"]["chromatic"])
        self.assertEqual(cue, "chromatic outside configured scale")

    def test_glyph_svg_is_tintable_and_vendor_independent(self) -> None:
        first = glyph_svg(self.visual, "animal:cat", 10, 20, 32, "#123456")
        second = glyph_svg(self.visual, "animal:cat", 10, 20, 32, "#abcdef")
        self.assertIn('#123456', first)
        self.assertIn('#abcdef', second)
        self.assertNotEqual(first, second)
        self.assertNotIn("🐈", first)
        self.assertIn("<path", first)

    def test_glyph_sheet_is_deterministic(self) -> None:
        first = render_glyph_sheet(self.visual, self.registry)
        second = render_glyph_sheet(self.visual, self.registry)
        self.assertEqual(first, second)
        self.assertIn("Absolute pitch-class palette", first)
        self.assertIn("Relative scale-degree palette", first)
        for source_id in self.registry:
            self.assertIn(source_id, first)

    def test_visual_renderer_has_no_platform_emoji_dependency(self) -> None:
        rendered = render_svg(self.score, self.registry, visual=self.visual, color_mode="scale_degree")
        self.assertIn("color=relative scale degree", rendered)
        self.assertIn("scale degree", rendered)
        self.assertNotIn("Segoe UI Emoji", rendered)
        for source in self.registry.values():
            self.assertNotIn(source["glyph"], rendered)

    def test_half_semitone_rounding_matches_browser(self) -> None:
        color, cue = color_cue_for_midi(self.visual, 60.5, "pitch_class")
        self.assertEqual(color, self.visual["palettes"]["pitch_class"][1])
        self.assertEqual(cue, "pitch class C#")

    def test_profile_rejects_missing_source_binding(self) -> None:
        raw = json.loads(VISUAL_PATH.read_text(encoding="utf-8"))
        raw["glyphs"] = raw["glyphs"][:-1]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "visual.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "missing glyph bindings"):
                load_visual_profile(path, self.registry)

    def test_visual_validate_cli_accepts_named_visual_flag(self) -> None:
        import subprocess, sys
        result = subprocess.run(
            [sys.executable, "-m", "esn", "visual-validate", "--visual", str(VISUAL_PATH), "--registry", str(REGISTRY_PATH)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("valid esn-visual/1", result.stdout)

    def test_profile_rejects_unsafe_svg_path(self) -> None:
        raw = json.loads(VISUAL_PATH.read_text(encoding="utf-8"))
        raw["glyphs"][0]["path"] = 'M0 0"/><script>alert(1)</script>'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "visual.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "invalid SVG path syntax"):
                load_visual_profile(path, self.registry)


if __name__ == "__main__":
    unittest.main()
