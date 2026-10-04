# Security Controls

This compact checklist is adapted from Kingdee code audit rules and quick audit patterns.

## SQL Injection

Risk sinks:

- `Statement.execute*` with user-controlled SQL;
- string concatenation into SQL, KSQL, ORDER BY, table names, or entity names;
- `DB.execute(DBRoute, String)` without parameter binding;
- MyBatis `${param}`.

Safe controls:

- `PreparedStatement` or named parameters;
- MyBatis `#{param}`;
- QFilter and `QueryServiceHelper.query()` with structured filters;
- hardcoded allowlist for dynamic column names.

Kill switches:

- enum or strong numeric type after parsing and range check;
- hardcoded mapping from user input to constant values;
- metadata keys from trusted definitions.

## XSS

Risk sinks:

- direct response writer output;
- JSP expression output;
- template raw HTML rendering;
- frontend `innerHTML`, Vue `v-html`, React raw HTML.

Safe controls:

- context-aware HTML/JS/URL encoding;
- template escaped output;
- JSON content type when not rendered as HTML;
- HTML sanitizer allowlist.

## SSRF

Risk sinks:

- user-controlled `URL`, `HttpClient`, `RestTemplate`, `OkHttp`, or `URLConnection`.

Safe controls:

- exact host allowlist;
- protocol allowlist;
- private, loopback, link-local, and metadata IP rejection;
- redirect disabled or revalidated;
- DNS rebinding protection.

## RCE / Expression Injection

Risk sinks:

- `Runtime.exec`, `ProcessBuilder`, script engine eval;
- JNDI lookup with user data;
- Velocity, FreeMarker, SpEL, OGNL, or Groovy evaluation;
- diagnostic endpoints exposing runtime command capability.

Safe controls:

- command allowlist and argument array form;
- platform API instead of shell;
- read-only expression context;
- signed or server-owned script content.

## Deserialization

Risk sinks:

- `ObjectInputStream.readObject`;
- `XMLDecoder`;
- Fastjson autoType;
- Jackson default typing;
- Hessian on user-controlled streams.

Safe controls:

- schema-bound JSON/XML parsing;
- class allowlist filters;
- Fastjson safe mode;
- no reachable gadget chain on classpath.

## File And Path

Risk sinks:

- download/upload using user-controlled path;
- zip extraction;
- file delete, move, or copy from request parameters.

Safe controls:

- canonical path check under a fixed base directory;
- extension and MIME allowlist;
- random server-side names;
- zip slip validation.

## Access Control / IDOR

Check:

- tenant, org, user, role, and data permission filters;
- owner checks on object ids;
- mass assignment of hidden fields;
- cross-data-center or MC privileged operations.

Do not accept UI hiding, frontend route checks, or menu permission alone as backend authorization.

### 批量权限证据

仅在审阅批量角色/授权变更或其结果时使用。先确认目标版本及实际页面；官方 V8.0.12 说明区分两类操作，不能混用对象或范围：

| 入口 | 实际改变的关系 | 核对范围 |
| --- | --- | --- |
| 安全管理 / 用户授权列表：批量分配或删除通用角色 | 用户在指定组织范围内拥有的通用角色 | 已选用户、组织、通用角色；多个组织均影响角色生效范围 |
| 安全管理 / 通用角色列表：批量追加或删除授权 | 通用角色包含的功能权限项 | 已选角色、追加/删除类型、具体功能权限项及其云/应用/业务对象 |

- 两类批量操作都在“保存”时执行；勾选、增删候选行或停留配置页不证明权限已变更。核实实际保存结果及对应关系，再结合权限日志追溯，不能仅凭成功提示宣布全部范围生效。
- 分配角色、追加权限会跳过已存在项，不重复增加。报告区分本次新增、原已存在、删除、失败和未核实的关系；没有逐项证据时不把全部选中数量当新增数量，也不猜部分成功或整批原子性。
- 批量角色分配的权限日志来源可标为“批量分配通用角色”；其余操作按实际日志核对，不推造来源字符串或导出 schema。日志记录与当前关系相互印证；删除一条角色/授权关系不证明用户已失去所有同类有效权限，仍需核对其他已存在的授权路径、组织及数据权限。
- 文档明确提示批量删除不可逆，不能假定界面有自动撤销，也不以删除/重新分配作只读审计的探针。变更计划应列明精确关系、影响范围及可核验恢复依据；实际变更由对应任务授权覆盖，本审阅卡不执行保存、删除或授予权限。

来源：[批量分配/删除权限](https://vip.kingdee.com/knowledge/890279731504517888)，更新 2026-09-22 17:18，初始版本 V8.0.12（2026年9月）。这些是该版本两个批量界面的关系与保存语义，不代表所有权限来源、接口调用或旧版本的通用合同。
