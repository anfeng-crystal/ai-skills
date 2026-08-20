from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "custom_control.py"
NODE = shutil.which("node")


class CustomControlCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(prefix="kd custom control ")
        self.root = Path(self.temp_dir.name)
        self.project = self.root / "project with spaces"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def run_cli(self, *args: str, expected: int = 0) -> dict:
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), *args, "--json"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            expected,
            msg=f"stdout:\n{completed.stdout}\nstderr:\n{completed.stderr}",
        )
        stream = completed.stdout if completed.stdout.strip() else completed.stderr
        return json.loads(stream)

    def init_project(self) -> dict:
        return self.run_cli(
            "init",
            "--project",
            str(self.project),
            "--control-id",
            "ztjg_demo_control",
            "--display-name",
            "示例控件",
            "--domain",
            "ztjg",
            "--module",
            "demo",
            "--platform-version",
            "8.0.1",
            "--targets",
            "pc,mobile",
        )

    @unittest.skipUnless(NODE, "node is required for generated project tests")
    def test_full_release_is_deterministic_and_self_verifying(self) -> None:
        created = self.init_project()
        self.assertEqual(created["status"], "created")
        validation = self.run_cli("validate", "--project", str(self.project))
        self.assertEqual(validation["errors"], 0)
        self.assertGreaterEqual(validation["warnings"], 1)

        tests = self.run_cli("test", "--project", str(self.project))
        self.assertEqual(tests["status"], "pass")
        build = self.run_cli("build", "--project", str(self.project))
        self.assertIn("index.js", build["files"])

        release_dir = self.root / "release"
        released = self.run_cli(
            "release", "--project", str(self.project), "--output-dir", str(release_dir)
        )
        archive = Path(released["archive"])
        first_bytes = archive.read_bytes()
        verified = self.run_cli(
            "verify-package", "--project", str(self.project), "--archive", str(archive)
        )
        self.assertEqual(verified["status"], "pass")
        self.assertEqual(verified["files"], ["css/control.css", "html/control.html", "index.js"])

        self.run_cli(
            "release",
            "--project",
            str(self.project),
            "--output-dir",
            str(release_dir),
            "--replace",
        )
        self.assertEqual(first_bytes, archive.read_bytes())
        digest = hashlib.sha256(first_bytes).hexdigest()
        checksum = (release_dir / f"{archive.name}.sha256").read_text(encoding="utf-8")
        self.assertTrue(checksum.startswith(digest))

    def test_fix_only_repairs_deterministic_id_mismatches(self) -> None:
        self.init_project()
        config_path = self.project / "cosmic-control.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["platform"]["schemeId"] = "wrong_scheme"
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        entry = self.project / "src" / "index.js"
        entry.write_text(
            entry.read_text(encoding="utf-8").replace(
                "KDApi.register('ztjg_demo_control'", "KDApi.register('wrong_control'"
            ),
            encoding="utf-8",
        )
        failed = self.run_cli("validate", "--project", str(self.project), expected=1)
        self.assertGreaterEqual(failed["errors"], 2)
        fixed = self.run_cli("validate", "--project", str(self.project), "--fix")
        self.assertEqual(fixed["errors"], 0)
        self.assertEqual(len(fixed["changes"]), 2)

    def test_missing_resource_and_secret_block_release(self) -> None:
        self.init_project()
        (self.project / "src" / "html" / "control.html").unlink()
        entry = self.project / "src" / "index.js"
        entry.write_text(
            entry.read_text(encoding="utf-8") + "\nconst token = 'not-a-placeholder';\n",
            encoding="utf-8",
        )
        failed = self.run_cli("validate", "--project", str(self.project), expected=1)
        codes = {finding["code"] for finding in failed["findings"]}
        self.assertIn("CC106", codes)
        self.assertIn("CC122", codes)
        blocked = self.run_cli(
            "release",
            "--project",
            str(self.project),
            "--output-dir",
            str(self.root / "release"),
            expected=2,
        )
        self.assertEqual(blocked["status"], "error")

    def test_environment_variants_are_never_packaged(self) -> None:
        self.init_project()
        (self.project / "src" / ".env.production").write_text(
            "API_KEY=should-not-ship\n", encoding="utf-8"
        )
        failed = self.run_cli("validate", "--project", str(self.project), expected=1)
        self.assertIn("CC102", {finding["code"] for finding in failed["findings"]})
        release_dir = self.root / "release"
        blocked = self.run_cli(
            "release",
            "--project",
            str(self.project),
            "--output-dir",
            str(release_dir),
            expected=2,
        )
        self.assertEqual(blocked["status"], "error")
        self.assertFalse(release_dir.exists())

    @unittest.skipUnless(NODE, "node is required for JavaScript parser checks")
    def test_javascript_parser_and_xss_checks_block_invalid_source(self) -> None:
        self.init_project()
        entry = self.project / "src" / "index.js"
        entry.write_text(
            entry.read_text(encoding="utf-8").replace(
                "self.model.dom.innerHTML = markup;",
                "self.model.dom.innerHTML = props;\n          eval('broken');\n          const invalid = ;",
            ),
            encoding="utf-8",
        )
        failed = self.run_cli("validate", "--project", str(self.project), expected=1)
        codes = {finding["code"] for finding in failed["findings"]}
        self.assertIn("CC123", codes)
        self.assertIn("CC125", codes)
        self.assertIn("CC126", codes)

    def test_verify_rejects_traversal_and_project_files(self) -> None:
        self.init_project()
        archive = self.root / "unsafe.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr("../escape.js", "bad")
            bundle.writestr("index.js", "KDApi.register('ztjg_demo_control', function () {});")
            bundle.writestr("package.json", "{}")
        failed = self.run_cli(
            "verify-package",
            "--project",
            str(self.project),
            "--archive",
            str(archive),
            expected=1,
        )
        codes = {finding["code"] for finding in failed["findings"]}
        self.assertIn("CC302", codes)
        self.assertIn("CC304", codes)

    def test_verify_reuses_complete_runtime_validation(self) -> None:
        self.init_project()
        archive = self.root / "invalid-runtime.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr(
                "index.js",
                "KDApi.register('ztjg_demo_control', function () {}); eval('unsafe');",
            )
        failed = self.run_cli(
            "verify-package",
            "--project",
            str(self.project),
            "--archive",
            str(archive),
            expected=1,
        )
        codes = {finding["code"] for finding in failed["findings"]}
        self.assertIn("CC114", codes)
        self.assertIn("CC115", codes)
        self.assertIn("CC125", codes)

    def test_verify_rejects_windows_collisions_and_corrupt_binary(self) -> None:
        self.init_project()
        collision = self.root / "collision.zip"
        with zipfile.ZipFile(collision, "w") as bundle:
            bundle.writestr("a.js", "one")
            bundle.writestr("A.js", "two")
        failed = self.run_cli(
            "verify-package",
            "--project",
            str(self.project),
            "--archive",
            str(collision),
            expected=1,
        )
        self.assertIn("CC315", {finding["code"] for finding in failed["findings"]})

        corrupt = self.root / "corrupt.zip"
        payload = b"\x00binary-crc-evidence\xff"
        source = self.project / "src"
        with zipfile.ZipFile(corrupt, "w", compression=zipfile.ZIP_STORED) as bundle:
            bundle.writestr("index.js", (source / "index.js").read_bytes())
            bundle.writestr("css/control.css", (source / "css" / "control.css").read_bytes())
            bundle.writestr("html/control.html", (source / "html" / "control.html").read_bytes())
            bundle.writestr("image.bin", payload)
        content = bytearray(corrupt.read_bytes())
        offset = content.find(payload)
        self.assertGreaterEqual(offset, 0)
        content[offset + 1] ^= 0x01
        corrupt.write_bytes(content)
        failed = self.run_cli(
            "verify-package",
            "--project",
            str(self.project),
            "--archive",
            str(corrupt),
            expected=1,
        )
        self.assertIn("CC309", {finding["code"] for finding in failed["findings"]})

    @unittest.skipUnless(NODE, "node is required for external build tests")
    def test_external_build_requires_explicit_command_gate(self) -> None:
        self.init_project()
        config_path = self.project / "cosmic-control.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["build"] = {
            "mode": "external",
            "outputDir": "dist/ztjg_demo_control",
            "command": ["node", "tools/build.mjs"],
        }
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        blocked = self.run_cli("build", "--project", str(self.project), expected=2)
        self.assertIn("--run-command", blocked["error"])
        built = self.run_cli("build", "--project", str(self.project), "--run-command")
        self.assertEqual(built["status"], "pass")

    @unittest.skipUnless(NODE, "node is required for external build tests")
    def test_external_build_cannot_release_stale_output(self) -> None:
        self.init_project()
        self.run_cli("build", "--project", str(self.project))
        entry = self.project / "src" / "index.js"
        entry.write_text(entry.read_text(encoding="utf-8") + "\n// fresh-source-marker\n", encoding="utf-8")
        config_path = self.project / "cosmic-control.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["build"] = {
            "mode": "external",
            "outputDir": "dist/ztjg_demo_control",
            "command": ["node", "-e", "void 0"],
        }
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
        release_dir = self.root / "release"
        blocked = self.run_cli(
            "release",
            "--project",
            str(self.project),
            "--output-dir",
            str(release_dir),
            "--run-command",
            expected=2,
        )
        self.assertEqual(blocked["status"], "error")
        self.assertFalse((release_dir / "ztjg_demo_control-0.1.0.zip").exists())
if __name__ == "__main__":
    unittest.main()
