# OpenAPI Audit

Use this reference for Kingdee Cosmic endpoint review.

## Entry Location

| Path feature | Preferred location strategy | Handler entry |
| --- | --- | --- |
| `*.do` | action XML or generated web action index | configured class and method |
| `/monitor/` | monitor handler registration | `handle0(HttpExchange)` |
| `/app/mc/` | MC V1 API index or `McApiService` subclass | `doCustomService(Map<String,Object>)` |
| `/v2/mc/` | MC V2 controller mapping | `@ApiPostMapping` method |
| `/app/` | OpenAPI V1 plugin registration | `doCustomService(Map<String,Object>)` |
| `/v2/` | OpenAPI V2 controller mapping | annotated method |
| other | `web.xml`, servlet, or Spring annotations | servlet/controller method |

## Required Evidence

Before assigning severity above Low, confirm:

- HTTP path and method;
- handler class and method;
- full request parameter list;
- authentication and filter/interceptor chain;
- taint source and sink;
- sanitizer or permission check status;
- call chain from entry to sink.

If any entry evidence is missing, mark `入口点未确认` and cap severity at Low unless there is independent runtime evidence.

## Kingdee-Specific Notes

- `/app/*` routes may be served under `/kapi/app/*`; match filters against actual runtime path.
- MC V1 APIs commonly authenticate through `McApiService.beforeCustomService()` and class annotations. Verify whether the target method actually calls the parent guard.
- QFilter, `QueryServiceHelper.query()` with QFilter, and ORM helpers are generally safe for SQL injection unless user input is later concatenated into raw SQL, KSQL, ORDER BY, table names, or dynamic expressions.
- Public diagnostic or monitor endpoints require extra auth review because low-privilege access can still expose logs, heap, profiler files, or runtime control surfaces.

## Report Fields

For each endpoint finding include:

- endpoint and handler;
- parameter table;
- auth requirement;
- vulnerable parameter;
- source-to-sink call chain;
- code location;
- severity and confidence;
- fix recommendation;
- verification state.
