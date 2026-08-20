import importlib.util
import io
import json
import os
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "analyze_service_flow.py"
SPEC = importlib.util.spec_from_file_location("analyze_service_flow", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def wrapped(value):
    return f"({json.dumps(value, ensure_ascii=False)})"


def flow_record(number="flow_main", definition=None, **extra):
    if definition is None:
        definition = {
            "nodes": {
                "start": {"id": "start", "type": "ManualStarter", "title": "开始"},
                "script": {
                    "id": "script",
                    "type": "Script",
                    "title": "处理",
                    "script": 'var token = "secret-value";\nreturn {"define_json_tag": "{}"};',
                },
                "end": {"id": "end", "type": "End", "title": "结束"},
            },
            "links": {
                "l1": {"source": "start", "target": "script"},
                "l2": {"source": "script", "target": "end", "condition": "private-condition"},
            },
        }
    value = {
        "$entityname": "isc_service_flow",
        "number": number,
        "name": {"zh_CN": "测试流程"},
        "variables": [
            {"var_name": "access_token", "var_type_id": "string", "default_value": "secret-default"},
            {"var_name": "count", "var_type_id": "integer", "default_value": 0},
        ],
        "proc_digest": "完成 #{count}",
        "define_json_tag": f"({json.dumps(definition, ensure_ascii=False)})",
    }
    value.update(extra)
    return value


class AnalyzeServiceFlowTests(unittest.TestCase):
    def write_text(self, directory, name, text):
        path = Path(directory) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_multiline_records_and_sensitive_values_are_not_emitted(self):
        with tempfile.TemporaryDirectory() as directory:
            data_source = {"$entityname": "isc_data_source", "number": "DS1"}
            text = "\n".join(
                [
                    "(\n" + json.dumps(data_source, ensure_ascii=False, indent=2) + "\n)",
                    "(\n" + json.dumps(flow_record(), ensure_ascii=False, indent=2) + "\n)",
                ]
            )
            path = self.write_text(directory, "multi.dts", text)
            before = path.read_bytes()
            report, scripts = MODULE.inspect_path(path, "flow_main")

            self.assertEqual(report["record_count"], 2)
            self.assertEqual(report["entity_counts"]["isc_service_flow"], 1)
            self.assertEqual(report["flows"][0]["summary"]["node_count"], 3)
            self.assertEqual(report["flows"][0]["summary"]["link_count"], 2)
            self.assertEqual(report["flows"][0]["summary"]["script_count"], 1)
            self.assertEqual(report["scripts"][0]["lines"], 2)
            self.assertEqual(report["scripts"][0]["scope_node_ids"], [])
            self.assertIn("credential_literal", report["scripts"][0]["sensitive_flags"])
            serialized = json.dumps(report, ensure_ascii=False)
            self.assertNotIn("secret-value", serialized)
            self.assertNotIn("secret-default", serialized)
            self.assertNotIn("private-condition", serialized)
            self.assertNotIn("_content", serialized)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(len(scripts), 1)

    def test_nested_subflow_and_real_links_are_preserved(self):
        subflow = {
            "nodes": {
                "s": {"id": "s", "type": "SubFlowStarter", "title": "子开始"},
                "e": {"id": "e", "type": "End", "title": "子结束"},
            },
            "links": [{"id": "sub-link", "source": "s", "target": "e"}],
        }
        definition = {
            "nodes": {
                "start": {"type": "ManualStarter"},
                "block": {"type": "Block", "title": "子流程", "subNode": json.dumps(subflow)},
                "end": {"type": "End"},
            },
            "links": {"l": {"source": "start", "target": "block"}},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "nested.dts", wrapped(flow_record(definition=definition)))
            report, _ = MODULE.inspect_path(path, "flow_main")
            flow = report["flows"][0]
            self.assertEqual(flow["summary"]["scope_count"], 2)
            self.assertEqual(flow["summary"]["node_count"], 5)
            self.assertEqual(flow["root_scope"]["children"][0]["link_count"], 1)
            diagram = MODULE.mermaid_report(report)
            self.assertEqual(diagram.count("-->"), 2)
            self.assertNotIn("private-condition", diagram)

    def test_script_metadata_exposes_public_scope_node_ids_for_patcher(self):
        subflow = {
            "nodes": {
                "nested-key": {"id": "nested-script-id", "type": "Script", "script": "return 2;"}
            },
            "links": {},
        }
        definition = {
            "nodes": {
                "block-key": {"id": "block-id", "type": "Block", "subNode": json.dumps(subflow)}
            },
            "links": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "scope-ids.dts", wrapped(flow_record(definition=definition)))
            report, _ = MODULE.inspect_path(path, "flow_main")
            script = report["scripts"][0]
            self.assertEqual(script["scope_node_ids"], ["block-id"])
            self.assertEqual(script["node_id"], "nested-script-id")

    def test_dangling_link_and_unreachable_node_are_reported(self):
        definition = {
            "nodes": {
                "start": {"type": "ManualStarter"},
                "orphan": {"type": "Script", "script": "return 1;"},
                "end": {"type": "End"},
            },
            "links": {
                "bad": {"source": "start", "target": "missing"},
                "ok": {"source": "start", "target": "end"},
            },
        }
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "broken.dts", wrapped(flow_record(definition=definition)))
            report, _ = MODULE.inspect_path(path, "flow_main")
            codes = {item["code"] for item in report["diagnostics"]}
            self.assertIn("DANGLING_LINK", codes)
            self.assertIn("UNREACHABLE_NODE", codes)
            self.assertEqual(report["status"], "error")

    def test_duplicate_flow_selection_is_not_auto_resolved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(
                directory,
                "duplicate.dts",
                wrapped(flow_record()) + "\n" + wrapped(flow_record(modifytime="2099-01-01")),
            )
            report, scripts = MODULE.inspect_path(path, "flow_main")
            self.assertEqual(report["selection"]["status"], "ambiguous")
            self.assertEqual(report["flows"], [])
            self.assertEqual(scripts, [])
            codes = {item["code"] for item in report["diagnostics"]}
            self.assertIn("DUPLICATE_FLOW_NUMBER", codes)
            self.assertIn("FLOW_SELECTION_AMBIGUOUS", codes)

            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = MODULE.main([str(path), "--flow", "flow_main"])
            self.assertEqual(result, 1)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(json.loads(stdout.getvalue())["selection"]["status"], "ambiguous")

    def test_bad_definition_is_reported_without_fabricated_topology(self):
        with tempfile.TemporaryDirectory() as directory:
            broken = flow_record()
            broken["define_json_tag"] = "({broken})"
            path = self.write_text(directory, "bad.dts", wrapped(broken))
            report, _ = MODULE.inspect_path(path)
            self.assertEqual(report["flows"][0]["definition_status"], "invalid")
            self.assertIsNone(report["flows"][0]["root_scope"])
            self.assertIn("INVALID_FLOW_DEFINITION", {item["code"] for item in report["diagnostics"]})

    def test_duplicate_key_in_top_level_record_fails_closed_without_leaking_content(self):
        duplicate_key = "top-level-duplicate-secret-key"
        first_value = "top-level-first-secret-value"
        second_value = "top-level-second-secret-value"
        definition = json.dumps({"nodes": {}, "links": {}}, ensure_ascii=False)
        payload = (
            "({"
            '"$entityname":"isc_service_flow",'
            '"number":"flow_main",'
            f'{json.dumps(duplicate_key)}:{json.dumps(first_value)},'
            f'{json.dumps(duplicate_key)}:{json.dumps(second_value)},'
            f'"define_json_tag":{json.dumps(f"({definition})", ensure_ascii=False)}'
            "})"
        )

        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "duplicate-top-level.dts", payload)
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = MODULE.main([str(path), "--flow", "flow_main"])

            emitted = stdout.getvalue() + stderr.getvalue()
            self.assertEqual(result, 2)
            self.assertEqual(stdout.getvalue(), "")
            self.assertTrue(stderr.getvalue().startswith("ERROR "))
            self.assertIn("duplicate JSON object key", stderr.getvalue())
            self.assertNotIn("Traceback", emitted)
            for secret in (duplicate_key, first_value, second_value):
                self.assertNotIn(secret, emitted)

    def test_duplicate_key_in_stringified_definition_is_a_redacted_json_diagnostic(self):
        duplicate_key = "definition-duplicate-secret-key"
        first_value = "definition-first-secret-value"
        second_value = "definition-second-secret-value"
        duplicate_definition = (
            "({"
            '"nodes":{},'
            '"links":{},'
            f'{json.dumps(duplicate_key)}:{json.dumps(first_value)},'
            f'{json.dumps(duplicate_key)}:{json.dumps(second_value)}'
            "})"
        )
        record = flow_record()
        record["define_json_tag"] = duplicate_definition

        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "duplicate-definition.dts", wrapped(record))
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = MODULE.main([str(path), "--flow", "flow_main"])

            report = json.loads(stdout.getvalue())
            serialized = json.dumps(report, ensure_ascii=False)
            findings = [
                item for item in report["diagnostics"]
                if item["code"] == "INVALID_FLOW_DEFINITION"
            ]
            self.assertEqual(result, 1)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["message"], "duplicate JSON object key is not allowed")
            self.assertEqual(report["flows"][0]["definition_status"], "invalid")
            self.assertIsNone(report["flows"][0]["root_scope"])
            self.assertNotIn("Traceback", serialized)
            for secret in (duplicate_key, first_value, second_value):
                self.assertNotIn(secret, serialized)

    def test_duplicate_key_in_stringified_subflow_is_a_redacted_json_diagnostic(self):
        duplicate_key = "subflow-duplicate-secret-key"
        first_value = "subflow-first-secret-value"
        second_value = "subflow-second-secret-value"
        duplicate_subflow = (
            "({"
            '"nodes":{},'
            '"links":{},'
            f'{json.dumps(duplicate_key)}:{json.dumps(first_value)},'
            f'{json.dumps(duplicate_key)}:{json.dumps(second_value)}'
            "})"
        )
        definition = {
            "nodes": {
                "start": {"type": "ManualStarter"},
                "block": {"type": "Block", "subNode": duplicate_subflow},
                "end": {"type": "End"},
            },
            "links": {
                "to-block": {"source": "start", "target": "block"},
                "to-end": {"source": "block", "target": "end"},
            },
        }

        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(
                directory,
                "duplicate-subflow.dts",
                wrapped(flow_record(definition=definition)),
            )
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = MODULE.main([str(path), "--flow", "flow_main"])

            report = json.loads(stdout.getvalue())
            serialized = json.dumps(report, ensure_ascii=False)
            findings = [
                item for item in report["diagnostics"]
                if item["code"] == "INVALID_SUBFLOW"
            ]
            self.assertEqual(result, 1)
            self.assertEqual(stderr.getvalue(), "")
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["message"], "duplicate JSON object key is not allowed")
            self.assertNotIn("Traceback", serialized)
            for secret in (duplicate_key, first_value, second_value):
                self.assertNotIn(secret, serialized)

    def test_nonfinite_json_constants_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            record = flow_record()
            record["enable"] = float("nan")
            path = self.write_text(directory, "nan.dts", wrapped(record))
            with self.assertRaises(MODULE.InspectionError):
                MODULE.inspect_path(path)
        with self.assertRaises(MODULE.InspectionError):
            MODULE.parse_dts_records('{"overflow":1e999}', "overflow.dts")
        deeply_nested = '{"deep":' + "[" * 300000 + "0" + "]" * 300000 + "}"
        with self.assertRaises(MODULE.InspectionError):
            MODULE.parse_dts_records(deeply_nested, "deep.dts")

    def test_explicit_script_extraction_sanitizes_paths_and_refuses_overwrite(self):
        definition = {
            "nodes": {
                "start": {"type": "ManualStarter"},
                "../escape": {"type": "Script", "title": "../../outside", "script": "return 1;"},
                "end": {"type": "End"},
            },
            "links": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "paths.dts", wrapped(flow_record(number="../flow", definition=definition)))
            _, scripts = MODULE.inspect_path(path)
            output = Path(directory) / "scripts"
            written = MODULE.extract_scripts(scripts, output, overwrite=False)
            self.assertEqual(len(written), 1)
            self.assertEqual(len(list(output.iterdir())), 1)
            self.assertEqual(next(output.iterdir()).resolve().parent, output.resolve())
            with self.assertRaises(MODULE.InspectionError):
                MODULE.extract_scripts(scripts, output, overwrite=False)
            protected = next(output.iterdir())
            with self.assertRaises(MODULE.InspectionError):
                MODULE.extract_scripts(
                    scripts,
                    output,
                    overwrite=True,
                    protected_paths=[protected],
                )

    def test_no_overwrite_atomic_write_preserves_competing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"

            def competing_link(_source, destination):
                Path(destination).write_text("competing", encoding="utf-8")
                raise FileExistsError

            with mock.patch.object(MODULE.os, "link", side_effect=competing_link):
                with self.assertRaises(MODULE.InspectionError):
                    MODULE.write_output(output, "ours", overwrite=False)
            self.assertEqual(output.read_text(encoding="utf-8"), "competing")

    def test_zip_input_and_cli_default_stdout_are_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "flows.zip"
            payload = wrapped(flow_record()).encode("utf-8")
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("nested/flow.dts", payload)
            before = archive_path.read_bytes()
            stdout = io.StringIO()
            stderr = io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = MODULE.main([str(archive_path), "--flow", "flow_main"])
            self.assertEqual(result, 0)
            self.assertEqual(stderr.getvalue(), "")
            parsed = json.loads(stdout.getvalue())
            self.assertEqual(parsed["inputs"][0]["source"], "flows.zip!member-1:flow.dts")
            self.assertFalse(parsed["input_modified"])
            self.assertEqual(archive_path.read_bytes(), before)

    def test_multi_member_zip_is_sorted_and_source_locations_are_unique(self):
        with tempfile.TemporaryDirectory() as directory:
            archive_path = Path(directory) / "multi.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("b/flow.dts", wrapped(flow_record(number="flow_b")))
                archive.writestr("a/flow.dts", wrapped(flow_record(number="flow_a")))
            report, _ = MODULE.inspect_path(archive_path)
            self.assertEqual(report["record_count"], 2)
            self.assertEqual(
                [item["source"] for item in report["inputs"]],
                ["multi.zip!member-1:flow.dts", "multi.zip!member-2:flow.dts"],
            )
            self.assertEqual(len({item["record_location"] for item in report["flows"]}), 2)

    def test_input_size_and_zip_member_limits_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "large.dts", wrapped(flow_record()))
            with self.assertRaises(MODULE.InspectionError):
                MODULE.inspect_path(path, max_input_bytes=1)

            archive_path = Path(directory) / "many.zip"
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr("a.dts", wrapped(flow_record(number="a")))
                archive.writestr("b.dts", wrapped(flow_record(number="b")))
            with self.assertRaises(MODULE.InspectionError):
                MODULE.inspect_path(archive_path, max_zip_members=1)

    def test_container_metadata_is_not_stringified_or_leaked(self):
        definition = {
            "nodes": {
                "safe": {
                    "id": {"password": "node-leak"},
                    "type": ["Script", {"secret": "type-leak"}],
                    "script": "return 1;",
                }
            },
            "links": {
                "edge": {
                    "id": {"token": "link-leak"},
                    "source": {"id": {"secret": "source-leak"}},
                    "target": "safe",
                }
            },
        }
        record = flow_record(definition=definition)
        record["resources"] = [
            {
                "res_alias": {"password": "resource-leak"},
                "res_type": ["jdbc", {"secret": "resource-type-leak"}],
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "containers.dts", wrapped(record))
            report, _ = MODULE.inspect_path(path)
            serialized = json.dumps(report, ensure_ascii=False)
            self.assertNotIn("-leak", serialized)
            codes = {item["code"] for item in report["diagnostics"]}
            self.assertIn("INVALID_NODE_ID", codes)
            self.assertIn("INVALID_RESOURCE_METADATA", codes)

    def test_deep_subflow_returns_diagnostic_instead_of_crashing(self):
        nested = {"nodes": {}, "links": {}}
        for index in range(34, -1, -1):
            nested = {
                "nodes": {
                    str(index): {
                        "id": str(index),
                        "type": "Block",
                        "subNode": nested,
                    }
                },
                "links": {},
            }
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "deep.dts", wrapped(flow_record(definition=nested)))
            report, _ = MODULE.inspect_path(path)
            self.assertIn("SUBFLOW_DEPTH", {item["code"] for item in report["diagnostics"]})
            self.assertEqual(report["status"], "error")

    def test_keyed_variables_satisfy_digest_references(self):
        record = flow_record()
        record["variables"] = {"count": {"type": "integer"}}
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "variables.dts", wrapped(record))
            report, _ = MODULE.inspect_path(path)
            self.assertEqual(report["flows"][0]["variables"][0]["name"], "count")
            self.assertNotIn(
                "DIGEST_VARIABLE_UNDEFINED",
                {item["code"] for item in report["diagnostics"]},
            )

    def test_empty_links_report_unreachable_non_starter_nodes(self):
        definition = {
            "nodes": {
                "start": {"type": "ManualStarter"},
                "script": {"type": "Script", "script": "return 1;"},
                "end": {"type": "End"},
            },
            "links": {},
        }
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "disconnected.dts", wrapped(flow_record(definition=definition)))
            report, _ = MODULE.inspect_path(path)
            unreachable = [
                item for item in report["diagnostics"]
                if item["code"] == "UNREACHABLE_NODE"
            ]
            self.assertEqual(len(unreachable), 2)

    def test_report_hardlink_to_input_is_rejected_without_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "input.dts", wrapped(flow_record()))
            report_path = Path(directory) / "report.json"
            os.link(path, report_path)
            before = path.read_bytes()
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = MODULE.main(
                    [str(path), "--flow", "flow_main", "--output", str(report_path), "--overwrite"]
                )
            self.assertEqual(result, 2)
            self.assertNotIn("Traceback", stderr.getvalue())
            self.assertEqual(path.read_bytes(), before)

    def test_report_overwrite_replaces_unrelated_hardlink_without_touching_victim(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "input.dts", wrapped(flow_record()))
            victim = self.write_text(directory, "victim.txt", "keep-victim")
            report_path = Path(directory) / "report.json"
            os.link(victim, report_path)
            result = MODULE.main(
                [str(path), "--flow", "flow_main", "--output", str(report_path), "--overwrite"]
            )
            self.assertEqual(result, 0)
            self.assertEqual(victim.read_text(encoding="utf-8"), "keep-victim")
            self.assertFalse(os.path.samefile(victim, report_path))
            self.assertEqual(json.loads(report_path.read_text(encoding="utf-8"))["status"], "pass_with_findings")

    def test_report_dangling_symlink_requires_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "input.dts", wrapped(flow_record()))
            report_path = Path(directory) / "report.json"
            report_path.symlink_to("missing.json")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = MODULE.main(
                    [str(path), "--flow", "flow_main", "--output", str(report_path)]
                )
            self.assertEqual(result, 2)
            self.assertTrue(report_path.is_symlink())
            self.assertFalse((Path(directory) / "missing.json").exists())

    def test_script_hardlink_to_input_is_rejected_without_modification(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "input.dts", wrapped(flow_record()))
            _, scripts = MODULE.inspect_path(path, "flow_main")
            output = Path(directory) / "scripts"
            prepared = MODULE.prepare_script_outputs(scripts, output, overwrite=True)
            output.mkdir()
            os.link(path, prepared[0][0])
            before = path.read_bytes()
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = MODULE.main(
                    [
                        str(path),
                        "--flow", "flow_main",
                        "--extract-scripts", str(output),
                        "--overwrite",
                    ]
                )
            self.assertEqual(result, 2)
            self.assertNotIn("Traceback", stderr.getvalue())
            self.assertEqual(path.read_bytes(), before)

    def test_script_overwrite_replaces_unrelated_hardlink_without_touching_victim(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "input.dts", wrapped(flow_record()))
            _, scripts = MODULE.inspect_path(path, "flow_main")
            output = Path(directory) / "scripts"
            prepared = MODULE.prepare_script_outputs(scripts, output, overwrite=True)
            output.mkdir()
            victim = self.write_text(directory, "victim.txt", "keep-victim")
            os.link(victim, prepared[0][0])
            with redirect_stdout(io.StringIO()):
                result = MODULE.main(
                    [
                        str(path),
                        "--flow", "flow_main",
                        "--extract-scripts", str(output),
                        "--overwrite",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(victim.read_text(encoding="utf-8"), "keep-victim")
            self.assertFalse(os.path.samefile(victim, prepared[0][0]))
            self.assertEqual(prepared[0][0].read_text(encoding="utf-8"), scripts[0]["_content"])

    def test_script_overwrite_replaces_same_directory_symlink_without_touching_victim(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "input.dts", wrapped(flow_record()))
            _, scripts = MODULE.inspect_path(path, "flow_main")
            output = Path(directory) / "scripts"
            prepared = MODULE.prepare_script_outputs(scripts, output, overwrite=True)
            output.mkdir()
            victim = self.write_text(output, "victim.txt", "keep-victim")
            prepared[0][0].symlink_to(victim.name)
            with redirect_stdout(io.StringIO()):
                result = MODULE.main(
                    [
                        str(path),
                        "--flow", "flow_main",
                        "--extract-scripts", str(output),
                        "--overwrite",
                    ]
                )
            self.assertEqual(result, 0)
            self.assertEqual(victim.read_text(encoding="utf-8"), "keep-victim")
            self.assertFalse(prepared[0][0].is_symlink())
            self.assertEqual(prepared[0][0].read_text(encoding="utf-8"), scripts[0]["_content"])

    def test_script_dangling_symlink_requires_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "input.dts", wrapped(flow_record()))
            _, scripts = MODULE.inspect_path(path, "flow_main")
            output = Path(directory) / "scripts"
            prepared = MODULE.prepare_script_outputs(scripts, output, overwrite=True)
            output.mkdir()
            prepared[0][0].symlink_to("missing.iscb")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = MODULE.main(
                    [
                        str(path),
                        "--flow", "flow_main",
                        "--extract-scripts", str(output),
                    ]
                )
            self.assertEqual(result, 2)
            self.assertTrue(prepared[0][0].is_symlink())
            self.assertFalse((output / "missing.iscb").exists())

    def test_report_conflict_causes_no_partial_script_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "input.dts", wrapped(flow_record()))
            report_path = self.write_text(directory, "existing.json", "keep")
            output = Path(directory) / "scripts"
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                result = MODULE.main(
                    [
                        str(path),
                        "--flow", "flow_main",
                        "--extract-scripts", str(output),
                        "--output", str(report_path),
                    ]
                )
            self.assertEqual(result, 2)
            self.assertFalse(output.exists())
            self.assertEqual(report_path.read_text(encoding="utf-8"), "keep")

    def test_markdown_and_mermaid_escape_untrusted_titles(self):
        definition = {
            "nodes": {
                "start": {"type": "ManualStarter", "title": "<img src=x>"},
                "end": {"type": "End", "title": "![remote](https://example.invalid/x)"},
            },
            "links": {"edge": {"source": "start", "target": "end"}},
        }
        record = flow_record(definition=definition)
        record["name"] = {"zh_CN": "<script>alert(1)</script>"}
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_text(directory, "markup.dts", wrapped(record))
            report, _ = MODULE.inspect_path(path)
            markdown = MODULE.markdown_report(report)
            mermaid = MODULE.mermaid_report(report)
            self.assertNotIn("<script>", markdown)
            self.assertNotIn("<img", markdown)
            self.assertNotIn("![remote]", markdown)
            self.assertNotIn("<script>", mermaid)
            self.assertNotIn("<img", mermaid)


if __name__ == "__main__":
    unittest.main()
