from __future__ import annotations

import copy
import tempfile
import unittest
import wave
from io import BytesIO
from pathlib import Path

from esn.cli import main
from esn.model import ValidationError, load_json, load_registry
from esn.playback import load_playback_registry, render_wav, resolve_profile

ROOT = Path(__file__).resolve().parents[1]


class PlaybackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = load_registry(ROOT / "registries" / "core.json")
        cls.score = load_json(ROOT / "examples" / "first-score.esn.json")
        cls.playback = load_playback_registry(ROOT / "playback" / "core.json", cls.sources)

    def test_reference_profiles_cover_every_event(self) -> None:
        for event in self.score["events"]:
            self.assertIsInstance(resolve_profile(self.playback, event), dict)

    def test_wav_render_is_byte_deterministic(self) -> None:
        first = render_wav(self.score, self.sources, self.playback)
        second = render_wav(copy.deepcopy(self.score), self.sources, self.playback)
        self.assertEqual(first, second)

    def test_wav_contract(self) -> None:
        payload = render_wav(self.score, self.sources, self.playback)
        self.assertTrue(payload.startswith(b"RIFF"))
        self.assertEqual(payload[8:12], b"WAVE")
        with wave.open(BytesIO(payload), "rb") as wav:
            self.assertEqual(wav.getnchannels(), 1)
            self.assertEqual(wav.getsampwidth(), 2)
            self.assertEqual(wav.getframerate(), 22050)
            self.assertGreater(wav.getnframes(), 1000)

    def test_pitch_curve_affects_audio(self) -> None:
        curved = render_wav(self.score, self.sources, self.playback)
        altered = copy.deepcopy(self.score)
        cat = next(event for event in altered["events"] if event["id"] == "cat-meow")
        del cat["pitch_curve"]
        straight = render_wav(altered, self.sources, self.playback)
        self.assertNotEqual(curved, straight)

    def test_missing_profile_is_rejected(self) -> None:
        broken = dict(self.playback)
        broken["profiles"] = {}
        with self.assertRaisesRegex(ValidationError, "no playback profile"):
            resolve_profile(broken, self.score["events"][0])

    def test_cli_audio_matches_renderer(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "score.wav"
            result = main([
                "audio", str(ROOT / "examples" / "first-score.esn.json"),
                "--registry", str(ROOT / "registries" / "core.json"),
                "--playback", str(ROOT / "playback" / "core.json"),
                "-o", str(output),
            ])
            self.assertEqual(result, 0)
            self.assertEqual(output.read_bytes(), render_wav(self.score, self.sources, self.playback))

    def test_playback_registry_rejects_unknown_source(self) -> None:
        bad = load_json(ROOT / "playback" / "core.json")
        bad["profiles"][0]["source"] = "animal:dragon"
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.json"
            path.write_text(__import__("json").dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "not registered"):
                load_playback_registry(path, self.sources)


if __name__ == "__main__":
    unittest.main()
