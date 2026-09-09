from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class WebEditorTests(unittest.TestCase):
    def test_editor_surface_is_wired(self) -> None:
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "editor.js").read_text(encoding="utf-8")
        self.assertIn("Play score", html)
        self.assertIn("Export ESN", html)
        self.assertIn('src="esn-domain.js"', html)
        self.assertIn('src="editor.js"', html)
        self.assertIn("AudioContext", script)
        self.assertIn("pointerdown", script)
        self.assertIn("exportScore", script)

    def test_editor_uses_semantic_sources_and_playback_profiles(self) -> None:
        script = (ROOT / "web" / "editor.js").read_text(encoding="utf-8")
        self.assertIn("../registries/core.json", script)
        self.assertIn("../playback/core.json", script)
        self.assertIn("pitch_policy", script)
        self.assertIn("structuredClone", script)


if __name__ == "__main__":
    unittest.main()
