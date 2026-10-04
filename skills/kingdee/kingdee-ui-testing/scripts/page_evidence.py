"""Shared local page identity contract; never infer identity from navigation."""

from __future__ import annotations

from typing import Any


PAGE_TYPES = {"list", "detail", "edit", "dialog"}
IDENTITY_FIELDS = ("formId", "pageType", "pageElement")
EVIDENCE_FIELDS = ("route", *IDENTITY_FIELDS)


def nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def expected_page(value: Any) -> dict[str, str]:
    """Validate an explicitly declared expectation, without manufacturing IDs."""
    if not isinstance(value, dict) or set(value) != set(IDENTITY_FIELDS):
        raise ValueError("page requires only formId, pageType and pageElement")
    if any(not nonempty_string(value[field]) for field in IDENTITY_FIELDS):
        raise ValueError("page identity fields must be non-empty strings")
    normalized = {field: value[field].strip() for field in IDENTITY_FIELDS}
    if normalized["pageType"] not in PAGE_TYPES:
        raise ValueError("pageType must be list, detail, edit or dialog")
    return normalized


def check_page(step: dict[str, Any], observed: Any) -> dict[str, Any]:
    """Compare before redaction. A match proves only supplied identity agreement."""
    if "page" not in step:
        return {"status": "not-requested"}
    expected = expected_page(step["page"])
    actual = observed if isinstance(observed, dict) else {}
    mismatches = [
        field for field in IDENTITY_FIELDS
        if nonempty_string(actual.get(field)) and actual[field].strip() != expected[field]
    ]
    missing = [field for field in EVIDENCE_FIELDS if not nonempty_string(actual.get(field))]
    if mismatches:
        # An explicit wrong identity remains actionable even when other proof is absent.
        return {"status": "wrong_page", "mismatchedFields": mismatches, "missingFields": missing}
    if missing:
        return {"status": "missing", "missingFields": missing}
    return {"status": "matched"}
