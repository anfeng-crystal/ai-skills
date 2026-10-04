"""Offline resource-update regression tests; all homes and ZIPs are synthetic."""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from kddt_common import KddtError
from kddt_resources import apply_job, rollback_backup


class EnvUpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get("KDDT_TEST_TMP"))
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "cosmic-home"
        self.job_dir = self.home / ".kddt-staging" / "test-job"
        self.job_file = self.job_dir / "job.json"
        self.downloads = self.job_dir / "downloads"
        self.downloads.mkdir(parents=True)
        self.cus = self.home / "mservice-cosmic" / "lib" / "cus"
        self.write(self.cus / "existing.jar", b"old-custom")
        self.write(self.cus / "retained.jar", b"retained-custom")
        self.job = {
            "cosmic_home": str(self.home),
            "job_dir": str(self.job_dir),
            "job_file": str(self.job_file),
            "job_id": "test-job",
            "status": "completed",
            "items": [],
        }

    @staticmethod
    def write(path, content):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    @staticmethod
    def files(root):
        return {p.relative_to(root).as_posix(): p.read_bytes()
                for p in root.rglob("*") if p.is_file()}

    def save_job(self):
        self.job_file.write_text(json.dumps(self.job), encoding="utf-8")

    def filesystem_is_case_sensitive(self):
        probe = Path(self.tmp.name) / "case-sensitivity-probe"
        probe.mkdir()
        (probe / "CASE").write_bytes(b"probe")
        return not (probe / "case").exists()

    def add_zip(self, entries, target="lib/cus"):
        path = self.downloads / f"package-{len(self.job['items'])}.zip"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            for name, data in entries.items():
                archive.writestr(name, data)
        item = {
            "name": path.name,
            "type": "package",
            "target": target,
            "staged_path": str(path),
            "status": "downloaded",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "md5": hashlib.md5(path.read_bytes()).hexdigest(),
        }
        self.job["items"].append(item)
        self.save_job()
        return item

    @staticmethod
    def quiet_call(function, argument):
        with contextlib.redirect_stdout(io.StringIO()):
            return function(argument)

    def apply(self):
        self.save_job()
        self.quiet_call(apply_job, self.job_file)
        saved = json.loads(self.job_file.read_text(encoding="utf-8"))
        self.assertEqual(saved["status"], "applied")
        backup = Path(saved["backup_dir"])
        self.assertTrue((backup / "backup.json").is_file())
        return backup

    def assert_apply_rejected(self, save=True):
        if save:
            self.save_job()
        resources = self.home / "mservice-cosmic"
        before = self.files(resources)
        before_paths = {p.relative_to(resources) for p in resources.rglob("*")}
        backup_root = self.home / ".kddt-backups"
        before_backup = (backup_root.exists(),
                         {p.relative_to(backup_root) for p in backup_root.rglob("*")},
                         self.files(backup_root))
        with self.assertRaises(KddtError):
            self.quiet_call(apply_job, self.job_file)
        self.assertEqual(self.files(resources), before)
        self.assertEqual({p.relative_to(resources) for p in resources.rglob("*")},
                         before_paths)
        self.assertEqual((backup_root.exists(),
                          {p.relative_to(backup_root) for p in backup_root.rglob("*")},
                          self.files(backup_root)), before_backup)
        if self.job_file.is_file():
            saved = json.loads(self.job_file.read_text(encoding="utf-8"))
            self.assertNotEqual(saved.get("status"), "applied")
        self.assertFalse((self.home / "escape.jar").exists())
        self.assertFalse((self.home.parent / "escape.jar").exists())

    def assert_backup_preserved(self, backup, before):
        after = self.files(backup)
        for name, data in before.items():
            self.assertIn(name, after)
            self.assertEqual(after[name], data)

    def test_apply_and_rollback_restore_existing_and_remove_added_jar(self):
        before = self.files(self.cus)
        self.add_zip({"existing.jar": b"new-custom", "added.jar": b"added-custom"})
        backup = self.apply()
        self.assertEqual((self.cus / "existing.jar").read_bytes(), b"new-custom")
        self.assertEqual((self.cus / "added.jar").read_bytes(), b"added-custom")
        self.assertEqual((self.cus / "retained.jar").read_bytes(), b"retained-custom")
        backup_files = self.files(backup)
        self.quiet_call(rollback_backup, backup)
        self.assertEqual(self.files(self.cus), before)
        self.assert_backup_preserved(backup, backup_files)

    def test_legacy_libs_normalize_and_rollback_without_copying_control_dirs(self):
        before = self.files(self.cus)
        sentinel = self.home / ".kddt-backups" / "previous" / "sentinel.txt"
        self.write(sentinel, b"previous-backup")
        self.add_zip({
            "cosmic/apppackage-cosmic/cus/existing.jar": b"legacy-new",
            "cosmic/apppackage-cosmic/cus/added.jar": b"legacy-added",
        }, target="legacy-libs")
        backup = self.apply()
        self.assertEqual((self.cus / "existing.jar").read_bytes(), b"legacy-new")
        self.assertEqual((self.cus / "added.jar").read_bytes(), b"legacy-added")
        self.assertEqual(sentinel.read_bytes(), b"previous-backup")
        backup_files = self.files(backup)
        for name in backup_files:
            self.assertFalse({".kddt-backups", ".kddt-staging", ".kddt-cache"}
                             & set(Path(name).parts), name)
        self.quiet_call(rollback_backup, backup)
        self.assertEqual(self.files(self.cus), before)
        self.assert_backup_preserved(backup, backup_files)
        self.assertEqual(sentinel.read_bytes(), b"previous-backup")
        self.assertTrue(self.job_file.is_file())

    def test_changed_staged_digest_is_rejected_before_target_mutation(self):
        item = self.add_zip({"existing.jar": b"new-custom"})
        with zipfile.ZipFile(item["staged_path"], "a") as archive:
            archive.writestr("added.jar", b"changed-after-download")
        item["md5"] = hashlib.md5(Path(item["staged_path"]).read_bytes()).hexdigest()
        self.assert_apply_rejected()

    def test_zip_file_directory_conflict_rejected_before_backup_or_resource_change(self):
        sentinel = self.home / ".kddt-backups" / "previous" / "sentinel.txt"
        self.write(sentinel, b"previous-backup")
        self.add_zip({"same": b"file-content", "same/": b""})
        self.assert_apply_rejected()

    def test_case_alias_file_directory_obeys_target_filesystem(self):
        case_sensitive = self.filesystem_is_case_sensitive()
        before = self.files(self.cus)
        self.add_zip({"existing.jar": b"first-package-new"})
        self.add_zip({"fresh.jar": b"payload", "FRESH.jar/": b""})
        with self.subTest(case_sensitive=case_sensitive):
            if not case_sensitive:
                self.assert_apply_rejected()
                return
            backup = self.apply()
            self.assertEqual((self.cus / "existing.jar").read_bytes(), b"first-package-new")
            self.assertEqual((self.cus / "fresh.jar").read_bytes(), b"payload")
            self.assertTrue((self.cus / "FRESH.jar").is_dir())
            self.assertFalse((self.cus / "fresh.jar").samefile(self.cus / "FRESH.jar"))
            self.quiet_call(rollback_backup, backup)
            self.assertEqual(self.files(self.cus), before)

    def test_case_alias_duplicate_files_obey_target_filesystem(self):
        case_sensitive = self.filesystem_is_case_sensitive()
        before = self.files(self.cus)
        self.add_zip({"existing.jar": b"first-package-new"})
        self.add_zip({"other.jar": b"first-version", "OTHER.jar": b"second-version"})
        with self.subTest(case_sensitive=case_sensitive):
            if not case_sensitive:
                self.assert_apply_rejected()
                return
            backup = self.apply()
            self.assertEqual((self.cus / "existing.jar").read_bytes(), b"first-package-new")
            self.assertEqual((self.cus / "other.jar").read_bytes(), b"first-version")
            self.assertEqual((self.cus / "OTHER.jar").read_bytes(), b"second-version")
            self.assertFalse((self.cus / "other.jar").samefile(self.cus / "OTHER.jar"))
            self.quiet_call(rollback_backup, backup)
            self.assertEqual(self.files(self.cus), before)

    def test_existing_backups_case_alias_is_protected(self):
        if self.filesystem_is_case_sensitive():
            self.skipTest("case-alias protection requires a case-insensitive filesystem")
        sentinel = self.home / ".kddt-backups" / "previous" / "sentinel.txt"
        self.write(sentinel, b"previous-backup")
        self.add_zip({".KDDT-BACKUPS/poison": b"must-not-write"}, target="legacy-libs")
        self.assert_apply_rejected()
        self.assertEqual(sentinel.read_bytes(), b"previous-backup")
        self.assertFalse((self.home / ".KDDT-BACKUPS" / "poison").exists())

    def test_absent_cache_case_alias_is_protected(self):
        if self.filesystem_is_case_sensitive():
            self.skipTest("case-alias protection requires a case-insensitive filesystem")
        self.assertFalse((self.home / ".kddt-cache").exists())
        self.add_zip({".KDDT-CACHE/poison": b"must-not-write"}, target="legacy-libs")
        self.assert_apply_rejected()
        self.assertFalse((self.home / ".kddt-cache").exists())
        self.assertFalse((self.home / ".KDDT-CACHE").exists())
        self.assertFalse((self.home / ".KDDT-CACHE" / "poison").exists())

    def test_legacy_static_normalize_and_rollback_preserve_backup(self):
        static = self.home / "static-file-service"
        self.write(static / "index.html", b"old-index")
        self.write(static / "retained.css", b"retained-style")
        before = self.files(static)
        self.add_zip({
            "webapp/static-file-service/index.html": b"new-index",
            "webapp/static-file-service/added.css": b"new-style",
        }, target="legacy-static")
        backup = self.apply()
        self.assertEqual((static / "index.html").read_bytes(), b"new-index")
        self.assertEqual((static / "added.css").read_bytes(), b"new-style")
        self.assertEqual((static / "retained.css").read_bytes(), b"retained-style")
        backup_files = self.files(backup)
        self.quiet_call(rollback_backup, backup)
        self.assertEqual(self.files(static), before)
        self.assert_backup_preserved(backup, backup_files)

    def test_second_zip_unsafe_entry_does_not_install_first_zip(self):
        self.add_zip({"existing.jar": b"first-new", "first.jar": b"first"})
        self.add_zip({"../../../../escape.jar": b"unsafe"})
        self.assert_apply_rejected()

    def test_second_zip_bad_crc_does_not_install_first_zip(self):
        self.add_zip({"existing.jar": b"first-new", "first.jar": b"first"})
        item = self.add_zip({"second.jar": b"second-original"})
        path = Path(item["staged_path"])
        damaged = bytearray(path.read_bytes())
        name_length, extra_length = struct.unpack_from("<HH", damaged, 26)
        damaged[30 + name_length + extra_length] ^= 1
        path.write_bytes(damaged)
        item["sha256"] = hashlib.sha256(damaged).hexdigest()
        item["md5"] = hashlib.md5(damaged).hexdigest()
        with zipfile.ZipFile(path) as archive:
            self.assertEqual(archive.testzip(), "second.jar")
        self.assert_apply_rejected()

    def test_second_missing_zip_does_not_install_first_zip(self):
        self.add_zip({"existing.jar": b"first-new", "first.jar": b"first"})
        item = self.add_zip({"second.jar": b"second"})
        Path(item["staged_path"]).unlink()
        self.assert_apply_rejected()

    def test_missing_sha256_is_rejected(self):
        item = self.add_zip({"existing.jar": b"new-custom"})
        del item["sha256"]
        self.assert_apply_rejected()

    def test_missing_job_manifest_is_rejected(self):
        self.add_zip({"existing.jar": b"new-custom"})
        self.job_file.unlink()
        self.assert_apply_rejected(save=False)

    def test_missing_items_manifest_is_rejected(self):
        del self.job["items"]
        self.assert_apply_rejected()

    def test_empty_items_manifest_is_rejected(self):
        self.assert_apply_rejected()

    def test_missing_staged_zip_is_rejected(self):
        item = self.add_zip({"existing.jar": b"new-custom"})
        Path(item["staged_path"]).unlink()
        self.assert_apply_rejected()

    def test_md5_mismatch_is_rejected(self):
        item = self.add_zip({"existing.jar": b"new-custom"})
        item["md5"] = "0" * 32
        self.assert_apply_rejected()

    def test_missing_later_rollback_backup_preserves_all_current_targets(self):
        bos = self.home / "mservice-cosmic" / "lib" / "bos"
        self.write(bos / "platform.jar", b"old-platform")
        self.add_zip({"existing.jar": b"new-custom"})
        self.add_zip({"platform.jar": b"new-platform"}, target="lib/bos")
        backup = self.apply()
        manifest = json.loads((backup / "backup.json").read_text(encoding="utf-8"))
        components = manifest["components"]
        self.assertGreaterEqual(len(components), 2)
        last_backup = Path(components[-1]["backup"])
        self.assertTrue(components[-1]["existed"])
        if last_backup.is_dir():
            shutil.rmtree(last_backup)
        else:
            last_backup.unlink()
        current = self.files(self.home / "mservice-cosmic")
        with self.assertRaises(KddtError):
            self.quiet_call(rollback_backup, backup)
        self.assertEqual(self.files(self.home / "mservice-cosmic"), current)
        self.assertTrue((backup / "backup.json").is_file())
        self.assertFalse(list(self.home.rglob("*.rollback-replaced-*")))


if __name__ == "__main__":
    unittest.main()
