import contextlib
import importlib.util
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'run_gradle_tests.py'
spec = importlib.util.spec_from_file_location('gradle_runner', SCRIPT)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class GradleSummaryTest(unittest.TestCase):
    def invoke(self, project, exit_code=0, dry_run=False):
        output = io.StringIO()
        argv = [str(SCRIPT), '--project', str(project), '--json']
        if dry_run:
            argv.append('--dry-run')
        with mock.patch.object(sys, 'argv', argv), contextlib.redirect_stdout(output):
            with mock.patch.object(runner.subprocess, 'run') as process:
                process.return_value.returncode = exit_code
                code = runner.main()
        return code, json.loads(output.getvalue()), process

    def test_execution_status_matches_process_result(self):
        with tempfile.TemporaryDirectory(prefix='gradle summary ') as folder:
            project = Path(folder)
            (project / 'gradlew').touch()
            for exit_code in (0, 7):
                with self.subTest(exit_code=exit_code):
                    code, result, process = self.invoke(project, exit_code)
                    self.assertEqual(exit_code, code)
                    self.assertEqual(exit_code, result['returncode'])
                    self.assertEqual(exit_code == 0, result['ok'])
                    process.assert_called_once()

    def test_dry_run_is_precheck_only(self):
        with tempfile.TemporaryDirectory(prefix='gradle summary ') as folder:
            project = Path(folder)
            (project / 'gradlew').touch()
            code, result, process = self.invoke(project, dry_run=True)
            self.assertEqual(0, code)
            self.assertTrue(result['ok'])
            self.assertTrue(result['dryRun'])
            self.assertNotIn('returncode', result)
            process.assert_not_called()

    def test_missing_wrapper_is_unsuccessful_without_execution(self):
        with tempfile.TemporaryDirectory(prefix='gradle summary ') as folder:
            with mock.patch.object(runner, 'find_gradlew', return_value=None):
                code, result, process = self.invoke(Path(folder))
            self.assertEqual(2, code)
            self.assertFalse(result['ok'])
            process.assert_not_called()


if __name__ == '__main__':
    unittest.main()
