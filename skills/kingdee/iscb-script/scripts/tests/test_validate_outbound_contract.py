from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "validate_outbound_contract.py"


class ValidateOutboundContractTest(unittest.TestCase):
    def run_validator(self, contract: dict, payload: dict, provenance: dict) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paths = {}
            for name, value in (("contract", contract), ("payload", payload), ("provenance", provenance)):
                path = root / f"{name}.json"
                path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
                paths[name] = path
            return subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--contract", str(paths["contract"]),
                    "--payload", str(paths["payload"]),
                    "--provenance", str(paths["provenance"]),
                    "--require-real-provenance",
                ],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_accepts_exact_types_semantics_and_real_sources(self) -> None:
        result = self.run_validator(
            contract(),
            {"TrackingUnit": "ORG-001", "Province": "浙江省", "Span": 1.5},
            provenance(),
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["status"], "pass")

    def test_rejects_wrong_code_semantics_invented_values_and_stale_types(self) -> None:
        evidence = provenance()
        evidence["fields"]["TrackingUnit"] = {
            "kind": "placeholder",
            "semantic_type": "administrative_org_number",
            "source": "invented test value",
        }
        result = self.run_validator(
            contract(),
            {"TrackingUnit": "10090000", "Province": "浙江省", "Span": "1.5", "OldField": "stale"},
            evidence,
        )
        self.assertEqual(result.returncode, 1, result.stdout)
        codes = {(item["field"], item["code"]) for item in json.loads(result.stdout)["errors"]}
        self.assertIn(("TrackingUnit", "non_real_provenance"), codes)
        self.assertIn(("TrackingUnit", "semantic_type_mismatch"), codes)
        self.assertIn(("Span", "json_type_mismatch"), codes)
        self.assertIn(("OldField", "unexpected_field"), codes)


def contract() -> dict:
    return {
        "version": 1,
        "allow_extra": False,
        "fields": {
            "TrackingUnit": {
                "required": True,
                "json_type": "string",
                "semantic_type": "unified_identity_code",
                "source_policy": "real",
            },
            "Province": {
                "required": True,
                "json_type": "string",
                "semantic_type": "text",
                "source_policy": "real",
            },
            "Span": {
                "required": True,
                "json_type": "number",
                "semantic_type": "numeric",
                "source_policy": "real",
            },
        },
    }


def provenance() -> dict:
    return {
        "fields": {
            "TrackingUnit": {
                "kind": "production_master_data",
                "semantic_type": "unified_identity_code",
                "source": "verified organization relation",
            },
            "Province": {
                "kind": "production_record",
                "semantic_type": "text",
                "source": "business record",
            },
            "Span": {
                "kind": "production_record",
                "semantic_type": "numeric",
                "source": "business record",
            },
        }
    }


if __name__ == "__main__":
    unittest.main()
