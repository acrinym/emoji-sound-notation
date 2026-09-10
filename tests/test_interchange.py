from __future__ import annotations

import csv
import hashlib
import io
import json
import struct
import tempfile
import unittest
from pathlib import Path

from esn.interchange import (
    canonical_report, cue_sheet_csv, export_smf, load_interchange_profile,
)
from esn.model import ValidationError, load_json, load_registry
from esn.score import TICKS_PER_QUARTER, migrate_v1_to_v2

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "registries" / "core.json"
SCORE_PATH = ROOT / "examples" / "first-score.esn.json"
PROFILE_PATH = ROOT / "interchange" / "core.json"


def _vlq(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    while True:
        byte = data[offset]
        offset += 1
        value = (value << 7) | (byte & 0x7F)
        if not byte & 0x80:
            return value, offset

def _tracks(midi: bytes) -> tuple[int, int, list[bytes]]:
    if midi[:4] != b"MThd":
        raise AssertionError("missing MIDI header")
    length, fmt, count, division = struct.unpack(">IHHH", midi[4:14])
    if length != 6:
        raise AssertionError("unexpected MIDI header length")
    offset = 14
    tracks: list[bytes] = []
    for _ in range(count):
        if midi[offset:offset + 4] != b"MTrk":
            raise AssertionError("missing track chunk")
        size = struct.unpack(">I", midi[offset + 4:offset + 8])[0]
        tracks.append(midi[offset + 8:offset + 8 + size])
        offset += 8 + size
    if offset != len(midi):
        raise AssertionError("trailing MIDI bytes")
    return fmt, division, tracks


def _cue_payloads(track: bytes) -> list[str]:
    payloads: list[str] = []
    offset = 0
    while offset < len(track):
        _delta, offset = _vlq(track, offset)
        status = track[offset]
        offset += 1
        if status == 0xFF:
            kind = track[offset]
            offset += 1
            size, offset = _vlq(track, offset)
            payload = track[offset:offset + size]
            offset += size
            if kind == 0x07:
                payloads.append(payload.decode("ascii"))
            if kind == 0x2F:
                break
        elif status & 0xF0 in {0xC0, 0xD0}:
            offset += 1
        else:
            offset += 2
    return payloads

def _note_messages(track: bytes) -> list[tuple[int, int, int, int, int]]:
    out = []
    offset = 0
    tick = 0
    while offset < len(track):
        delta, offset = _vlq(track, offset)
        tick += delta
        status = track[offset]
        offset += 1
        if status == 0xFF:
            kind = track[offset]
            offset += 1
            size, offset = _vlq(track, offset)
            offset += size
            if kind == 0x2F:
                break
        elif status & 0xF0 in {0xC0, 0xD0}:
            offset += 1
        else:
            first, second = track[offset], track[offset + 1]
            offset += 2
            if status & 0xF0 in {0x80, 0x90}:
                out.append((tick, status & 0xF0, status & 0x0F, first, second))
    return out

class InterchangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = load_registry(REGISTRY_PATH)
        cls.score = load_json(SCORE_PATH)
        cls.profile = load_interchange_profile(PROFILE_PATH, cls.registry)

    def test_core_profile_and_smf_header(self) -> None:
        self.assertEqual(set(self.profile["mappings"]), {"instrument:piano", "instrument:bell", "percussion:drum"})
        midi, report = export_smf(self.score, self.registry, self.profile)
        fmt, division, tracks = _tracks(midi)
        self.assertEqual(fmt, 1)
        self.assertEqual(division, 480)
        self.assertEqual(len(tracks), 5)
        self.assertEqual(report["events_total"], 6)
        self.assertEqual(report["midi_notes"], 3)
        self.assertEqual(report["cue_only"], 3)

    def test_export_is_byte_deterministic(self) -> None:
        first, report_a = export_smf(self.score, self.registry, self.profile)
        second, report_b = export_smf(self.score, self.registry, self.profile)
        self.assertEqual(first, second)
        self.assertEqual(canonical_report(report_a), canonical_report(report_b))

    def test_every_event_has_a_timed_semantic_cue(self) -> None:
        midi, _report = export_smf(self.score, self.registry, self.profile)
        _fmt, _division, tracks = _tracks(midi)
        cues = _cue_payloads(tracks[-1])
        self.assertEqual(len(cues), len(self.score["events"]))
        decoded = [json.loads(text.removeprefix("ESN1:")) for text in cues]
        self.assertEqual({event["id"] for event in decoded}, {event["id"] for event in self.score["events"]})

    def test_cue_sheet_contains_every_event_and_real_time(self) -> None:
        rows = list(csv.DictReader(io.StringIO(cue_sheet_csv(self.score, self.registry, self.profile))))
        self.assertEqual(len(rows), 6)
        by_id = {row["id"]: row for row in rows}
        self.assertEqual(by_id["piano-c4"]["midi_status"], "midi_note")
        self.assertEqual(by_id["rain-bed"]["midi_status"], "cue_only")
        self.assertEqual(by_id["door-slam"]["start_seconds"], "2.343750")
        self.assertEqual(by_id["drum-hit"]["midi_channel"], "10")

    def test_pitch_curve_loss_is_reported_when_mapped(self) -> None:
        raw = load_json(PROFILE_PATH)
        raw["midi_sources"].append({"source": "animal:cat", "mode": "pitched", "channel": 2, "program": 80})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            profile = load_interchange_profile(path, self.registry)
            _midi, report = export_smf(self.score, self.registry, profile)
        cat = next(row for row in report["events"] if row["id"] == "cat-meow")
        self.assertEqual(cat["status"], "midi_note")
        self.assertIn("pitch_curve_flattened", cat["losses"])

    def test_overlapping_same_note_preserves_independent_lifetimes(self) -> None:
        score = {
            "format": "esn/1", "title": "Overlap", "tempo_bpm": 120,
            "events": [
                {"id":"first","source":"instrument:piano","gesture":"strike","onset":0,"duration":2,"pitch":{"note":"C4"},"dynamics":0.7},
                {"id":"second","source":"instrument:piano","gesture":"strike","onset":1,"duration":2,"pitch":{"note":"C4"},"dynamics":0.8},
            ],
        }
        midi, report = export_smf(score, self.registry, self.profile)
        self.assertEqual(hashlib.sha256(midi).hexdigest().upper(), "2FC7433B4B71D118821C59D30AB1A09664748025EDF291A00F177AFE437EA2A1")
        _fmt, _division, tracks = _tracks(midi)
        notes = [message for track in tracks for message in _note_messages(track)]
        self.assertEqual([(t, status, channel, note) for t, status, channel, note, _velocity in notes], [
            (0, 0x90, 0, 60), (480, 0x90, 2, 60),
            (960, 0x80, 0, 60), (1440, 0x80, 2, 60),
        ])
        by_id = {row["id"]: row for row in report["events"]}
        self.assertEqual(by_id["first"]["channel"], 0)
        self.assertEqual(by_id["second"]["channel"], 2)
        self.assertIn("overlap_channel_reassigned", by_id["second"]["losses"])
        rows = {row["id"]: row for row in csv.DictReader(io.StringIO(cue_sheet_csv(score, self.registry, self.profile)))}
        self.assertEqual(rows["second"]["midi_channel"], "3")
        self.assertIn("overlap_channel_reassigned", rows["second"]["midi_status"])

    def test_esn2_interchange_preserves_absolute_timing_and_reports_structure_loss(self) -> None:
        score = migrate_v1_to_v2(self.score, self.registry)
        piano_track = next(track for track in score["tracks"] if track["sections"][0]["source"] == "instrument:piano")
        piano_track["context"] = {"tempo_bpm": 120}
        midi, report = export_smf(score, self.registry, self.profile)
        self.assertTrue(midi.startswith(b"MThd"))
        self.assertEqual(report["source_format"], "esn/2")
        self.assertIn("track_section_structure_flattened", report["score_losses"])
        piano = next(row for row in report["events"] if row["id"] == "piano-c4")
        self.assertEqual(piano["track_id"], piano_track["id"])
        rows = {row["id"]: row for row in csv.DictReader(io.StringIO(cue_sheet_csv(score, self.registry, self.profile)))}
        self.assertEqual(rows["piano-c4"]["start_seconds"], "0.000000")
        self.assertEqual(rows["piano-c4"]["duration_seconds"], "0.500000")
        self.assertTrue(rows["cat-meow"]["track_id"].startswith("track-"))

    def test_cli_exports_midi_report_and_cue_sheet(self) -> None:
        import subprocess, sys
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            midi, report, cues = root / "score.mid", root / "report.json", root / "cues.csv"
            common = [str(SCORE_PATH), "--registry", str(REGISTRY_PATH), "--interchange", str(PROFILE_PATH)]
            result = subprocess.run([sys.executable, "-m", "esn", "midi-export", *common, "-o", str(midi), "--report", str(report)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = subprocess.run([sys.executable, "-m", "esn", "cue-export", *common, "-o", str(cues)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(midi.read_bytes().startswith(b"MThd"))
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["events_total"], 6)
            self.assertEqual(len(list(csv.DictReader(io.StringIO(cues.read_text(encoding="utf-8"))))), 6)

    def test_conflicting_programs_on_same_channel_are_rejected(self) -> None:
        raw = load_json(PROFILE_PATH)
        raw["midi_sources"].append({"source": "animal:cat", "mode": "pitched", "channel": 0, "program": 80})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "different program"):
                load_interchange_profile(path, self.registry)

    def test_unknown_source_mapping_is_rejected(self) -> None:
        raw = load_json(PROFILE_PATH)
        raw["midi_sources"].append({"source": "missing:source", "mode": "fixed", "channel": 3, "note": 60})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "not registered"):
                load_interchange_profile(path, self.registry)


if __name__ == "__main__":
    unittest.main()
