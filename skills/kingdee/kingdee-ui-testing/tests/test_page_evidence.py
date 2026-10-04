"""Page evidence contract regressions; no browser or business requests."""

import copy
import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import normalize_cases as normalize
import build_evidence_report as report

EXPECTED = {"formId": "sample_list", "pageType": "list", "pageElement": "status"}
OBSERVED = {**EXPECTED, "route": "/sample/list"}


def cases(page=EXPECTED):
    step = {"stepId": "check", "action": "assert", "target": "status", "expected": "可见"}
    if page is not None:
        step["page"] = copy.deepcopy(page)
    return [{"caseId": "PAGE-1", "steps": [step]}]


def result(page=OBSERVED, status="passed"):
    value = {"caseId": "PAGE-1", "stepId": "check", "status": status, "actual": "可见"}
    if page is not None:
        value["page"] = copy.deepcopy(page)
    return value


def build(raw_cases, results):
    return report.build_report(normalize.normalize(raw_cases, "safe-smoke"), results)


class PageEvidenceTest(unittest.TestCase):
    def test_correct_page_preserves_expected_actual_and_raw_status(self):
        normalized = normalize.normalize(cases(), "safe-smoke")
        self.assertEqual(EXPECTED, normalized["cases"][0]["steps"][0]["page"])
        output = report.build_report(normalized, [result(status="PASSED")])
        step = output["cases"][0]["steps"][0]
        self.assertEqual(EXPECTED, step["page"])
        self.assertEqual(OBSERVED, step["evidence"]["page"])
        self.assertEqual("PASSED", step["rawStatus"])
        self.assertEqual("matched", step["pageCheck"]["status"])
        self.assertEqual(1, output["summary"]["pagePassedCount"])

    def test_wrong_identity_cannot_pass(self):
        for field, value in (("formId", "sample_detail"), ("pageType", "detail"), ("pageElement", "other")):
            with self.subTest(field=field):
                output = build(cases(), [result({**OBSERVED, field: value})])
                step = output["cases"][0]["steps"][0]
                self.assertEqual("blocked", step["status"])
                self.assertEqual("blocked_wrong_page", step["blockReason"])
                self.assertEqual("passed", step["rawStatus"])
                self.assertEqual(0, output["summary"]["statusCounts"]["passed"])

    def test_missing_page_or_required_field_cannot_pass(self):
        for observed in (None, {}, *(dict((k, v) for k, v in OBSERVED.items() if k != key) for key in OBSERVED)):
            with self.subTest(observed=observed):
                step = build(cases(), [result(observed)])["cases"][0]["steps"][0]
                self.assertEqual("blocked", step["status"])
                self.assertEqual("blocked_missing_page_evidence", step["blockReason"])

    def test_malformed_observations_are_missing_without_crash(self):
        for observed in ("list", [], 1, {**OBSERVED, "route": " "}, {**OBSERVED, "formId": 12},
                         {**OBSERVED, "pageType": False}, {**OBSERVED, "pageElement": ["status"]}):
            with self.subTest(observed=observed):
                step = build(cases(), [result(observed)])["cases"][0]["steps"][0]
                self.assertEqual("blocked", step["status"])
                self.assertEqual("missing", step["pageCheck"]["status"])

    def test_explicit_wrong_identity_takes_precedence_over_missing_route(self):
        step = build(cases(), [result({**EXPECTED, "formId": "other"})])["cases"][0]["steps"][0]
        self.assertEqual("blocked_wrong_page", step["blockReason"])
        self.assertEqual(["route"], step["pageCheck"]["missingFields"])
        self.assertEqual(["formId"], step["pageCheck"]["mismatchedFields"])

    def test_nonpassing_states_and_missing_result_are_preserved(self):
        for status in ("failed", "blocked", "skipped", "not-run"):
            with self.subTest(status=status):
                step = build(cases(), [result({**OBSERVED, "formId": "other"}, status)])["cases"][0]["steps"][0]
                self.assertEqual(status, step["status"])
                self.assertEqual(status, step["rawStatus"])
                self.assertEqual("wrong_page", step["pageCheck"]["status"])
        step = build(cases(), [])["cases"][0]["steps"][0]
        self.assertEqual("not-run", step["status"])
        self.assertIsNone(step["rawStatus"])

    def test_navigation_and_nonpage_assertion_do_not_claim_page_verification(self):
        for action in ("navigate", "assert", "wait"):
            raw = cases(None)
            raw[0]["steps"][0]["action"] = action
            output = build(raw, [result(None)])
            step = output["cases"][0]["steps"][0]
            self.assertEqual("passed", step["status"])
            self.assertEqual("not-requested", step["pageCheck"]["status"])
            self.assertNotIn("page", step)
            self.assertEqual(0, output["summary"]["pagePassedCount"])

    def test_route_redaction_applies_to_matched_orphan_and_nested_evidence(self):
        for route in (
            "https://fake-login:fake-password@internal.invalid/sample/list?phone=13800138000&code=opaque#private-fragment",
            "//internal.invalid/sample/list?%74oken=encoded-secret#private-fragment",
            "/sample/list?accountId=demo-account&mobile=13800138000#private-fragment",
            "https://internal.invalid?code=opaque",
        ):
            with self.subTest(route=route):
                item = result({**OBSERVED, "route": route})
                item["before"] = {"route": route, "token": "nested-secret"}
                orphan = {**item, "stepId": "orphan"}
                output = build(cases(), [item, orphan])
                serialized = json.dumps(output)
                for secret in ("internal.invalid", "fake-login", "fake-password", "13800138000", "opaque",
                               "encoded-secret", "demo-account", "private-fragment", "nested-secret"):
                    self.assertNotIn(secret, serialized)
                self.assertEqual(1, output["summary"]["pagePassedCount"])
                self.assertEqual(1, output["summary"]["unexpectedResultCount"])

    def test_redaction_does_not_hide_identity_mismatch_before_comparison(self):
        expected = {**EXPECTED, "pageElement": "accountId=expected"}
        actual = {**OBSERVED, "pageElement": "accountId=other"}
        step = build(cases(expected), [result(actual)])["cases"][0]["steps"][0]
        self.assertEqual(step["page"]["pageElement"], step["evidence"]["page"]["pageElement"])
        self.assertEqual("blocked_wrong_page", step["blockReason"])

    def test_invalid_route_shapes_do_not_leak_query_values(self):
        sensitive_route = "https://private.invalid/path?phone=13800000000"
        for route in ([sensitive_route], {"value": sensitive_route}, None, 123):
            with self.subTest(route=route):
                item = result({**OBSERVED, "route": route})
                item["after"] = {"route": route}
                output = build(cases(), [item, {**item, "stepId": "orphan"}])
                step = output["cases"][0]["steps"][0]
                self.assertEqual("blocked", step["status"])
                self.assertEqual(["route"], step["pageCheck"]["missingFields"])
                self.assertEqual("[INVALID_ROUTE]", step["evidence"]["page"]["route"])
                self.assertNotIn("13800000000", json.dumps(output))

    def test_normalizer_and_report_reject_invalid_expectation(self):
        for page in ({}, "list", 1, {**EXPECTED, "route": "/list"}, {**EXPECTED, "formId": " "},
                     {**EXPECTED, "pageElement": 1}, {**EXPECTED, "pageType": "unknown"}):
            with self.subTest(page=page):
                with self.assertRaises(ValueError):
                    normalize.normalize(cases(page), "safe-smoke")
                normalized = normalize.normalize(cases(), "safe-smoke")
                normalized["cases"][0]["steps"][0]["page"] = page
                with self.assertRaises(ValueError):
                    report.build_report(normalized, [result()])


class PageCliTest(unittest.TestCase):
    def run_cli(self, script, *args):
        return subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / script), *map(str, args)],
                              capture_output=True, text=True, check=False)

    def write_csv(self, path, page=EXPECTED):
        fields = ["case_id", "step_id", "action", "target", "expected",
                  "page_form_id", "page_type", "page_element"]
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerow({"case_id": "PAGE-1", "step_id": "check", "action": "assert",
                             "target": "status", "expected": "可见", "page_form_id": page.get("formId", ""),
                             "page_type": page.get("pageType", ""), "page_element": page.get("pageElement", "")})

    def test_csv_json_cli_roundtrip_and_report_outputs(self):
        with tempfile.TemporaryDirectory(prefix="页面 evidence ") as temp:
            directory = Path(temp)
            source, normalized_path = directory / "用例 input.csv", directory / "normalized cases.json"
            self.write_csv(source)
            first = self.run_cli("normalize_cases.py", "--input", source, "--mode", "safe-smoke", "--output", normalized_path)
            self.assertEqual(0, first.returncode, first.stderr)
            self.assertEqual("", first.stdout)
            second = self.run_cli("normalize_cases.py", "--input", normalized_path, "--mode", "safe-smoke")
            self.assertEqual(0, second.returncode, second.stderr)
            normalized = json.loads(second.stdout)
            self.assertEqual(normalize.normalize(cases(), "safe-smoke"), normalized)
            results_path = directory / "results.jsonl"
            results_path.write_text(json.dumps(result(), ensure_ascii=False) + "\n", encoding="utf-8")
            out = self.run_cli("build_evidence_report.py", "--cases", normalized_path, "--results", results_path)
            self.assertEqual(0, out.returncode, out.stderr)
            self.assertEqual(1, json.loads(out.stdout)["summary"]["pagePassedCount"])
            output_path = directory / "output report.json"
            args = ("--cases", normalized_path, "--results", results_path, "--output", output_path)
            written = self.run_cli("build_evidence_report.py", *args)
            self.assertEqual(0, written.returncode, written.stderr)
            self.assertEqual("", written.stdout)
            self.assertEqual(json.loads(out.stdout), json.loads(output_path.read_text(encoding="utf-8")))
            blocked = self.run_cli("build_evidence_report.py", *args)
            self.assertEqual(2, blocked.returncode)
            forced = self.run_cli("build_evidence_report.py", *args, "--force")
            self.assertEqual(0, forced.returncode, forced.stderr)
            protected = self.run_cli("build_evidence_report.py", "--cases", normalized_path,
                                     "--results", results_path, "--output", results_path, "--force")
            self.assertEqual(2, protected.returncode)
            self.assertEqual(result(), json.loads(results_path.read_text(encoding="utf-8")))

    def test_partial_csv_page_rejected_and_empty_columns_omitted(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "input.csv"
            self.write_csv(path, {"formId": "sample_list"})
            process = self.run_cli("normalize_cases.py", "--input", path, "--mode", "generate")
            self.assertEqual(2, process.returncode)
            self.assertEqual("", process.stdout)
            self.write_csv(path, {})
            normalized = normalize.normalize(normalize.cases_from_csv(path), "generate")
            self.assertNotIn("page", normalized["cases"][0]["steps"][0])

    def test_result_formats_duplicates_and_contract_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            for name, data in (("array.json", [result()]), ("object.json", {"results": [result()]})):
                path = directory / name
                path.write_text(json.dumps(data), encoding="utf-8")
                self.assertEqual([result()], report.load_results(path))
        normalized = normalize.normalize(cases(), "safe-smoke")
        with self.assertRaisesRegex(ValueError, "duplicate result"):
            report.build_report(normalized, [result(), result()])
        contract = json.loads((ROOT / "tests/fixtures/approved_contract.json").read_text(encoding="utf-8"))
        output = report.build_report(normalized, [result()], contract)
        self.assertEqual(64, len(output["contract"]["contractDigest"]))
        self.assertFalse(output["contract"]["perStepConfirmationRequired"])
        with self.assertRaises(ValueError):
            report.build_report(normalized, [result()], {**contract, "maxWrites": 0})


if __name__ == "__main__":
    unittest.main()
