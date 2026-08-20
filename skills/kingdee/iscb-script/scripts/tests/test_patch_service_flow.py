from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
SCRIPT = SCRIPTS / "patch_service_flow.py"
SPEC = importlib.util.spec_from_file_location("patch_service_flow", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def wrapped(value: dict) -> str:
    return f"({json.dumps(value, ensure_ascii=False, separators=(',', ':'))})"


def make_definition(top_script="return 1;", nested_script="return 2;"):
    subflow = {
        "nodes": {
            "s": {"id": "s", "type": "SubFlowStarter"},
            "q": {"id": "q", "type": "Script", "script": nested_script},
            "e": {"id": "e", "type": "End"},
        },
        "links": {
            "sq": {"source": "s", "target": "q"},
            "qe": {"source": "q", "target": "e"},
        },
    }
    return {
        "nodes": {
            "1": {"id": "1", "type": "ManualStarter"},
            "3": {"id": "3", "type": "Script", "script": top_script},
            "4": {"id": "4", "type": "Block", "subNode": wrapped(subflow)},
            "9": {"id": "9", "type": "End"},
        },
        "links": {
            "13": {"source": "1", "target": "3"},
            "34": {"source": "3", "target": "4"},
            "49": {"source": "4", "target": "9"},
        },
    }


def make_flow(number="flow_main", version="12", top_script="return 1;", nested_script="return 2;"):
    return {
        "$entityname": "isc_service_flow",
        "number": number,
        "version": version,
        "modifytime": "2026-08-01 10:00:00.000",
        "comment": "旧说明",
        "proc_digest": "保持不变",
        "resources": [{"res_alias": "DB1", "res_ref_id": "resource-id"}],
        "variables": [{"var_name": "count", "var_type_id": "integer"}],
        "define_json_tag": wrapped(make_definition(top_script, nested_script)),
    }


class PatchServiceFlowTests(unittest.TestCase):
    def create_case(self, directory: str, *, duplicate=False, version="12"):
        root = Path(directory)
        baseline = root / "baseline.dts"
        data_source = {
            "$entityname": "isc_data_source",
            "number": "DB1",
            "name": {"zh_CN": "连接"},
        }
        lines = [
            "\ufeff" + wrapped(data_source) + "\r\n",
            "\r\n",
            wrapped(make_flow(version=version)) + "\r\n",
        ]
        if duplicate:
            lines.append(wrapped(make_flow()) + "\r\n")
        baseline.write_text("".join(lines), encoding="utf-8", newline="")

        replacements = root / "replacements"
        replacements.mkdir()
        top_file = replacements / "top.iscb"
        nested_file = replacements / "nested.iscb"
        top_file.write_text("return 10;\n", encoding="utf-8", newline="")
        nested_file.write_text("return 20;\n", encoding="utf-8", newline="")

        manifest = {
            "schema_version": 1,
            "input_sha256": MODULE.file_sha256(baseline),
            "flow_number": "flow_main",
            "metadata": {
                "expected_version": version,
                "expected_modifytime": "2026-08-01 10:00:00.000",
                "expected_comment_sha256": MODULE.sha256_text("旧说明"),
                "new_modifytime": "2026-08-12 09:30:00.000",
                "comment_separator": " | ",
                "summary": "依据经验规则生成评审副本",
            },
            "changes": [
                {
                    "scope_path": [],
                    "node_id": "3",
                    "expected_script_sha256": MODULE.sha256_text("return 1;"),
                    "replacement_file": "replacements/top.iscb",
                    "replacement_sha256": MODULE.file_sha256(top_file),
                    "evidence_level": "bundle_runtime",
                    "experience_rules": ["EXP-COL-APPEND-001"],
                    "allow_sensitive_flags": [],
                },
                {
                    "scope_path": ["4"],
                    "node_id": "q",
                    "expected_script_sha256": MODULE.sha256_text("return 2;"),
                    "replacement_file": "replacements/nested.iscb",
                    "replacement_sha256": MODULE.file_sha256(nested_file),
                    "evidence_level": "experience_hypothesis",
                    "experience_rules": ["EXP-HTTP-001"],
                    "allow_sensitive_flags": [],
                },
            ],
        }
        manifest_path = root / "patch.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        return baseline, manifest_path, manifest, lines

    def read_output_flow(self, output: Path):
        raw = output.read_bytes()
        _, _, records = MODULE.parse_plain_dts(raw, output.name)
        flow = next(item["value"] for item in records if item["value"].get("$entityname") == "isc_service_flow")
        definition, _ = MODULE.unwrap_definition(flow["define_json_tag"], "flow")
        MODULE.expand_subflows(definition)
        return flow, definition

    def run_main(self, args):
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = MODULE.main(args)
        return result, stdout.getvalue(), stderr.getvalue()

    def write_manifest(self, path: Path, manifest: dict) -> None:
        path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    def rewrite_selected_flow(self, baseline: Path, transform) -> None:
        _, lines, records = MODULE.parse_plain_dts(baseline.read_bytes(), baseline.name)
        selected = next(
            record
            for record in records
            if record["value"].get("$entityname") == "isc_service_flow"
            and record["value"].get("number") == "flow_main"
        )
        flow = selected["value"]
        transform(flow)
        lines[selected["line_index"]] = MODULE.rebuild_target_line(
            lines[selected["line_index"]], flow
        )
        baseline.write_bytes("".join(lines).encode("utf-8"))

    def test_generate_patches_main_and_nested_scripts_with_preservation_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, _, original_lines = self.create_case(directory)
            output = Path(directory) / "review.dts"
            before = baseline.read_bytes()
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = MODULE.main(
                    [
                        "generate",
                        "--baseline", str(baseline),
                        "--manifest", str(manifest_path),
                        "--output", str(output),
                    ]
                )
            self.assertEqual(result, 0, stderr.getvalue())
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(baseline.read_bytes(), before)
            report = json.loads(stdout.getvalue())
            self.assertEqual(report["status"], "generated_review_copy_not_imported")
            self.assertTrue(report["requires_platform_validation"])
            self.assertTrue(report["input_snapshots_verified"])
            self.assertEqual(report["manifest_sha256"], MODULE.file_sha256(manifest_path))
            self.assertFalse(report["evidence_artifacts_verified"])
            self.assertEqual(
                report["declared_evidence_level_counts"],
                {"bundle_runtime": 1, "experience_hypothesis": 1},
            )
            self.assertEqual(report["unchanged_record_bytes"], {"unchanged": 1, "total": 2})
            self.assertEqual(len(report["changes"]), 2)
            self.assertEqual(
                [item["declared_evidence_level"] for item in report["changes"]],
                ["bundle_runtime", "experience_hypothesis"],
            )
            self.assertTrue(all(item["evidence_verified"] is False for item in report["changes"]))
            self.assertTrue(all("evidence_level" not in item for item in report["changes"]))
            self.assertNotIn("return 10", stdout.getvalue())
            self.assertNotIn("旧说明", stdout.getvalue())

            output_lines = output.read_bytes().decode("utf-8").splitlines(keepends=True)
            self.assertEqual(output_lines[0].encode("utf-8"), original_lines[0].encode("utf-8"))
            self.assertEqual(output_lines[1].encode("utf-8"), original_lines[1].encode("utf-8"))
            flow, definition = self.read_output_flow(output)
            self.assertEqual(flow["version"], "13")
            self.assertEqual(flow["modifytime"], "2026-08-12 09:30:00.000")
            self.assertEqual(flow["comment"], "旧说明 | 依据经验规则生成评审副本")
            self.assertEqual(flow["proc_digest"], "保持不变")
            self.assertEqual(definition["nodes"]["3"]["script"], "return 10;\n")
            self.assertEqual(definition["nodes"]["4"]["subNode"]["nodes"]["q"]["script"], "return 20;\n")

    def test_inspect_validates_without_writing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, _, _ = self.create_case(directory)
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                result = MODULE.main(
                    ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
                )
            self.assertEqual(result, 0)
            report = json.loads(stdout.getvalue())
            self.assertEqual(report["status"], "validated_patch_plan_not_generated")
            self.assertNotIn("output", report)

    def test_input_hash_drift_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, manifest, _ = self.create_case(directory)
            manifest["input_sha256"] = "0" * 64
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = MODULE.main(
                    ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
                )
            self.assertEqual(result, 1)
            self.assertEqual(json.loads(stderr.getvalue())["status"], "patch_refused")

    def test_duplicate_flow_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, manifest, _ = self.create_case(directory, duplicate=True)
            manifest["input_sha256"] = MODULE.file_sha256(baseline)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                result = MODULE.main(
                    ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
                )
            self.assertEqual(result, 1)

    def test_script_hash_drift_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, manifest, _ = self.create_case(directory)
            manifest["changes"][0]["expected_script_sha256"] = "f" * 64
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                result = MODULE.main(
                    ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
                )
            self.assertEqual(result, 1)

    def test_replacement_path_escape_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, manifest, _ = self.create_case(directory)
            outside = Path(directory).parent / "outside-review-script.iscb"
            outside.write_text("return 99;", encoding="utf-8")
            try:
                manifest["changes"][0]["replacement_file"] = "../outside-review-script.iscb"
                manifest["changes"][0]["replacement_sha256"] = MODULE.file_sha256(outside)
                manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
                with redirect_stderr(io.StringIO()):
                    result = MODULE.main(
                        ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
                    )
                self.assertEqual(result, 1)
            finally:
                outside.unlink(missing_ok=True)

    def test_credential_literal_replacement_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, manifest, _ = self.create_case(directory)
            replacement = Path(directory) / "replacements" / "top.iscb"
            replacement.write_text('var token = "literal-secret";\nreturn 10;\n', encoding="utf-8")
            manifest["changes"][0]["replacement_sha256"] = MODULE.file_sha256(replacement)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                result = MODULE.main(
                    ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
                )
            self.assertEqual(result, 1)

    def test_numeric_version_types_and_unsupported_semver(self):
        self.assertEqual(MODULE.increment_version(2), 3)
        self.assertEqual(MODULE.increment_version("2"), "3")
        self.assertEqual(MODULE.increment_version("002"), "003")
        for value in (True, 1.5, "1.2.0", None):
            with self.assertRaises(MODULE.PatchRefused):
                MODULE.increment_version(value)

    def test_output_conflicts_and_zip_are_refused_without_input_change(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, _, _ = self.create_case(directory)
            before = baseline.read_bytes()
            with redirect_stderr(io.StringIO()):
                result = MODULE.main(
                    [
                        "generate",
                        "--baseline", str(baseline),
                        "--manifest", str(manifest_path),
                        "--output", str(baseline),
                    ]
                )
            self.assertEqual(result, 1)
            self.assertEqual(baseline.read_bytes(), before)

            archive = Path(directory) / "baseline.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("baseline.dts", before)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["input_sha256"] = MODULE.file_sha256(archive)
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                result = MODULE.main(
                    ["inspect", "--baseline", str(archive), "--manifest", str(manifest_path)]
                )
            self.assertEqual(result, 1)

    def test_multiline_record_is_refused_by_patch_v1(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            flow = make_flow()
            baseline = root / "multiline.dts"
            baseline.write_text("(\n" + json.dumps(flow, ensure_ascii=False, indent=2) + "\n)\n", encoding="utf-8")
            replacements = root / "replacements"
            replacements.mkdir()
            replacement = replacements / "top.iscb"
            replacement.write_text("return 10;", encoding="utf-8")
            manifest = {
                "schema_version": 1,
                "input_sha256": MODULE.file_sha256(baseline),
                "flow_number": "flow_main",
                "metadata": {
                    "expected_version": "12",
                    "expected_modifytime": "2026-08-01 10:00:00.000",
                    "expected_comment_sha256": MODULE.sha256_text("旧说明"),
                    "new_modifytime": "2026-08-12 09:30:00.000",
                    "comment_separator": " | ",
                    "summary": "生成评审副本",
                },
                "changes": [
                    {
                        "scope_path": [],
                        "node_id": "3",
                        "expected_script_sha256": MODULE.sha256_text("return 1;"),
                        "replacement_file": "replacements/top.iscb",
                        "replacement_sha256": MODULE.file_sha256(replacement),
                        "evidence_level": "experience_hypothesis",
                        "experience_rules": ["EXP-OPT-AUTO-001"],
                        "allow_sensitive_flags": [],
                    }
                ],
            }
            manifest_path = root / "patch.json"
            manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
            with redirect_stderr(io.StringIO()):
                result = MODULE.main(
                    ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
                )
            self.assertEqual(result, 1)

    def test_baseline_manifest_and_replacement_snapshot_drift_are_refused(self):
        for drift_target in ("baseline", "manifest", "replacement"):
            with self.subTest(drift_target=drift_target), tempfile.TemporaryDirectory() as directory:
                baseline, manifest_path, _, _ = self.create_case(directory)
                replacement = Path(directory) / "replacements" / "top.iscb"
                target = {
                    "baseline": baseline,
                    "manifest": manifest_path,
                    "replacement": replacement,
                }[drift_target]
                original_verify = MODULE.verify_input_snapshots
                mutated = False

                def drift_then_verify(snapshots):
                    nonlocal mutated
                    if not mutated:
                        with target.open("ab") as handle:
                            handle.write(b" ")
                        mutated = True
                    return original_verify(snapshots)

                with mock.patch.object(
                    MODULE,
                    "verify_input_snapshots",
                    side_effect=drift_then_verify,
                ):
                    result, stdout, stderr = self.run_main(
                        ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
                    )
                self.assertEqual(result, 1)
                self.assertEqual(stdout, "")
                self.assertNotIn("Traceback", stderr)
                self.assertEqual(json.loads(stderr)["status"], "patch_refused")

    def test_snapshot_growth_is_rejected_before_hash_reread(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "replacement.iscb"
            path.write_bytes(b"x")
            snapshot = MODULE.FileSnapshot(
                "replacement_file",
                path,
                path.resolve(),
                MODULE.file_sha256(path),
                1,
                1,
            )
            path.write_bytes(b"x" * 1024)
            with mock.patch.object(MODULE, "bounded_file_sha256") as digest:
                with self.assertRaises(MODULE.PatchRefused):
                    MODULE.verify_file_snapshot(snapshot)
            digest.assert_not_called()

    def test_publish_time_baseline_drift_is_blocked_before_atomic_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, _, _ = self.create_case(directory)
            output = Path(directory) / "review.dts"
            original_verify = MODULE.verify_input_snapshots
            verify_calls = 0

            def drift_after_publish(snapshots):
                nonlocal verify_calls
                verify_calls += 1
                if verify_calls == 2:
                    with baseline.open("ab") as handle:
                        handle.write(b" ")
                return original_verify(snapshots)

            with mock.patch.object(
                MODULE,
                "verify_input_snapshots",
                side_effect=drift_after_publish,
            ):
                result, stdout, stderr = self.run_main(
                    [
                        "generate",
                        "--baseline", str(baseline),
                        "--manifest", str(manifest_path),
                        "--output", str(output),
                    ]
                )
            self.assertEqual(result, 1)
            self.assertEqual(stdout, "")
            self.assertNotIn("Traceback", stderr)
            self.assertFalse(output.exists())

    def test_no_clobber_publication_race_preserves_competing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, _, _ = self.create_case(directory)
            output = Path(directory) / "review.dts"

            def competing_rename(_source, destination):
                Path(destination).write_text("competing-output", encoding="utf-8")
                raise FileExistsError

            with mock.patch.object(
                MODULE,
                "rename_no_replace",
                side_effect=competing_rename,
            ):
                result, stdout, stderr = self.run_main(
                    [
                        "generate",
                        "--baseline", str(baseline),
                        "--manifest", str(manifest_path),
                        "--output", str(output),
                    ]
                )
            self.assertEqual(result, 1)
            self.assertEqual(stdout, "")
            self.assertNotIn("Traceback", stderr)
            self.assertEqual(output.read_text(encoding="utf-8"), "competing-output")
            self.assertEqual(list(Path(directory).glob(".review.dts.stage.*")), [])

    def test_duplicate_json_keys_are_refused_in_manifest_record_and_definition(self):
        for location in ("manifest", "record", "definition"):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as directory:
                baseline, manifest_path, manifest, _ = self.create_case(directory)
                if location == "manifest":
                    raw_manifest = manifest_path.read_text(encoding="utf-8")
                    raw_manifest = raw_manifest.replace(
                        '"flow_number": "flow_main"',
                        '"flow_number": "shadow", "flow_number": "flow_main"',
                        1,
                    )
                    manifest_path.write_text(raw_manifest, encoding="utf-8")
                elif location == "record":
                    raw_baseline = baseline.read_text(encoding="utf-8")
                    raw_baseline = raw_baseline.replace(
                        '"proc_digest":"保持不变"',
                        '"proc_digest":"shadow","proc_digest":"保持不变"',
                        1,
                    )
                    baseline.write_text(raw_baseline, encoding="utf-8", newline="")
                    manifest["input_sha256"] = MODULE.file_sha256(baseline)
                    self.write_manifest(manifest_path, manifest)
                else:
                    def duplicate_definition_key(flow):
                        definition = flow["define_json_tag"]
                        flow["define_json_tag"] = definition.replace(
                            '"links":',
                            '"links":{},"links":',
                            1,
                        )

                    self.rewrite_selected_flow(baseline, duplicate_definition_key)
                    manifest["input_sha256"] = MODULE.file_sha256(baseline)
                    self.write_manifest(manifest_path, manifest)

                result, stdout, stderr = self.run_main(
                    ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
                )
                self.assertEqual(result, 1)
                self.assertEqual(stdout, "")
                self.assertNotIn("Traceback", stderr)
                self.assertEqual(json.loads(stderr)["status"], "patch_refused")

    def test_top_level_single_object_array_is_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, manifest, _ = self.create_case(directory)
            lines = baseline.read_text(encoding="utf-8").splitlines(keepends=True)
            for index, line in enumerate(lines):
                if "isc_service_flow" not in line:
                    continue
                body, ending = MODULE.line_ending(line)
                token = body.strip()
                lines[index] = "([" + token[1:-1] + "])" + ending
            baseline.write_text("".join(lines), encoding="utf-8", newline="")
            manifest["input_sha256"] = MODULE.file_sha256(baseline)
            self.write_manifest(manifest_path, manifest)
            result, stdout, stderr = self.run_main(
                ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
            )
            self.assertEqual(result, 1)
            self.assertEqual(stdout, "")
            self.assertNotIn("Traceback", stderr)

    def test_define_json_pointer_uses_actual_definition_field(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, manifest, _ = self.create_case(directory)

            def use_define_json(flow):
                flow["define_json"] = flow.pop("define_json_tag")

            self.rewrite_selected_flow(baseline, use_define_json)
            manifest["input_sha256"] = MODULE.file_sha256(baseline)
            self.write_manifest(manifest_path, manifest)
            result, stdout, stderr = self.run_main(
                ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
            )
            self.assertEqual(result, 0, stderr)
            changes = json.loads(stdout)["changes"]
            self.assertEqual(
                [item["definition_field_pointer"] for item in changes],
                ["/define_json", "/define_json"],
            )
            self.assertEqual(
                [item["decoded_definition_pointer"] for item in changes],
                [
                    "/nodes/3/script",
                    "/nodes/4/subNode/nodes/q/script",
                ],
            )

    def test_node_object_ids_resolve_when_json_keys_differ_in_main_and_subflow(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, manifest, _ = self.create_case(directory)
            output = Path(directory) / "review.dts"

            def rename_node_keys(flow):
                definition, wrapped_definition = MODULE.unwrap_definition(
                    flow["define_json_tag"], "flow"
                )
                definition["nodes"]["top-key"] = definition["nodes"].pop("3")
                block = definition["nodes"].pop("4")
                definition["nodes"]["block-key"] = block
                subflow, wrapped_subflow = MODULE.unwrap_definition(block["subNode"], "subflow")
                subflow["nodes"]["nested-key"] = subflow["nodes"].pop("q")
                block["subNode"] = MODULE.serialize_definition(subflow, wrapped_subflow)
                flow["define_json_tag"] = MODULE.serialize_definition(
                    definition, wrapped_definition
                )

            self.rewrite_selected_flow(baseline, rename_node_keys)
            manifest["input_sha256"] = MODULE.file_sha256(baseline)
            self.write_manifest(manifest_path, manifest)
            result, stdout, stderr = self.run_main(
                [
                    "generate",
                    "--baseline", str(baseline),
                    "--manifest", str(manifest_path),
                    "--output", str(output),
                ]
            )
            self.assertEqual(result, 0, stderr)
            report = json.loads(stdout)
            self.assertEqual(
                [item["decoded_definition_pointer"] for item in report["changes"]],
                [
                    "/nodes/top-key/script",
                    "/nodes/block-key/subNode/nodes/nested-key/script",
                ],
            )
            _, definition = self.read_output_flow(output)
            self.assertEqual(definition["nodes"]["top-key"]["script"], "return 10;\n")
            self.assertEqual(
                definition["nodes"]["block-key"]["subNode"]["nodes"]["nested-key"]["script"],
                "return 20;\n",
            )

    def test_malicious_manifest_values_are_refused_without_leak_or_traceback(self):
        cases = (
            ("unknown_field", lambda manifest: manifest.__setitem__("token=SUPERSECRET", True)),
            (
                "comment_separator",
                lambda manifest: manifest["metadata"].__setitem__("comment_separator", "pwd=x"),
            ),
            (
                "evidence_type",
                lambda manifest: manifest["changes"][0].__setitem__("evidence_level", []),
            ),
            ("schema_bool", lambda manifest: manifest.__setitem__("schema_version", True)),
            (
                "nul_path",
                lambda manifest: manifest["changes"][0].__setitem__(
                    "replacement_file", "bad\x00path.iscb"
                ),
            ),
            (
                "unknown_experience_rule",
                lambda manifest: manifest["changes"][0].__setitem__(
                    "experience_rules", ["EXP-UNKNOWN-SECRET-001"]
                ),
            ),
            (
                "hypothesis_without_rule",
                lambda manifest: manifest["changes"][1].__setitem__(
                    "experience_rules", []
                ),
            ),
            (
                "invalid_modifytime",
                lambda manifest: manifest["metadata"].__setitem__(
                    "new_modifytime", "2026-99-99 99:99:99.999"
                ),
            ),
        )
        for name, mutate in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                baseline, manifest_path, manifest, _ = self.create_case(directory)
                mutate(manifest)
                self.write_manifest(manifest_path, manifest)
                result, stdout, stderr = self.run_main(
                    ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
                )
                self.assertEqual(result, 1)
                self.assertEqual(stdout, "")
                self.assertNotIn("Traceback", stderr)
                self.assertNotIn("SUPERSECRET", stderr)
                self.assertNotIn("pwd=x", stderr)
                self.assertEqual(json.loads(stderr)["status"], "patch_refused")

    def test_deep_manifest_is_refused_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, manifest, _ = self.create_case(directory)
            raw = json.dumps(manifest, ensure_ascii=False)
            raw = raw[:-1] + ', "deep":' + "[" * 300000 + "0" + "]" * 300000 + "}"
            manifest_path.write_text(raw, encoding="utf-8")
            result, stdout, stderr = self.run_main(
                ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
            )
            self.assertEqual(result, 1)
            self.assertEqual(stdout, "")
            self.assertNotIn("Traceback", stderr)
            self.assertEqual(json.loads(stderr)["status"], "patch_refused")

    def test_sensitive_node_id_is_redacted_from_nested_parse_error(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, manifest, _ = self.create_case(directory)

            def make_sensitive_invalid_subflow(flow):
                definition, wrapped_definition = MODULE.unwrap_definition(
                    flow["define_json_tag"], "flow"
                )
                block = definition["nodes"]["4"]
                block["id"] = "host=SECRET.INTERNAL"
                block["subNode"] = "({broken})"
                flow["define_json_tag"] = MODULE.serialize_definition(
                    definition, wrapped_definition
                )

            self.rewrite_selected_flow(baseline, make_sensitive_invalid_subflow)
            manifest["input_sha256"] = MODULE.file_sha256(baseline)
            self.write_manifest(manifest_path, manifest)
            result, stdout, stderr = self.run_main(
                ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
            )
            self.assertEqual(result, 1)
            self.assertEqual(stdout, "")
            self.assertNotIn("SECRET.INTERNAL", stderr)
            self.assertNotIn("Traceback", stderr)

    def test_change_count_and_cumulative_replacement_limits_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, manifest, _ = self.create_case(directory)
            manifest["changes"] = [
                dict(manifest["changes"][0])
                for _ in range(MODULE.MAX_CHANGES + 1)
            ]
            self.write_manifest(manifest_path, manifest)
            result, stdout, stderr = self.run_main(
                ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
            )
            self.assertEqual(result, 1)
            self.assertEqual(stdout, "")
            self.assertIn("supported limit", json.loads(stderr)["message"])

        with tempfile.TemporaryDirectory() as directory:
            baseline, manifest_path, _, _ = self.create_case(directory)
            replacement_bytes = sum(
                len((Path(directory) / "replacements" / name).read_bytes())
                for name in ("top.iscb", "nested.iscb")
            )
            with mock.patch.object(
                MODULE,
                "MAX_TOTAL_REPLACEMENT_BYTES",
                replacement_bytes - 1,
            ):
                result, stdout, stderr = self.run_main(
                    ["inspect", "--baseline", str(baseline), "--manifest", str(manifest_path)]
                )
            self.assertEqual(result, 1)
            self.assertEqual(stdout, "")
            self.assertIn("cumulative size limit", json.loads(stderr)["message"])


if __name__ == "__main__":
    unittest.main()
