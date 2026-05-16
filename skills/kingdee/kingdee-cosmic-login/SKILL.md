---
name: kingdee-cosmic-login
description: "Kingdee auth: test env login, list data centers, verify Cookie/CSRF."
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [kingdee, cosmic, login, authentication, cookie]
  platforms:
    claude-code:
      argument-hint: "<base_url> [username] [password] [datacenter_id]"
      allowed-tools: "Bash Read Edit"
---

# Cosmic Login Skill
Use this skill when a task needs to log in to a Kingdee Cloud Cosmic test environment before calling APIs, running probes, or validating automated test flows. The skill ships a self-contained Python helper, `cosmic_login.py`, that performs the browser-equivalent RSA login flow and prints machine-readable `KEY=VALUE` output.

## Routing Boundary

This is a tool subprocess for authentication only. After login, datacenter selection, or session validation, return the Cookie/CSRF outcome to the active API, metadata, or troubleshooting task. Do not use this skill as the owner for business implementation, metadata analysis, SDK lookup, or Java plugin repair.

## Safety Rules

1. Treat username, password, Cookie, CSRF token, and datacenter ids as sensitive session material.
2. Do not persist credentials, Cookies, or tokens into project files unless the user explicitly asks for that destination.
3. Do not print raw passwords in final answers. Redact Cookies and CSRF tokens in chat summaries unless the user explicitly requested the raw value.
4. Prefer using the existing project Python environment. Do not install Python packages globally without user approval.
5. Do not use production credentials or production URLs unless the user explicitly says the current task is production-safe.

## Inputs

Required and optional inputs:

| Input | Required | Notes |
| --- | --- | --- |
| `base_url` | yes | Cosmic site root, usually ending with `/ierp`; trim trailing slash is handled by the script. |
| `username` | login only | Omit when the user only wants to list datacenters. |
| `password` | login only | Use only for the current command unless persistence is explicitly requested. |
| `datacenter_id` | required for multi-datacenter sites | If omitted and multiple datacenters exist, the script lists available ids and stops. |
| `cookie` | check only | Used with `--check` to verify an existing session. |

## Workflow

1. Identify the user intent:
   - List datacenters: only `base_url` is available or requested.
   - Login: `base_url`, `username`, and `password` are available.
   - Check session: user provides a Cookie and asks whether it is still valid.
2. Locate `cosmic_login.py` next to this `SKILL.md`. If the runtime exposes a skill directory variable, use that path. Otherwise search only the current skill directory or the project path the user provided.
3. Check dependencies only when needed:
   ```bash
   python -c "import requests; import Crypto"
   ```
   If this fails, ask before installing dependencies. Recommended packages are `requests` and `pycryptodome`; `rsa` is a supported fallback for encryption only.
4. Run the command that matches the intent:
   ```bash
   # List datacenters
   python "$COSMIC_LOGIN_SCRIPT" "$BASE_URL"

   # Login, auto-selecting only when exactly one datacenter exists
   python "$COSMIC_LOGIN_SCRIPT" "$BASE_URL" "$USERNAME" "$PASSWORD"

   # Login with explicit datacenter
   python "$COSMIC_LOGIN_SCRIPT" "$BASE_URL" "$USERNAME" "$PASSWORD" "$DATACENTER_ID"

   # Check existing Cookie
   python "$COSMIC_LOGIN_SCRIPT" --check "$BASE_URL" "$COOKIE"
   ```
5. Parse output:
   - Success starts with `LOGIN_SUCCESS`.
   - `COOKIE=...` is the HTTP Cookie header value.
   - `CSRF_TOKEN=...` is the `kd-csrf-token` header value when available.
   - `ACCOUNT_ID=...` is the datacenter/account id used for the login.
   - `SESSION_VALID=True` means an existing Cookie passed the lightweight check.
6. Use the login state only for the requested downstream task. When passing it to a follow-up API call, include:
   ```text
   Cookie: <COOKIE>
   kd-csrf-token: <CSRF_TOKEN>
   ```
7. In the final response, report the outcome and next action. Redact session material by default:
   ```text
   登录成功：account_id=156..., cookie 已获取，csrf token 已获取。
   ```

## Error Handling

| Output or symptom | Likely cause | Action |
| --- | --- | --- |
| `RSA 加密库不可用` | Neither `pycryptodome` nor `rsa` is installed. | Ask before installing `requests pycryptodome`, or use the project package manager. |
| `获取数据中心失败` | Base URL, network, proxy, or server availability issue. | Verify URL and connectivity before retrying. |
| `检测到 N 个数据中心` | The environment has multiple datacenters. | Ask the user to choose one of the listed ids, then rerun with `datacenter_id`. |
| `datacenter_id 看起来是占位符` | Placeholder config was passed as a real id. | Replace it with an actual datacenter id from the list command. |
| `获取公钥失败` | Wrong datacenter id, incompatible account, or server-side login error. | Recheck datacenter id and username type. |
| `登录失败` | Bad credentials, account restrictions, captcha, or server-side policy. | Ask the user to verify credentials or browser login state. |
| `SESSION_VALID=False` | Cookie expired or lacks required permission. | Re-login and retry the downstream API call. |
| HTTP 403 on downstream API | Login succeeded but the account lacks API/kapi permission. | Ask the user to confirm Cosmic permissions. |
