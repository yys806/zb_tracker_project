from pathlib import Path
import unittest


class ImportProjectScriptTests(unittest.TestCase):
    def test_import_script_repairs_linux_permissions_after_unzip(self):
        script = Path("scripts/run/00_import_project.sh").read_text(encoding="utf-8")

        self.assertIn('find "$TARGET_DIR" -type d -exec chmod 755 {} +', script)
        self.assertIn('find "$TARGET_DIR" -type f -exec chmod 644 {} +', script)
        self.assertIn('find "$TARGET_DIR/scripts/run" -type f -name "*.sh" -exec chmod 755 {} +', script)
        self.assertIn("import orangepi_tracker", script)
