from __future__ import annotations

import copy
import json
import math
import struct
import tempfile
import unittest
import wave
from pathlib import Path

from esn.cli import main
from esn.model import ValidationError, load_json, load_registry
from esn.playback import load_playback_registry, render_wav
from esn.soundpack import load_sound_pack, resolve_sound_binding

ROOT = Path(__file__).resolve().parents[1]


def pack_doc(asset: str = "samples/meow.wav") -> dict:
    return {
        "format": "esn-sound-pack/1",
        "id": "test.sample-pack",
        "name": "Test Sample Pack",
        "version": "1.0.0",
        "license": {"name": "CC0 1.0", "spdx": "CC0-1.0"},
        "provenance": {"creator": "ESN tests", "source": "generated fixture"},
        "fallback": "reference_synth",
        "bindings": [{"source": "animal:cat", "gesture": "meow", "asset": asset, "gain": 0.8, "root_note": "C4"}],
    }


def write_tone(path: Path, rate: int = 16000, seconds: float = 0.3) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frames = bytearray()
    for index in range(int(rate * seconds)):
        sample = int(round(math.sin(2 * math.pi * 261.6256 * index / rate) * 12000))
        frames.extend(struct.pack("<h", sample))
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(bytes(frames))


class SoundPackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.sources = load_registry(ROOT / "registries" / "core.json")
        cls.score = load_json(ROOT / "examples" / "first-score.esn.json")
        cls.playback = load_playback_registry(ROOT / "playback" / "core.json", cls.sources)

    def test_reference_pack_is_valid_and_empty_by_design(self) -> None:
        pack = load_sound_pack(ROOT / "soundpacks" / "reference.json", self.sources)
        self.assertEqual(pack["doc"]["format"], "esn-sound-pack/1")
        self.assertEqual(pack["bindings"], {})
        self.assertEqual(pack["missing_assets"], ())

    def test_missing_sample_falls_back_byte_identically(self) -> None:
        baseline = render_wav(self.score, self.sources, self.playback)
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "pack.json"
            manifest.write_text(json.dumps(pack_doc()), encoding="utf-8")
            pack = load_sound_pack(manifest, self.sources)
            self.assertEqual(pack["missing_assets"], ("samples/meow.wav",))
            rendered = render_wav(copy.deepcopy(self.score), self.sources, self.playback, pack)
        self.assertEqual(rendered, baseline)

    def test_sample_backed_render_is_deterministic_and_changes_realization(self) -> None:
        baseline = render_wav(self.score, self.sources, self.playback)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_tone(root / "samples" / "meow.wav")
            manifest = root / "pack.json"
            manifest.write_text(json.dumps(pack_doc()), encoding="utf-8")
            pack = load_sound_pack(manifest, self.sources)
            first = render_wav(copy.deepcopy(self.score), self.sources, self.playback, pack)
            second = render_wav(copy.deepcopy(self.score), self.sources, self.playback, pack)
        self.assertEqual(first, second)
        self.assertNotEqual(first, baseline)
        cat = next(event for event in self.score["events"] if event["id"] == "cat-meow")
        self.assertEqual(resolve_sound_binding(pack, cat)["asset"], "samples/meow.wav")

    def test_cli_validates_pack_and_renders_with_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            write_tone(root / "samples" / "meow.wav")
            manifest = root / "pack.json"
            manifest.write_text(json.dumps(pack_doc()), encoding="utf-8")
            self.assertEqual(main(["sound-pack-validate", "--sound-pack", str(manifest), "--registry", str(ROOT / "registries" / "core.json")]), 0)
            output = root / "sample-backed.wav"
            result = main([
                "audio", str(ROOT / "examples" / "first-score.esn.json"),
                "--registry", str(ROOT / "registries" / "core.json"),
                "--playback", str(ROOT / "playback" / "core.json"),
                "--sound-pack", str(manifest), "-o", str(output),
            ])
            self.assertEqual(result, 0)
            self.assertTrue(output.read_bytes().startswith(b"RIFF"))

    def test_pack_rejects_cross_platform_absolute_paths(self) -> None:
        for asset in ("C:/Windows/bad.wav", "C:\\Windows\\bad.wav", "/tmp/bad.wav", "//server/share/bad.wav"):
            bad = load_json(ROOT / "soundpacks" / "reference.json")
            bad["bindings"] = [{"source": "animal:cat", "gesture": "meow", "asset": asset}]
            with tempfile.TemporaryDirectory() as temp_dir:
                path = Path(temp_dir) / "pack.json"
                path.write_text(json.dumps(bad), encoding="utf-8")
                with self.assertRaisesRegex(ValidationError, "relative .wav path"):
                    load_sound_pack(path, self.sources)

    def test_pack_rejects_path_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest = Path(temp_dir) / "pack.json"
            manifest.write_text(json.dumps(pack_doc("../escape.wav")), encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "relative .wav path"):
                load_sound_pack(manifest, self.sources)


if __name__ == "__main__":
    unittest.main()
