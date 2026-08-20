import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "script_runtime_real.py"
SPEC = importlib.util.spec_from_file_location("script_runtime_real", SCRIPT)
runtime = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(runtime)


class ScriptRuntimeCompatibilityTests(unittest.TestCase):
    def test_java8_uses_source_and_target_flags(self):
        self.assertEqual(["-source", "8", "-target", "8"], runtime.release_args(8))

    def test_newer_javac_uses_release_8(self):
        self.assertEqual(["--release", "8"], runtime.release_args(17))
        self.assertEqual(["--release", "8"], runtime.release_args(21))

    def test_cached_class_with_wrong_major_is_recompiled(self):
        with tempfile.TemporaryDirectory() as directory:
            classes = Path(directory) / "classes"
            main_class = classes / "local" / "iscb" / "runtime" / "ScriptRuntimeMain.class"
            main_class.parent.mkdir(parents=True)
            main_class.write_bytes(b"\xca\xfe\xba\xbe\x00\x00\x00\x45")
            with mock.patch.object(runtime, "RUNNER_CLASSES", classes):
                self.assertTrue(runtime.needs_compile())

    def test_java8_class_major_is_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            class_file = Path(directory) / "Runner.class"
            class_file.write_bytes(b"\xca\xfe\xba\xbe\x00\x00\x00\x34")
            self.assertEqual(52, runtime.class_major_version(class_file))


if __name__ == "__main__":
    unittest.main()
