import copy
import unittest

from esn.model import load_json, load_registry
from esn.score import (
    DEFAULT_A4_HZ,
    DEFAULT_TEMPO_BPM,
    TICKS_PER_QUARTER,
    expand_chord_pitches,
    explode_chord,
    factory_defaults,
    flatten_score,
    migrate_v1_to_v2,
    split_section,
    validate_score_v2,
)


class ScoreGrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry = load_registry("registries/core.json")
        cls.legacy = load_json("examples/first-score.esn.json")

    def cat_score(self):
        return {
            "format": "esn/2",
            "title": "Cat Chord",
            "length_ticks": 8 * TICKS_PER_QUARTER,
            "defaults": factory_defaults(),
            "tracks": [{
                "id": "cats", "name": "Cat Chorus",
                "context": {},
                "sections": [{
                    "id": "cats-a", "start_tick": 0,
                    "end_tick": 8 * TICKS_PER_QUARTER,
                    "source": "animal:cat", "context": {},
                    "objects": [{
                        "id": "cat-c", "type": "chord", "gesture": "meow",
                        "tick": TICKS_PER_QUARTER,
                        "duration_ticks": TICKS_PER_QUARTER,
                        "root": "C4", "quality": "major", "inversion": 0,
                        "dynamics": 0.8,
                    }],
                }],
            }],
        }

    def test_factory_defaults_are_musical_and_432(self):
        defaults = factory_defaults()
        self.assertEqual(defaults["tempo_bpm"], 96)
        self.assertEqual(defaults["time_signature"], {"numerator": 4, "denominator": 4})
        self.assertEqual(defaults["key"], {"tonic": "C", "scale": "major"})
        self.assertEqual(defaults["tuning"], {"a4_hz": 432.0})
        self.assertEqual(DEFAULT_TEMPO_BPM, 96)
        self.assertEqual(DEFAULT_A4_HZ, 432.0)

    def test_cat_chord_is_valid_and_expands(self):
        score = self.cat_score()
        validate_score_v2(score, self.registry)
        chord = score["tracks"][0]["sections"][0]["objects"][0]
        self.assertEqual(expand_chord_pitches(chord), ["C4", "E4", "G4"])

    def test_chord_inversion_and_pentatonic_stack(self):
        chord = {"root": "C4", "quality": "major", "inversion": 1}
        self.assertEqual(expand_chord_pitches(chord), ["E4", "G4", "C5"])
        chord = {"root": "A3", "quality": "minor_pentatonic", "inversion": 0}
        self.assertEqual(expand_chord_pitches(chord), ["A3", "C4", "D4", "E4", "G4"])

    def test_explode_chord_preserves_timing_and_semantics(self):
        score = self.cat_score()
        exploded = explode_chord(score, "cat-c", self.registry)
        validate_score_v2(exploded, self.registry)
        objects = exploded["tracks"][0]["sections"][0]["objects"]
        self.assertEqual([obj["pitch"]["note"] for obj in objects], ["C4", "E4", "G4"])
        self.assertTrue(all(obj["gesture"] == "meow" for obj in objects))
        self.assertTrue(all(obj["tick"] == TICKS_PER_QUARTER for obj in objects))
        self.assertTrue(all(obj["duration_ticks"] == TICKS_PER_QUARTER for obj in objects))

    def test_split_section_creates_an_unassigned_new_section_without_mutation(self):
        score = self.cat_score()
        before = copy.deepcopy(score["tracks"][0]["sections"][0]["objects"])
        split = split_section(score, "cats", "cats-a", 4 * TICKS_PER_QUARTER)
        sections = split["tracks"][0]["sections"]
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0]["source"], "animal:cat")
        self.assertIsNone(sections[1]["source"])
        self.assertEqual(sections[0]["objects"], before)
        self.assertEqual(sections[1]["objects"], [])

    def test_migrate_v1_to_v2_preserves_legacy_event_meaning(self):
        migrated = migrate_v1_to_v2(self.legacy, self.registry)
        validate_score_v2(migrated, self.registry)
        self.assertEqual(migrated["format"], "esn/2")
        self.assertEqual(migrated["defaults"]["tempo_bpm"], 96)
        flattened = flatten_score(migrated, self.registry)
        by_id = {row["event"]["id"]: row for row in flattened}
        for legacy_event in self.legacy["events"]:
            row = by_id[legacy_event["id"]]
            event = row["event"]
            self.assertEqual(event["source"], legacy_event["source"])
            self.assertEqual(event["gesture"], legacy_event["gesture"])
            self.assertEqual(event.get("pitch"), legacy_event.get("pitch"))
            self.assertAlmostEqual(row["onset_seconds"], legacy_event["onset"] * 0.625)
            self.assertAlmostEqual(row["duration_seconds"], legacy_event["duration"] * 0.625)

    def test_section_tempo_and_tuning_are_independent(self):
        score = self.cat_score()
        track = score["tracks"][0]
        track["context"] = {"tempo_bpm": 120, "tuning": {"a4_hz": 444.0}}
        section = track["sections"][0]
        section["context"] = {"tempo_bpm": 60, "tuning": {"a4_hz": 432.0}}
        rows = flatten_score(score, self.registry)
        self.assertEqual(rows[0]["tempo_bpm"], 60)
        self.assertEqual(rows[0]["a4_hz"], 432.0)
        self.assertAlmostEqual(rows[0]["onset_seconds"], 1.0)
        self.assertAlmostEqual(rows[0]["duration_seconds"], 1.0)

    def test_invalid_sections_and_source_gesture_are_rejected(self):
        score = self.cat_score()
        score["tracks"][0]["sections"][0]["end_tick"] = 999999
        with self.assertRaisesRegex(ValueError, "length_ticks"):
            validate_score_v2(score, self.registry)
        score = self.cat_score()
        score["tracks"][0]["sections"][0]["objects"][0]["gesture"] = "slam"
        with self.assertRaisesRegex(ValueError, "gesture"):
            validate_score_v2(score, self.registry)


if __name__ == "__main__":
    unittest.main()
