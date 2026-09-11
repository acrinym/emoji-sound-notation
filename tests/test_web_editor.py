from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WebEditorTests(unittest.TestCase):
    def test_consumer_entrypoint_and_launcher_exist(self) -> None:
        landing = (ROOT / "index.html").read_text(encoding="utf-8")
        launcher = (ROOT / "launch_esn.py").read_text(encoding="utf-8")
        self.assertIn("Draw a sound scene. Hear the sketch. Hand it off.", landing)
        self.assertIn("Open the sound canvas", landing)
        self.assertTrue((ROOT / "START_ESN.cmd").is_file())
        self.assertIn("ThreadingHTTPServer", launcher)

    def test_esn2_editor_surface_is_customer_wired(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "editor.js").read_text(encoding="utf-8")
        for text in ("Play score", "Save project", "Cue sheet", "MIDI", "Score defaults", "Track", "Section", "Harmony"):
            self.assertIn(text, html)
        for element_id in ("scene-tempo", "scene-tuning", "scene-meter-num", "scene-key", "track-select", "section-select", "section-source", "split-section", "add-chord", "explode-chord"):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn('src="score-domain.js"', html)
        self.assertIn("AudioContext", script)
        self.assertIn("pointerdown", script)

    def test_editor_uses_all_binding_layers(self) -> None:
        script = (ROOT / "web" / "editor.js").read_text(encoding="utf-8")
        for path in ("../registries/core.json", "../playback/core.json", "../visual/core.json", "../interchange/core.json", "../soundpacks/reference.json"):
            self.assertIn(path, script)
        self.assertIn("EsnScoreDomain", script)
        self.assertIn("pitch_policy", script)
        self.assertIn("structuredClone", script)

    def test_project_lifecycle_migrates_legacy_and_saves_esn2(self) -> None:
        script = (ROOT / "web" / "editor.js").read_text(encoding="utf-8")
        for symbol in ("newScene", "openProject", "normalizeScore", "commitScoreSettings", "exportScore"):
            self.assertIn(f"function {symbol}", script)
        self.assertIn('score.format==="esn/1"?migrateV1ToV2', script)
        self.assertIn('format:"esn/2"', script)
        self.assertIn('$("project-file").addEventListener("change"', script)

    def test_click_selection_and_drag_threshold_regression(self) -> None:
        script = (ROOT / "web" / "editor.js").read_text(encoding="utf-8")
        self.assertIn("Math.abs(dx)<3&&Math.abs(dy)<3", script)
        self.assertIn("if(!moved)return", script)
        self.assertIn("state.selectedObjectId=obj.id", script)
        self.assertIn("chip.onclick=e=>", script)

    def test_editor_exports_loss_aware_handoffs(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "editor.js").read_text(encoding="utf-8")
        domain = (ROOT / "web" / "interchange-domain.js").read_text(encoding="utf-8")
        self.assertIn('id="export-cues"', html)
        self.assertIn('id="export-midi"', html)
        self.assertIn("function exportCues", script)
        self.assertIn("function exportMidi", script)
        self.assertIn("browserInterchangeScore", script)
        self.assertIn("flattened loss-aware", script)
        self.assertIn("cueCsv", domain)
        self.assertIn("midiBytes", domain)

    def test_sound_pack_workflow_survives_score_model_change(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "editor.js").read_text(encoding="utf-8")
        for element_id in ("load-pack", "pack-folder", "pack-name", "choose-sample", "sample-file", "sample-loop", "sample-root", "clear-sample"):
            self.assertIn(f'id="{element_id}"', html)
        for symbol in ("loadSoundPackFolder", "effectiveRealization", "prepareRealization", "setLocalSample"):
            self.assertIn(f"function {symbol}", script)
        self.assertIn('origin:"missing"', script)
        self.assertIn("safe fallback", script)

    def test_cat_reference_score_proves_tracks_sections_and_chords(self) -> None:
        score = json.loads((ROOT / "examples" / "cat-counterpoint.esn.json").read_text(encoding="utf-8"))
        self.assertEqual(score["format"], "esn/2")
        self.assertEqual(score["defaults"]["tuning"]["a4_hz"], 432.0)
        self.assertGreaterEqual(len(score["tracks"]), 4)
        cats = [section for track in score["tracks"] for section in track["sections"] if section["source"] == "animal:cat"]
        self.assertGreaterEqual(len(cats), 2)
        chords = [obj for section in cats for obj in section["objects"] if obj["type"] == "chord"]
        self.assertGreaterEqual(len(chords), 2)
        self.assertTrue(any(len(track["sections"]) > 1 for track in score["tracks"]))


if __name__ == "__main__":
    unittest.main()
