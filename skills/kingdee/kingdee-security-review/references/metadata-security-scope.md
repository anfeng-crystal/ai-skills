# Metadata Security Scope

Use metadata evidence before reviewing or actively verifying Kingdee page, operation, OpenAPI, or plugin-entry security issues.

## Required Evidence

- Entity number and environment.
- Form or operation entry from `forms[].formId`.
- Plugin class from `forms[].plugins[].className`.
- Page element from `forms[].plugins[].pageElement`.
- Source type from `forms[].plugins[].source`.

## Scope Decisions

| Evidence | Allowed decision |
|---|---|
| Metadata contract has matching dev/test form and plugin | Static audit or scoped `verify` can proceed after `scope_check.py`. |
| Only source code exists, no metadata binding | Static audit can proceed; active POC must be marked blocked until binding is confirmed. |
| Contract says production only | Default deny active POC unless user explicitly authorizes production scope. |
| Contract has warnings | Include warnings in scope report and avoid broad severity claims. |

## Workflow

1. Ask `kingdee-metadata-analyzer` for a contract when the finding depends on real page or operation exposure.
2. Run `scripts/scope_check.py` with the target mode and URL before any network probe.
3. Start with `scripts/poc_runner.py` dry-run and only execute after scope and payload are both approved.

## Report Language

Do not say an endpoint is exploitable just because a class exists in source. State one of:

- metadata-confirmed entry;
- source-only candidate;
- runtime-verified finding;
- blocked by missing scope evidence.
