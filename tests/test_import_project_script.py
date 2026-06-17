from pathlib import Path
import subprocess
import tempfile
import unittest


class ImportProjectScriptTests(unittest.TestCase):
    def test_import_script_repairs_linux_permissions_after_unzip(self):
        script = Path("scripts/run/00_import_project.sh").read_text(encoding="utf-8")

        self.assertIn('find "$TARGET_DIR" -type d -exec chmod 755 {} +', script)
        self.assertIn('find "$TARGET_DIR" -type f -exec chmod 644 {} +', script)
        self.assertIn('find "$TARGET_DIR/scripts/run" -type f -name "*.sh" -exec chmod 755 {} +', script)
        self.assertIn("import orangepi_tracker", script)

    def test_common_script_strips_crlf_from_local_env(self):
        common_script = Path("scripts/run/_common.sh").read_text(encoding="utf-8")
        self.assertIn("tr -d", common_script)
        self.assertIn("'\\r'", common_script)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_dir = root / "scripts" / "run"
            run_dir.mkdir(parents=True)
            (run_dir / "_common.sh").write_text(common_script, encoding="utf-8")
            (root / ".env.local").write_bytes(
                b"DEEPSEEK_API_BASE=https://api.deepseek.com\r\nDEEPSEEK_MODEL=deepseek-v4-flash\r\n"
            )

            command = (
                "PYTHON_BIN=/usr/bin/true PIP_BIN=/usr/bin/true "
                "source scripts/run/_common.sh >/dev/null; "
                'printf %s "$DEEPSEEK_API_BASE" | od -An -tx1'
            )
            result = subprocess.run(["bash", "-lc", command], cwd=root, check=True, capture_output=True, text=True)

        self.assertNotIn("0d", result.stdout.split())
