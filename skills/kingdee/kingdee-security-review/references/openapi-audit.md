# OpenAPI Audit

Use this reference for Kingdee Cosmic endpoint review.

## Entry Location

Use these path patterns as local navigation hints, not a version-independent routing or authorization contract. Confirm the deployed API engine, registration and actual handler before applying a row.

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

## Official permission behavior by version

- Separate third-party application/API access authorization from the proxy user's business permissions. The official calling flow says operation APIs apply user permissions, while custom APIs require their plugin to implement permission handling; a valid token alone does not prove either branch is adequately authorized.
- V7.0.7 adds the save API's automatic save-permission check switch. When enabled it checks create/modify rights and may return `603` for missing permission. Verify the actual API switch and operation metadata binding; do not assume all historical APIs gained that behavior after an upgrade, or label a missing switch as proof of exploitation.
- V8.0.4 adds query permission checks for controlled base data and special data permissions behind the documented system setting. For controlled base data, the operation API can accept organization context through `X-BD-CTRL-ORGIDS` or `bos_bdCtrl_useOrgIds` as documented; the new RESTful engine uses the header only and documents full checks by default. First establish engine, target version, switch, proxy user, organization and data rules; do not transfer this behavior to older engines or alter settings during a read-only audit.

Official Knowledge sources (read as product documentation, not user comments):

- [金蝶AI苍穹OpenAPI调用流程](https://developer.kingdee.com/knowledge/specialDetail/226337046514476288?category=239331354741842688&id=213309216805890816&type=Knowledge&productLineId=29&lang=zh-CN), updated 2025-12-19 10:04; V4.0.006 / V6.0.1.
- [保存操作API权限增强校验](https://developer.kingdee.com/knowledge/specialDetail/226337046514476288?category=226337340351087360&id=685450223417566464&type=Knowledge&productLineId=29&lang=zh-CN), updated 2025-03-10 11:05; changelog V7.0.7 (2025-03-11). The displayed update and changelog dates differ; preserve both without inferring target rollout.
- [查询操作API支持权限全量校验](https://developer.kingdee.com/knowledge/specialDetail/226337046514476288?category=408200984532495104&id=788778229871437568&type=Knowledge&productLineId=29&lang=zh-CN), updated 2026-07-31 10:38; V8.0.4 (2025-12). Configuration names must be confirmed in the target UI/documentation, not guessed from a newer article.

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
