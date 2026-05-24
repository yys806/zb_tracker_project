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

        self.assertIn("<title>OrangePi 云台控制台</title>", html)
        self.assertIn(WEB_CONSOLE_VERSION, html)
        self.assertIn("v27-status-reset-smooth", html)
        self.assertIn('xhr.setRequestHeader("Cache-Control", "no-store")', html)
        self.assertIn('xhr.timeout = 3500;', html)
        self.assertIn('xhr.ontimeout', html)
        self.assertIn('xhr.onerror', html)
        self.assertIn("request timeout", html)
        self.assertIn("控制台脚本已加载", html)
        self.assertIn("表单控制已可用", html)
        self.assertNotIn("正在连接控制台...", html)
        self.assertIn('id="startTracking" type="submit">开始跟踪</button>', html)
        self.assertIn('id="reset" type="submit">复位</button>', html)
        self.assertIn("/api/status", html)
        self.assertIn("window.setTimeout(refreshStatus, 0);", html)
        self.assertIn('setInterval(refreshStatus, 1000);', html)
        self.assertIn("XMLHttpRequest", html)

        unsupported_js_markers = ("async function", "await ", "=>", "const ", "let ", "${")
        for marker in unsupported_js_markers:
            self.assertNotIn(marker, html)

        mojibake_markers = ("�", "锟", "娴", "閺", "閹", "闊", "閸", "閻", "缁")
        for marker in mojibake_markers:
            self.assertNotIn(marker, html)

    def test_web_console_has_no_js_fallback_forms(self) -> None:
        html = INDEX_HTML.decode("utf-8")

        self.assertIn('class="button-strip"', html)
        self.assertIn('action="/ui/calibrate"', html)
        self.assertIn('action="/ui/start"', html)
        self.assertIn('action="/ui/stop"', html)
        self.assertIn('action="/ui/reset"', html)
        self.assertIn('method="get"', html)
        self.assertIn('type="submit"', html)
        self.assertNotIn('action="/ui/save-config"', html)
        self.assertNotIn('action="/ui/resume"', html)

    def test_web_console_only_exposes_four_operator_buttons(self) -> None:
        html = INDEX_HTML.decode("utf-8")

        self.assertEqual(html.count("<button "), 4)
        for label in ("中心自动标定", "开始跟踪", "急停", "复位"):
            self.assertIn(f">{label}</button>", html)
        for removed_label in ("保存当前 HSV", "恢复跟踪", "保存配置", "切换颜色"):
            self.assertNotIn(removed_label, html)

    def test_web_server_handles_no_js_ui_routes(self) -> None:
        from orangepi_tracker.web_server import MjpegHandler

        source = MjpegHandler.do_GET.__code__.co_consts
        joined = "\n".join(str(item) for item in source)

        self.assertIn("/ui/calibrate", joined)
        self.assertIn("/ui/start", joined)
        self.assertIn("/ui/stop", joined)
        self.assertIn("/ui/reset", joined)
        self.assertNotIn("/ui/resume", joined)
        self.assertNotIn("/ui/save-config", joined)

    def test_web_console_exposes_reset_button_not_center_button(self) -> None:
        html = INDEX_HTML.decode("utf-8")

        self.assertIn('id="reset"', html)
        self.assertIn("/api/reset", html)
        self.assertIn('$("calibrate").onclick', html)
        self.assertIn('$("startTracking").onclick', html)
        self.assertIn('$("stop").onclick', html)
        self.assertIn('$("reset").onclick', html)
        self.assertNotIn('id="saveConfig"', html)
        self.assertNotIn('id="resume"', html)
        self.assertNotIn("/api/save-config", html)
        self.assertNotIn("/api/resume", html)
        self.assertNotIn('id="center"', html)
        self.assertNotIn("/api/center", html)

    def test_web_console_uses_auto_calibration_not_manual_hsv_or_color_pick(self) -> None:
        html = INDEX_HTML.decode("utf-8")

        self.assertIn('id="calibrate"', html)
        self.assertIn('id="hsvReadout"', html)
        self.assertNotIn('id="colorSelect"', html)
        self.assertNotIn('id="applyColor"', html)
        self.assertNotIn('id="applyHsv"', html)
        self.assertNotIn('id="hsvEditor"', html)
        self.assertNotIn("/api/color", html)
        self.assertNotIn("/api/hsv", html)

    def test_status_refresh_is_designed_to_show_hsv_and_live_status(self) -> None:
        html = INDEX_HTML.decode("utf-8")

        self.assertIn("formatHsv(data.hsv_ranges)", html)
        self.assertIn('data.hsv_ranges', html)
        self.assertIn('$("state").textContent', html)
        self.assertIn('$("fps").textContent', html)
        self.assertIn('$("angles").textContent', html)
        self.assertIn('$("hsvReadout").textContent', html)

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
