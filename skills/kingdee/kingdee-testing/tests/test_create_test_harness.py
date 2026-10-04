#!/usr/bin/env python3
"""Offline output-boundary tests for the harness generator."""
import errno
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL = Path(__file__).resolve().parents[1]
SCRIPT = SKILL / 'scripts/create_test_harness.py'
SOURCE = SKILL / 'assets/java-test-harness'
TEMPLATES = sorted(path.relative_to(SOURCE) for path in SOURCE.rglob('*') if path.is_file())


def file_state(root):
    """Record regular files and links, without following directory links."""
    state = {}
    for directory, folders, files in os.walk(root, followlinks=False):
        for name in folders + files:
            path = Path(directory) / name
            relative = str(path.relative_to(root))
            if path.is_symlink():
                state[relative] = ['symlink', os.readlink(path)]
            elif path.is_file():
                state[relative] = ['file', hashlib.sha256(path.read_bytes()).hexdigest()]
    return state


class HarnessOutputContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='kingdee-harness-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / 'output'

    def make_symlink(self, link, target, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except NotImplementedError as error:
            self.skipTest(f'symbolic links are unavailable: {error}')
        except OSError as error:
            if error.errno in {errno.EPERM, errno.EACCES, errno.ENOSYS, errno.ENOTSUP} or getattr(error, 'winerror', None) == 1314:
                self.skipTest(f'symbolic link creation is unavailable: {error}')
            raise

    def run_cli(self, output=None, force=False):
        command = [sys.executable, str(SCRIPT), '--output', str(output or self.output), '--json']
        if force:
            command.append('--force')
        return subprocess.run(command, text=True, capture_output=True)

    def assert_rejected_without_file_changes(self, force):
        before = file_state(self.root)
        result = self.run_cli(force=force)
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(before, file_state(self.root), 'preflight failure changed a regular file or link')
        self.assertTrue(result.stderr.strip(), 'rejection needs a diagnostic')

    def test_normal_generation(self):
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['copied'], [str(path) for path in TEMPLATES])
        self.assertEqual(report['skipped'], [])
        for relative in TEMPLATES:
            self.assertEqual((SOURCE / relative).read_bytes(), (self.output / relative).read_bytes())

    def test_default_skips_existing_regular_file(self):
        target = self.output / TEMPLATES[-1]
        target.parent.mkdir(parents=True)
        target.write_bytes(b'existing user content\n')
        result = self.run_cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['skipped'], [str(TEMPLATES[-1])])
        self.assertEqual(target.read_bytes(), b'existing user content\n')
        for relative in TEMPLATES[:-1]:
            self.assertEqual((SOURCE / relative).read_bytes(), (self.output / relative).read_bytes())

    def test_force_overwrites_existing_regular_file(self):
        target = self.output / TEMPLATES[-1]
        target.parent.mkdir(parents=True)
        target.write_bytes(b'existing user content\n')
        result = self.run_cli(force=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['skipped'], [])
        for relative in TEMPLATES:
            self.assertEqual((SOURCE / relative).read_bytes(), (self.output / relative).read_bytes())

    def test_directory_symlink_rejected_even_when_internal(self):
        for force in (False, True):
            with self.subTest(force=force):
                self.output.mkdir(exist_ok=True)
                internal = self.output / 'linked-directory'
                internal.mkdir(exist_ok=True)
                link = self.output / 'src'
                if not link.is_symlink():
                    self.make_symlink(link, internal, directory=True)
                self.assert_rejected_without_file_changes(force)

    def test_directory_symlink_cannot_write_outside_output(self):
        self.output.mkdir()
        outside = self.root / 'outside-output'
        outside.mkdir()
        self.make_symlink(self.output / 'src', outside, directory=True)
        for force in (False, True):
            with self.subTest(force=force):
                self.assert_rejected_without_file_changes(force)

    def test_file_symlink_rejected_before_earlier_templates_are_written(self):
        target = self.output / TEMPLATES[-1]
        target.parent.mkdir(parents=True)
        outside = self.root / 'existing-external-file'
        outside.write_bytes(b'preserve outside file\n')
        self.make_symlink(target, outside)
        for force in (False, True):
            with self.subTest(force=force):
                self.assert_rejected_without_file_changes(force)

    def test_dangling_file_symlink_rejected_before_any_copy(self):
        target = self.output / TEMPLATES[-1]
        target.parent.mkdir(parents=True)
        self.make_symlink(target, self.root / 'missing-external-file')
        for force in (False, True):
            with self.subTest(force=force):
                self.assert_rejected_without_file_changes(force)

    def test_target_directory_conflict_rejected_before_any_copy(self):
        (self.output / TEMPLATES[-1]).mkdir(parents=True)
        for force in (False, True):
            with self.subTest(force=force):
                self.assert_rejected_without_file_changes(force)

    def test_ancestor_regular_file_conflict_rejected(self):
        self.output.mkdir()
        (self.output / 'src').write_bytes(b'ancestor is a regular file\n')
        for force in (False, True):
            with self.subTest(force=force):
                self.assert_rejected_without_file_changes(force)

    def test_explicit_output_root_symlink_keeps_resolve_semantics(self):
        self.output.mkdir()
        root_link = self.root / 'explicit-root-link'
        self.make_symlink(root_link, self.output, directory=True)
        result = self.run_cli(output=root_link)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['output'], str(self.output.resolve()))
        for relative in TEMPLATES:
            self.assertEqual((SOURCE / relative).read_bytes(), (self.output / relative).read_bytes())


if __name__ == '__main__':
    unittest.main(verbosity=2)
