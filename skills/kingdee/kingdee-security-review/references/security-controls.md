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
