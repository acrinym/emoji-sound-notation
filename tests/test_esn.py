from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from esn.model import ValidationError, canonical_json, hz_to_midi, load_json, load_registry, note_to_midi, validate_score
from esn.render import render_svg


class EsnFoundationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(ROOT / "registries" / "core.json")
        cls.score = load_json(ROOT / "examples" / "first-score.esn.json")

    def test_reference_score_validates(self) -> None:
        validate_score(self.score, self.registry)

    def test_pitch_conversions(self) -> None:
        self.assertEqual(note_to_midi("C4"), 60)
        self.assertAlmostEqual(hz_to_midi(440.0), 69.0)

    def test_canonical_json_is_stable(self) -> None:
        first = canonical_json(self.score)
        second = canonical_json(load_json(ROOT / "examples" / "first-score.esn.json"))
        self.assertEqual(first, second)
    def test_renderer_is_deterministic_and_semantic(self) -> None:
        validate_score(self.score, self.registry)
        first = render_svg(self.score, self.registry)
        second = render_svg(copy.deepcopy(self.score), self.registry)
        self.assertEqual(first, second)
        self.assertIn("🐈", first)
        self.assertIn("animal:cat / meow", first)
        self.assertIn("UNPITCHED / SPECTRAL EVENTS", first)
        self.assertIn("C4", first)

    def test_forbidden_pitch_is_rejected(self) -> None:
        score = copy.deepcopy(self.score)
        rain = next(event for event in score["events"] if event["source"] == "nature:rain")
        rain["pitch"] = {"note": "C3"}
        with self.assertRaisesRegex(ValidationError, "pitch is forbidden"):
            validate_score(score, self.registry)

    def test_unknown_gesture_is_rejected(self) -> None:
        score = copy.deepcopy(self.score)
        score["events"][1]["gesture"] = "quack"
        with self.assertRaisesRegex(ValidationError, "not valid"):
            validate_score(score, self.registry)

    def test_non_monotonic_pitch_curve_is_rejected(self) -> None:
        score = copy.deepcopy(self.score)
        score["events"][1]["pitch_curve"][1]["at"] = 0.4
        with self.assertRaisesRegex(ValidationError, "strictly increase"):
            validate_score(score, self.registry)


if __name__ == "__main__":
    unittest.main()
