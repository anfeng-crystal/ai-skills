import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


NORMALIZE = load_module("ui_normalize", SCRIPTS / "normalize_cases.py")
CONTRACT = load_module("ui_contract", SCRIPTS / "validate_execution_contract.py")
EVIDENCE = load_module("ui_evidence", SCRIPTS / "build_evidence_report.py")
FIXTURES = ROOT / "tests" / "fixtures"


class NormalizeCasesTest(unittest.TestCase):
    def test_csv_normalization_preserves_order(self):
        raw = NORMALIZE.cases_from_csv(FIXTURES / "safe_cases.csv")
        result = NORMALIZE.normalize(raw, "safe-smoke")
        self.assertEqual("UI-001", result["cases"][0]["caseId"])
        self.assertEqual([1, 2, 3], [step["order"] for step in result["cases"][0]["steps"]])
        self.assertTrue(all(not step["mutates"] for step in result["cases"][0]["steps"]))

    def test_safe_mode_rejects_mutation_and_credential_fields(self):
        with self.assertRaisesRegex(ValueError, "forbids"):
            NORMALIZE.normalize(
                [{"caseId": "x", "steps": [{"action": "save", "target": "form"}]}],
                "safe-smoke",
            )
        with self.assertRaisesRegex(ValueError, "credential/session"):
            NORMALIZE.normalize(
                [
                    {
                        "caseId": "x",
                        "password": "forbidden",
                        "steps": [{"action": "inspect", "target": "form"}],
                    }
                ],
                "generate",
            )
        with self.assertRaisesRegex(ValueError, "credential/session"):
            NORMALIZE.normalize(
                [
                    {
                        "caseId": "x",
                        "steps": [
                            {
                                "action": "input",
                                "target": "field",
                                "data": '{"token":"forbidden"}',
                            }
                        ],
                    }
                ],
                "generate",
            )

    def test_cli_accepts_utf8_and_paths_with_spaces(self):
        with tempfile.TemporaryDirectory(prefix="ui cases path ") as temp_name:
            temp = Path(temp_name)
            input_path = temp / "用例 input.csv"
            output_path = temp / "normalized output.json"
            input_path.write_bytes((FIXTURES / "safe_cases.csv").read_bytes())
            process = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "normalize_cases.py"),
                    "--input",
                    str(input_path),
                    "--mode",
                    "safe-smoke",
                    "--output",
                    str(output_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, process.returncode, process.stderr)
            self.assertEqual("UI-001", json.loads(output_path.read_text(encoding="utf-8"))["cases"][0]["caseId"])


class ContractTest(unittest.TestCase):
    def test_approved_crud_contract_covers_whole_task(self):
        contract = json.loads((FIXTURES / "approved_contract.json").read_text(encoding="utf-8"))
        result = CONTRACT.validate_contract(contract)
        self.assertTrue(result["valid"])
        self.assertFalse(result["perStepConfirmationRequired"])
        self.assertEqual(64, len(result["contractDigest"]))

    def test_safe_contract_rejects_write_and_prod_requires_approval(self):
        with self.assertRaisesRegex(ValueError, "write-capable"):
            CONTRACT.validate_contract(
                {
                    "taskId": "task-safe",
                    "mode": "safe-smoke",
                    "environmentClass": "dev-test",
                    "targetRef": "dev-a",
                    "caseIds": ["UI-001"],
                    "allowedActions": ["navigate", "save"],
                    "maxCases": 1,
                    "maxWrites": 0,
                }
            )

    def test_all_read_modes_and_approved_prod_mode_validate(self):
        generate = {
            "taskId": "task-generate",
            "mode": "generate",
            "environmentClass": "none",
            "targetRef": "",
            "caseIds": ["UI-GEN-001"],
            "allowedActions": [],
            "maxCases": 1,
            "maxWrites": 0,
        }
        safe = {
            "taskId": "task-safe",
            "mode": "safe-smoke",
            "environmentClass": "dev-test",
            "targetRef": "dev-a",
            "caseIds": ["UI-001"],
            "allowedActions": ["navigate", "click", "inspect"],
            "allowedClickEffects": ["navigation", "inspect"],
            "maxCases": 1,
            "maxWrites": 0,
        }
        prod_safe = {
            **safe,
            "taskId": "task-prod-safe",
            "mode": "prod-safe-smoke",
            "environmentClass": "prod",
            "targetRef": "prod-a",
            "approvalRef": "approval-prod-safe",
        }
        approved_prod = json.loads(
            (FIXTURES / "approved_contract.json").read_text(encoding="utf-8")
        )
        approved_prod.update(
            {
                "taskId": "task-prod-e2e",
                "mode": "approved-prod-e2e",
                "environmentClass": "prod",
                "targetRef": "prod-a",
                "approvalRef": "approval-prod-e2e",
            }
        )
        for contract in (generate, safe, prod_safe, approved_prod):
            self.assertTrue(CONTRACT.validate_contract(contract)["valid"])
        with self.assertRaisesRegex(ValueError, "approvalRef"):
            CONTRACT.validate_contract(
                {
                    "taskId": "task-prod",
                    "mode": "prod-safe-smoke",
                    "environmentClass": "prod",
                    "targetRef": "prod-a",
                    "caseIds": ["UI-001"],
                    "allowedActions": ["navigate", "inspect"],
                    "maxCases": 1,
                    "maxWrites": 0,
                }
            )


class EvidenceTest(unittest.TestCase):
    def test_report_exposes_missing_step_and_redacts_runtime_values(self):
        normalized = NORMALIZE.normalize(NORMALIZE.cases_from_csv(FIXTURES / "safe_cases.csv"), "safe-smoke")
        results = EVIDENCE.load_results(FIXTURES / "safe_results.jsonl")
        report = EVIDENCE.build_report(normalized, results)
        self.assertEqual(1, report["summary"]["statusCounts"]["not-run"])
        self.assertEqual(1, report["summary"]["statusCounts"]["passed"])
        self.assertEqual(1, report["summary"]["statusCounts"]["failed"])
        serialized = json.dumps(report, ensure_ascii=False)
        for secret in ("internal.example.invalid", "1001", "192.0.2.10", "demo-account"):
            self.assertNotIn(secret, serialized)


if __name__ == "__main__":
    unittest.main()
