# Cosmic Login API Reference

## 适用边界

下列端点、RSA 和 CSRF 回退描述的是随附 `cosmic_login.py` 的当前实现，尚未取得覆盖全部苍穹版本的官方页面登录协议合同；使用时以当前任务已有的目标版本/配置及脱敏会话验证为准，不能宣称与所有浏览器登录方式完全一致。

页面 Cookie/CSRF 与外部 OpenAPI 的应用令牌是不同入口。官方 [金蝶AI苍穹OpenAPI调用流程](https://developer.kingdee.com/knowledge/specialDetail/226337046514476288?category=239331354741842688&id=213309216805890816&type=Knowledge&productLineId=29&lang=zh-CN)（更新于 2025-12-19 10:04，V6.0.1 调整认证）要求外部调用通过第三方应用及代理用户取得令牌，并在请求头传递。仅在目标接口明确接受页面会话时复用本模块的 Cookie；OpenAPI 令牌流程见 `kingdee-openapi-client`。

## cosmic_login.py — 自包含模块 API

### 函数

#### `list_datacenters(base_url, timeout=15) -> list`
获取苍穹数据中心列表。返回 `[{"id": "xxx", "name": "开发中心"}, ...]`

#### `login(base_url, username, password, account_id, language="zh_CN", timeout=15) -> dict`
完整登录流程。返回:
```python
{
    "success": bool,
    "cookie": str,          # 完整 Cookie 字符串（可直接用于 HTTP Header）
    "csrf_token": str,      # kd-csrf-token 值
    "error": str,           # 失败时的错误信息
    "account_id": str,      # 数据中心 ID
    "user_id": str,         # 用户 ID（如可获取）
}
```

#### `auto_login(base_url, username, password, account_id="", timeout=15) -> dict`
一步登录。account_id 留空时自动检测数据中心（仅 1 个时自动使用，多个时返回列表）。

#### `check_session(base_url, cookie, csrf_token="", timeout=8) -> bool`
检查已有 Cookie 是否仍然有效。发送轻量请求到 `/api/login/getUserLanguage.do`。

### CLI 用法

```bash
python cosmic_login.py <url>                         # 列出数据中心
python cosmic_login.py <url> <user> <pwd>            # 自动登录
python cosmic_login.py <url> <user> <pwd> <dc_id>    # 指定数据中心
python cosmic_login.py --check <url> <cookie>        # 检查会话
```

登录成功时 CLI 输出 `LOGIN_SUCCESS`、`COOKIE_AVAILABLE`、`CSRF_TOKEN_AVAILABLE` 和 `ACCOUNT_ID`，不会输出 Cookie/CSRF 原值。下游需要原值时，应在同一 Python 进程中调用 `auto_login()` 并直接消费返回字典。

## RSA 加密细节

密码使用 RSA PKCS1v1.5 加密:
1. 服务端通过 `/auth/getPublicKey.do` 提供 PEM 公钥
2. 客户端用公钥加密明文密码
3. 加密字节经 Base64 编码后传输

支持两个加密后端:
- `pycryptodome`（推荐）: `Crypto.Cipher.PKCS1_v1_5`
- `rsa` 库（备选）: `rsa.encrypt()`

## CSRF Token 提取策略

三级回退:
1. 从 Cookie 键中查找包含 "csrf" 的项
2. 从响应头 `kd-csrf-token` 获取
3. 从 index.html 页面内容正则提取
