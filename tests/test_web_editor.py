from __future__ import annotations

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

    def test_editor_surface_is_customer_wired(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "editor.js").read_text(encoding="utf-8")
        for text in ("Preview scene", "Save project", "Cue sheet", "MIDI", "New", "Open"):
            self.assertIn(text, html)
        for element_id in ("scene-title", "scene-tempo", "project-file", "color-mode"):
            self.assertIn(f'id="{element_id}"', html)
        self.assertIn('src="esn-domain.js"', html)
        self.assertIn('src="visual-domain.js"', html)
        self.assertIn('src="interchange-domain.js"', html)
        self.assertIn("AudioContext", script)
        self.assertIn("pointerdown", script)

    def test_editor_uses_all_binding_layers(self) -> None:
        script = (ROOT / "web" / "editor.js").read_text(encoding="utf-8")
        self.assertIn("../registries/core.json", script)
        self.assertIn("../playback/core.json", script)
        self.assertIn("../visual/core.json", script)
        self.assertIn("../interchange/core.json", script)
        self.assertIn("pitch_policy", script)
        self.assertIn("structuredClone", script)

    def test_editor_renders_canonical_glyphs_and_plain_color_modes(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "editor.js").read_text(encoding="utf-8")
        visual_domain = (ROOT / "web" / "visual-domain.js").read_text(encoding="utf-8")
        self.assertIn("Note names", html)
        self.assertIn("Scale steps", html)
        self.assertIn("EsnVisualDomain", script)
        self.assertIn("sourceLabel", script)
        self.assertIn("canonical-glyph", visual_domain)

    def test_project_lifecycle_is_real_not_export_only(self) -> None:
        script = (ROOT / "web" / "editor.js").read_text(encoding="utf-8")
        for symbol in ("newScene", "openProjectFile", "validateProject", "commitSceneSettings"):
            self.assertIn(f"function {symbol}", script)
        self.assertIn('$("project-file").addEventListener("change"', script)
        self.assertIn('$("scene-tempo").addEventListener("change"', script)
        self.assertIn("reference synth", script)

    def test_editor_exports_loss_aware_handoffs(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "editor.js").read_text(encoding="utf-8")
        domain = (ROOT / "web" / "interchange-domain.js").read_text(encoding="utf-8")
        self.assertIn('id="export-cues"', html)
        self.assertIn('id="export-midi"', html)
        self.assertIn("exportCueSheet", script)
        self.assertIn("exportMidi", script)
        self.assertIn("cueCsv", domain)
        self.assertIn("midiBytes", domain)


if __name__ == "__main__":
    unittest.main()
