# Metadata-driven Testing

Use this reference when tests depend on Kingdee entity fields, PC/mobile form bindings, operation plugins, or plugin entry points.

## Input

Prefer the `kingdee-metadata-analyzer` contract:

```bash
python3 <metadata-skill>/scripts/metadata_contract.py --inventory <inventory.json> --quick-cache <entity-cache.json> --environment dev --output metadata-contract.json
```

## Rules

- Generate tests from confirmed `fieldKey`, `fieldType`, `entryKey`, `formId`, `pageElement`, and `className` values.
- If `entryKey` is `null`, do not generate body-entry assertions that assume the field is on the bill head.
- If `forms` is empty, generate only entity-level tests and mark page-entry tests as blocked by missing metadata.
- Treat `warnings` as test preconditions. A warning does not fail local tests, but it must appear in the verification report.
- Runtime probes still need explicit dev/test targets; metadata only confirms intended entry points.

## Output

When reporting test coverage, separate:

- metadata-confirmed tests;
- source-inferred tests;
- runtime-verified tests;
- blocked tests caused by missing field, form, plugin, or environment evidence.
