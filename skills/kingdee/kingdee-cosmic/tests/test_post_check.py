import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
POST_CHECK = SKILL_ROOT / "scripts" / "cosmic-post-check.py"
ASSETS = SKILL_ROOT / "assets"


class PostCheckSubprocessTest(unittest.TestCase):
    def run_post_check(self, target: Path, *args: str, env=None):
        process_env = os.environ.copy()
        process_env.pop("OK_COSMIC_KNOWLEDGE_DB", None)
        if env:
            process_env.update(env)
        return subprocess.run(
            [sys.executable, str(POST_CHECK), str(target), *args],
            check=False,
            capture_output=True,
            text=True,
            env=process_env,
        )

    def make_gradle_project(self, base: Path, source: str, gradle_exit: int = 0):
        project = base / "fake gradle project"
        target = project / "app" / "src" / "main" / "java" / "Demo.java"
        target.parent.mkdir(parents=True)
        target.write_text(source, encoding="utf-8")
        (project / "build.gradle").write_text("", encoding="utf-8")
        (project / "settings.gradle").write_text(
            "include 'app'\n", encoding="utf-8"
        )
        (project / "gradle.properties").write_text(
            "sourceCompatibility=1.8\n", encoding="utf-8"
        )

        gradlew = project / "gradlew"
        gradlew.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$@\" > gradle-invocation.txt\n"
            f"exit {gradle_exit}\n",
            encoding="utf-8",
        )
        gradlew.chmod(0o644)

        java_home = base / "fake jdk"
        java_home.mkdir()
        (java_home / "release").write_text(
            'JAVA_VERSION="1.8.0_402"\n', encoding="utf-8"
        )
        return project, target, gradlew, java_home

    def test_json_stdout_is_standalone_without_gradle(self):
        with tempfile.TemporaryDirectory(prefix="cosmic post check ") as temp_name:
            target = Path(temp_name) / "Demo.java"
            target.write_text("public class Demo {}\n", encoding="utf-8")

            process = self.run_post_check(target, "--json")

            report = json.loads(process.stdout)
            self.assertEqual(0, process.returncode, process.stderr)
            self.assertTrue(report["summary"]["passed"])
            self.assertNotIn("使用 post-lint", process.stdout)
            self.assertIn("使用 post-lint", process.stderr)

    def test_gradle_success_continues_lint_and_preserves_wrapper_mode(self):
        source = """\
public class Demo {
    void readMetadata() {
        int t_meta_forbidden = 1;
    }
}
"""
        with tempfile.TemporaryDirectory(prefix="cosmic post check ") as temp_name:
            project, target, gradlew, java_home = self.make_gradle_project(
                Path(temp_name), source
            )
            before_mode = stat.S_IMODE(gradlew.stat().st_mode)

            process = self.run_post_check(
                target, "--json", env={"JAVA_HOME": str(java_home)}
            )

            report = json.loads(process.stdout)
            invocation = (project / "gradle-invocation.txt").read_text(
                encoding="utf-8"
            )
            self.assertEqual(1, process.returncode)
            self.assertFalse(report["summary"]["passed"])
            self.assertIn("SCENE-009", {i["rule_id"] for i in report["issues"]})
            self.assertIn(":app:compileJava", invocation)
            self.assertIn("--console=plain", invocation)
            self.assertEqual(before_mode, stat.S_IMODE(gradlew.stat().st_mode))
            self.assertEqual(0o644, stat.S_IMODE(gradlew.stat().st_mode))

    def test_gradle_failure_returns_json_and_skips_lint(self):
        with tempfile.TemporaryDirectory(prefix="cosmic post check ") as temp_name:
            _, target, _, java_home = self.make_gradle_project(
                Path(temp_name), "public class Demo {}\n", gradle_exit=7
            )

            process = self.run_post_check(
                target, "--json", env={"JAVA_HOME": str(java_home)}
            )

            report = json.loads(process.stdout)
            self.assertEqual(7, process.returncode)
            self.assertFalse(report["summary"]["passed"])
            self.assertEqual("gradle", report["post_check"]["stage"])
            self.assertNotIn("使用 post-lint", process.stderr)

    def test_ast_scene_checks_work_through_installed_tree_sitter_api(self):
        source = """\
public class Demo extends AbstractFormPlugin implements ClickListener {
    @Override
    public void registerListener() {
        super.registerListener();
    }

    @Override
    public void afterBindData() {
    }
}
"""
        with tempfile.TemporaryDirectory(prefix="cosmic post check ") as temp_name:
            target = Path(temp_name) / "Demo.java"
            target.write_text(source, encoding="utf-8")

            process = self.run_post_check(target, "--json")

            report = json.loads(process.stdout)
            rule_ids = {issue["rule_id"] for issue in report["issues"]}
            self.assertEqual(0, process.returncode, process.stderr)
            self.assertIn("SCENE-005", rule_ids)
            self.assertIn("SCENE-011", rule_ids)

    def test_bundled_assets_have_no_error_level_findings(self):
        process = self.run_post_check(ASSETS, "--json")

        report = json.loads(process.stdout)
        self.assertEqual(0, process.returncode, process.stderr)
        self.assertTrue(report["summary"]["passed"])
        self.assertEqual(0, report["summary"]["errors"])

    def test_algo_context_owns_dataset_lifecycle_but_unscoped_dataset_fails(self):
        safe_source = """\
public class Demo {
    void scoped() {
        try (AlgoContext ignored = Algo.newContext()) {
            DataSet ds = loadDataSet();
            mayFail();
        }
    }
}
"""
        unsafe_source = """\
public class Demo {
    void leaking() {
        DataSet ds = loadDataSet();
        mayFail();
    }
}
"""
        with tempfile.TemporaryDirectory(prefix="cosmic dataset context ") as temp_name:
            safe_target = Path(temp_name) / "Safe.java"
            unsafe_target = Path(temp_name) / "Unsafe.java"
            safe_target.write_text(safe_source, encoding="utf-8")
            unsafe_target.write_text(unsafe_source, encoding="utf-8")

            safe_process = self.run_post_check(safe_target, "--json")
            unsafe_process = self.run_post_check(unsafe_target, "--json")

            safe_report = json.loads(safe_process.stdout)
            unsafe_report = json.loads(unsafe_process.stdout)
            self.assertEqual(0, safe_process.returncode, safe_process.stderr)
            self.assertNotIn(
                "RESOURCE-004", {i["rule_id"] for i in safe_report["issues"]}
            )
            self.assertEqual(1, unsafe_process.returncode)
            self.assertIn(
                "RESOURCE-004", {i["rule_id"] for i in unsafe_report["issues"]}
            )

    def test_keyset_page_query_is_allowed_but_uncursored_loop_query_fails(self):
        safe_source = """\
public class Demo {
    void scan(int pageSize) {
        if (pageSize <= 0) {
            return;
        }
        long lastId = 0L;
        while (true) {
            QFilter filter = new QFilter("status", QCP.equals, "A")
                    .and("id", QCP.large_than, lastId);
            DynamicObjectCollection page = QueryServiceHelper.query(
                    "sample", "id", filter.toArray(), "id asc", pageSize);
            if (page.isEmpty()) {
                break;
            }
            lastId = page.get(page.size() - 1).getLong("id");
        }
    }
}
"""
        unguarded_source = safe_source.replace(
            "        if (pageSize <= 0) {\n"
            "            return;\n"
            "        }\n",
            "",
        )
        unsafe_source = """\
public class Demo {
    void scan(int pageSize) {
        while (true) {
            DynamicObjectCollection page = QueryServiceHelper.query(
                    "sample", "id", null, "id asc", pageSize);
            if (page.isEmpty()) {
                break;
            }
        }
    }
}
"""
        with tempfile.TemporaryDirectory(prefix="cosmic keyset query ") as temp_name:
            safe_target = Path(temp_name) / "Safe.java"
            unguarded_target = Path(temp_name) / "Unguarded.java"
            unsafe_target = Path(temp_name) / "Unsafe.java"
            safe_target.write_text(safe_source, encoding="utf-8")
            unguarded_target.write_text(unguarded_source, encoding="utf-8")
            unsafe_target.write_text(unsafe_source, encoding="utf-8")

            safe_process = self.run_post_check(safe_target, "--json")
            unguarded_process = self.run_post_check(unguarded_target, "--json")
            unsafe_process = self.run_post_check(unsafe_target, "--json")

            safe_report = json.loads(safe_process.stdout)
            unguarded_report = json.loads(unguarded_process.stdout)
            unsafe_report = json.loads(unsafe_process.stdout)
            self.assertEqual(0, safe_process.returncode, safe_process.stderr)
            self.assertNotIn(
                "STYLE-015", {i["rule_id"] for i in safe_report["issues"]}
            )
            self.assertEqual(1, unguarded_process.returncode)
            self.assertIn(
                "STYLE-015", {i["rule_id"] for i in unguarded_report["issues"]}
            )
            self.assertEqual(1, unsafe_process.returncode)
            self.assertIn(
                "STYLE-015", {i["rule_id"] for i in unsafe_report["issues"]}
            )


if __name__ == "__main__":
    unittest.main()
