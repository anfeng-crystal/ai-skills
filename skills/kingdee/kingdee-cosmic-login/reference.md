# Cosmic Login API Reference

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