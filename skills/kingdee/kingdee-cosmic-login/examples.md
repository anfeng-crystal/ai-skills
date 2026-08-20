# Cosmic Login 使用示例

## 示例 1: Claude Code 中使用 slash command

```
/kingdee-cosmic-login http://127.0.0.1:8080/ierp <username> <password>
```

## 示例 2: 命令行直接调用

```bash
# 列出数据中心
python cosmic_login.py http://127.0.0.1:8080/ierp

# 自动登录（单数据中心自动选择）
python cosmic_login.py http://127.0.0.1:8080/ierp admin <password>

# 指定数据中心
python cosmic_login.py http://127.0.0.1:8080/ierp admin <password> 1565321489509515264

# 检查 Cookie 是否有效
python cosmic_login.py --check http://127.0.0.1:8080/ierp "KERPSESSIONID=xxx; other=yyy"
```

## 示例 3: Python 代码中导入使用

```python
# 将 cosmic_login.py 复制到你的项目中，直接 import
from cosmic_login import auto_login, check_session

# 一步登录
result = auto_login("http://127.0.0.1:8080/ierp", "admin", "<password>")
if result["success"]:
    cookie = result["cookie"]
    csrf = result["csrf_token"]
    # 用 cookie 调用苍穹 API...

# 检查已有 Cookie 是否还能用
if not check_session("http://127.0.0.1:8080/ierp", old_cookie):
    result = auto_login(...)  # 重新登录
```

## 示例 4: 在 shell 脚本中解析状态

```bash
#!/bin/bash
if python cosmic_login.py http://127.0.0.1:8080/ierp admin <password>; then
    echo "登录成功；下游需要 Cookie/CSRF 时使用同进程 Python API"
else
    echo "登录失败" >&2
fi
```

## 示例 5: 多数据中心环境

```bash
# 先列出数据中心
$ python cosmic_login.py https://cosmic.example.com/ierp
DATACENTERS_COUNT=3
  DC: id=100001  name=开发中心
  DC: id=100002  name=测试中心
  DC: id=100003  name=生产中心

# 指定数据中心 ID 登录
$ python cosmic_login.py https://cosmic.example.com/ierp admin pwd 100002
LOGIN_SUCCESS
COOKIE_AVAILABLE=True
CSRF_TOKEN_AVAILABLE=True
ACCOUNT_ID=100002
```
