from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")
if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from orangepi_tracker.web_server import INDEX_HTML, WEB_CONSOLE_VERSION


def extract_inline_script(html: str) -> str:
    start = html.index("<script>") + len("<script>")
    end = html.index("</script>")
    return html[start:end]


class WebServerMarkupTests(unittest.TestCase):
    def test_web_console_markup_is_valid_utf8_and_binds_controls(self) -> None:
        html = INDEX_HTML.decode("utf-8")

        self.assertIn(WEB_CONSOLE_VERSION, html)
        self.assertIn('xhr.setRequestHeader("Cache-Control", "no-store")', html)
        self.assertIn('var requestTimeout = timeoutMs || 6000;', html)
        self.assertIn('xhr.timeout = requestTimeout;', html)
        self.assertIn('var statusPending = false;', html)
        self.assertIn('if (statusPending) return;', html)
        self.assertIn('xhr.ontimeout', html)
        self.assertIn('xhr.onerror', html)
        self.assertIn('action="/ui/flow-toggle"', html)
        self.assertIn('/api/flow-toggle', html)
        self.assertIn('/api/flow', html)
        self.assertIn('action="/ui/gesture-toggle"', html)
        self.assertIn('/api/gesture-toggle', html)
        self.assertIn('/api/gesture', html)
        self.assertIn('id="visionBackend"', html)
        self.assertNotIn('action="/ui/vision-dnn"', html)
        self.assertNotIn('action="/ui/vision-rknn"', html)
        self.assertNotIn('/api/vision-mode', html)
        self.assertIn('/api/ai/analyze', html)
        self.assertIn('setInterval(refreshFlow, 3000);', html)
        self.assertIn('id="trajectoryCanvas"', html)
        self.assertIn('id="heatmapCanvas"', html)
        self.assertIn('id="aiOutput"', html)
        self.assertIn('requestAi("status"', html)
        self.assertIn('requestAi("vision"', html)
        self.assertIn('requestAi("diagnosis"', html)

    def test_web_console_has_operator_and_ai_buttons(self) -> None:
        html = INDEX_HTML.decode("utf-8")

        self.assertEqual(html.count("<button "), 9)
        for label in ("中心自动标定", "开始跟踪", "急停", "复位", "开启光流分析"):
            self.assertIn(label, html)
        for label in ("状态解释", "视觉解释", "异常诊断"):
            self.assertIn(label, html)

    def test_web_server_handles_no_js_ui_routes(self) -> None:
        from orangepi_tracker.web_server import MjpegHandler

        source = MjpegHandler.do_GET.__code__.co_consts
        joined = "\n".join(str(item) for item in source)

        self.assertIn("/ui/calibrate", joined)
        self.assertIn("/ui/start", joined)
        self.assertIn("/ui/stop", joined)
        self.assertIn("/ui/reset", joined)
        self.assertIn("/ui/flow-toggle", joined)
        self.assertIn("/ui/gesture-toggle", joined)
        self.assertNotIn("/ui/vision-dnn", joined)
        self.assertNotIn("/ui/vision-rknn", joined)
        self.assertNotIn("/ui/resume", joined)
        self.assertNotIn("/ui/save-config", joined)

    def test_status_refresh_is_designed_to_show_flow_motion(self) -> None:
        html = INDEX_HTML.decode("utf-8")

        self.assertIn('$("flowState").textContent', html)
        self.assertIn('drawTrajectory(data);', html)
        self.assertIn('drawHeatmap(data);', html)

    def test_inline_javascript_has_valid_syntax(self) -> None:
        node = shutil.which("node")
        if node is None:
            self.skipTest("node is not available")

        html = INDEX_HTML.decode("utf-8")
        script = extract_inline_script(html)
        with tempfile.TemporaryDirectory() as tmpdir:
            script_path = Path(tmpdir) / "web_console.js"
            script_path.write_text(script, encoding="utf-8")
            result = subprocess.run(
                [node, "--check", str(script_path)],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
