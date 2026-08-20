from __future__ import annotations

import importlib.util
import sys
import unittest
from argparse import Namespace
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scope_check.py"
SPEC = importlib.util.spec_from_file_location("scope_check", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def args(**overrides):
    values = {
        "mode": "audit-readonly",
        "target_url": "https://prod.example.invalid/ierp",
        "scope": "prod",
        "allow_prod": False,
        "allow_unknown": False,
        "reason": "ticket-123",
    }
    values.update(overrides)
    return Namespace(**values)


class ScopeCheckTest(unittest.TestCase):
    def test_production_readonly_contract_is_allowed(self) -> None:
        decision = MODULE.decide(args())
        self.assertTrue(decision.allowed)
        self.assertEqual("audit-readonly", decision.mode)

    def test_readonly_requires_authorization_reference(self) -> None:
        self.assertFalse(MODULE.decide(args(reason="")).allowed)

    def test_unknown_readonly_scope_is_blocked(self) -> None:
        self.assertFalse(MODULE.decide(args(scope="unknown")).allowed)

    def test_active_production_remains_blocked_without_flag(self) -> None:
        decision = MODULE.decide(args(mode="verify", reason="ticket-123"))
        self.assertFalse(decision.allowed)

    def test_sensitive_query_values_are_redacted_from_decision(self) -> None:
        decision = MODULE.decide(
            args(target_url="https://prod.example.invalid/ierp?token=plain-secret&tenant=demo")
        )
        self.assertNotIn("plain-secret", decision.target_url)
        self.assertIn("tenant=demo", decision.target_url)
        self.assertIn("%3Credacted%3E", decision.target_url)

    def test_embedded_credentials_are_blocked_and_redacted(self) -> None:
        decision = MODULE.decide(args(target_url="https://user:plain-secret@prod.example.invalid/ierp"))
        self.assertFalse(decision.allowed)
        self.assertNotIn("plain-secret", decision.target_url)

    def test_non_http_target_is_blocked(self) -> None:
        self.assertFalse(MODULE.decide(args(target_url="file:///tmp/example")).allowed)


if __name__ == "__main__":
    unittest.main()
