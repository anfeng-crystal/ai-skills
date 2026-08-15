import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
CONFIG_CHECK = SKILL_ROOT / "scripts" / "cosmic-config-check.py"


class ConfigCheckSubprocessTest(unittest.TestCase):
    def run_check(self, cwd: Path, *args: str):
        return subprocess.run(
            [sys.executable, str(CONFIG_CHECK), *args],
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_requires_explicit_config(self):
        with tempfile.TemporaryDirectory(prefix="cosmic config check ") as temp_name:
            process = self.run_check(Path(temp_name))

        self.assertEqual(2, process.returncode)
        self.assertIn("--config", process.stderr)
        self.assertIn("required", process.stderr)

    def test_relative_environment_config_is_resolved_from_parent_project(self):
        with tempfile.TemporaryDirectory(prefix="cosmic config check ") as temp_name:
            project_root = Path(temp_name) / "project"
            module_root = project_root / "code" / "module"
            module_root.mkdir(parents=True)
            knowledge_db = project_root / "knowledge.db"
            knowledge_db.touch()
            config_path = project_root / "ok-cosmic.dev.json"
            config_path.write_text(
                json.dumps({"graph": {"dbPath": "knowledge.db"}}),
                encoding="utf-8",
            )

            process = self.run_check(
                module_root,
                "--config",
                "ok-cosmic.dev.json",
                "--json",
            )

        report = json.loads(process.stdout)
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertTrue(report["ok"])
        self.assertEqual(str(config_path.resolve()), report["configPath"])


if __name__ == "__main__":
    unittest.main()
