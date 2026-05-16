# kingdee-cosmic-login

**作者：** AIHR 交付效能部

**注意：仅限内部使用**

面向金蝶云苍穹（Kingdee Cloud Cosmic）开发的自动登录工具，提供**自包含、零项目依赖**的登录能力，一行命令完成 RSA 加密认证，拿到可直接用于后续所有 OpenAPI / kapi / 元数据接口调用的 `Cookie` 与 `CSRF Token`。

---

## 📌 概览

`kingdee-cosmic-login` 专门解决**"调任何苍穹接口前，先得有合法登录态"**这一通用前置问题。它把苍穹页面端登录的 3 步 RSA 加密流程（拉数据中心、取公钥、加密提交凭据）封装成一个独立 Python 脚本，无需手工抓包、F12 拷 Cookie，也无需任何项目侧改造。

适用场景包括但不限于：自动化测试、CI/CD 鉴权、二开调试脚本、元数据批量探查、HAR 回放、跨环境对比工具等所有"需要先登录再调用苍穹接口"的工作流。它也可以作为 `cosmic-dev`、`cosmic-replay`、`cosmic-hr-knowledge-ingest`、`cosmic-env` 等所有"调用苍穹环境"工具的**共用登录底座**。

## 🧠 核心能力

- `🔐` **RSA 加密自动登录**：3 步走完整页面端登录协议（getAllDatacenters → getPublicKey → yzjlogin），与浏览器登录完全一致，不依赖私有协议或抓包来的临时 Cookie
- `🌐` **多数据中心识别**：单数据中心自动选择，多数据中心列出 ID 强制要求显式指定
- `🔁` **会话有效性探活**：`--check` 模式发轻量请求验证现有 Cookie 是否仍可用，避免重复登录
- `📦` **零项目依赖**：整个目录可独立拷贝到任何项目使用，仅需 `pip install requests pycryptodome`
- `🧰` **双重 RSA 后端兜底**：优先 `pycryptodome`，失败回退 `rsa` 库，再失败尝试解 DER 重构密钥，最大化兼容性
- `📤` **标准化 KEY=VALUE 输出**：脚本输出可被 shell / Python 直接 grep 解析，不需要 JSON parser
- `🧩` **三种使用入口**：命令行 CLI、Python 模块 `import auto_login`、Shell 脚本管道

## 🧭 解决了什么问题

| 老办法的痛点 | kingdee-cosmic-login 给出的答案 |
|--------------|------------------------|
| F12 复制 Cookie，过期就重抓 | `auto_login()` 一行拿到 Cookie，配 `check_session()` 失效自动重登 |
| 各项目重复实现 RSA 加密 + 数据中心选择 | 单一脚本，复制即用，所有项目共享同一份维护代码 |
| 每次写新工具都得绑定项目侧 `config.py` | 脚本不依赖任何项目结构，输出 KEY=VALUE 任你处置 |
| 多数据中心环境用错 ID 静默登错租户 | 单 DC 自动选 / 多 DC 强制要求显式指定，避免误登 |
| `pycryptodome` 装不上的内网机器无解 | 自动回退 `rsa` 库，仍能完成加密 |
| Cookie 拿到了但 CSRF Token 找不到 | 三级回退提取（Cookie 字段 / 响应头 / index.html 正则） |

## 🚀 快速开始

### 快速分流

| 你的情况 | 从哪步开始 | 预计耗时 |
|----------|------------|--------|
| 首次安装 | 步骤 1 | 3 分钟 |
| 已装好，要登一个新环境 | 步骤 4 | 10 秒 |
| 已有 Cookie，想确认是否过期 | 步骤 5 | 5 秒 |
| 想在自己的 Python 工程里 import 用 | 步骤 6 | 1 分钟 |

下面是完整安装与使用流程。

---

## 1. 环境检查

在开始之前，请确保您的系统满足以下要求：

### 必需环境

| 依赖项 | 版本要求 | 检查命令 | 备注 |
|--------|----------|----------|------|
| Python | 3.8+ | `python --version` | 推荐 3.10+ |
| requests | 任意版本 | `pip show requests` | HTTP 客户端 |
| pycryptodome | 任意版本 | `pip show pycryptodome` | RSA 加密首选后端 |

### 检查清单

```bash
# 检查 Python 版本
python --version

# 检查 pip 包
pip show requests pycryptodome
```

### 一键安装依赖

```bash
pip install requests pycryptodome
```

> 如果内网无法访问 pypi，可改装 `pip install requests rsa`，脚本会自动降级到 `rsa` 库后端。

---

## 2. 安装

`kingdee-cosmic-login` 是一个完全自包含的目录，把整个目录 `cp` 到任意位置即可使用。

### 2.1 直接拷贝到工程

```bash
# 任意位置都可以
cp -R /path/to/kingdee-cosmic-login /your/workspace/kingdee-cosmic-login
```

之后用绝对路径或相对路径调用脚本：

```bash
python /your/workspace/kingdee-cosmic-login/cosmic_login.py <base_url> <user> <password>
```

### 2.2 作为 Python 包 import

把 `kingdee-cosmic-login/` 目录加入 `PYTHONPATH`，或直接拷到工程内的 `tools/` 目录：

```bash
cp /path/to/kingdee-cosmic-login/cosmic_login.py /your/project/tools/
```

```python
import sys
sys.path.insert(0, "/your/project/tools")
from cosmic_login import auto_login, check_session
```

### 2.3 多工程共享一份源（推荐）

为避免多工程各拷贝一份导致版本散落，建议**只维护一份**源目录，再用软链接指过去：

**macOS / Linux：**

```bash
# 唯一维护点
mkdir -p ~/tools
cp -R /path/to/kingdee-cosmic-login ~/tools/kingdee-cosmic-login

# 各工程通过软链接引用
ln -sfn ~/tools/kingdee-cosmic-login /your/project-a/tools/kingdee-cosmic-login
ln -sfn ~/tools/kingdee-cosmic-login /your/project-b/tools/kingdee-cosmic-login
```

**Windows（推荐管理员 PowerShell）：**

```powershell
mkdir $env:USERPROFILE\tools -ErrorAction SilentlyContinue
Copy-Item -Path D:\path\to\kingdee-cosmic-login -Destination $env:USERPROFILE\tools\kingdee-cosmic-login -Recurse

cmd /c mklink /J "D:\your\project-a\tools\kingdee-cosmic-login" "$env:USERPROFILE\tools\kingdee-cosmic-login"
```

---

## 3. 配置（可选）

**kingdee-cosmic-login 没有强制配置文件**，所有参数通过命令行传入即可。但如果你不想每次都打长串 URL，可以借鉴下面两种约定。

### 3.1 环境变量（推荐）

在 shell profile 或项目 `.env` 里写：

```bash
export COSMIC_BASE_URL="http://127.0.0.1:8080/ierp"
export COSMIC_USERNAME="admin"
export COSMIC_PASSWORD="KDadm123"
export COSMIC_DATACENTER_ID="1565321489509515264"
```

调用时直接引用：

```bash
python /path/to/cosmic_login.py "$COSMIC_BASE_URL" "$COSMIC_USERNAME" "$COSMIC_PASSWORD" "$COSMIC_DATACENTER_ID"
```

### 3.2 项目侧 `cosmic.json`（与下游工具共享）

如果项目里同时使用 `cosmic-replay` / `cosmic-env` 等下游工具，建议在项目根放：

```json
{
  "baseUrl": "http://127.0.0.1:8080/ierp",
  "username": "admin",
  "password": "KDadm123",
  "datacenterId": "1565321489509515264"
}
```

让下游工具共享同一份凭据，避免到处散落。

---

## 4. 登录使用

### 4.1 命令行直接调用

```bash
# 1. 列出数据中心（不传账号密码 = 列表模式）
python /path/to/cosmic_login.py http://127.0.0.1:8080/ierp

# 2. 自动登录（单数据中心环境，自动选择）
python /path/to/cosmic_login.py http://127.0.0.1:8080/ierp admin KDadm123

# 3. 指定数据中心登录（多数据中心环境必须显式指定）
python /path/to/cosmic_login.py http://127.0.0.1:8080/ierp admin KDadm123 1565321489509515264

# 4. 检查已有 Cookie 是否还有效
python /path/to/cosmic_login.py --check http://127.0.0.1:8080/ierp "KERPSESSIONID=xxx; other=yyy"
```

### 4.2 Python 代码内 import

```python
from cosmic_login import auto_login, check_session, list_datacenters

# 一步登录
result = auto_login("http://127.0.0.1:8080/ierp", "admin", "KDadm123")
if result["success"]:
    cookie = result["cookie"]
    csrf_token = result["csrf_token"]
    # 用 cookie + csrf 调用任意苍穹接口
    headers = {"Cookie": cookie, "kd-csrf-token": csrf_token}

# 复用前先探活
if not check_session("http://127.0.0.1:8080/ierp", old_cookie):
    result = auto_login("http://127.0.0.1:8080/ierp", "admin", "KDadm123")
```

### 4.3 Shell 脚本中解析输出

```bash
#!/bin/bash
OUTPUT=$(python cosmic_login.py http://127.0.0.1:8080/ierp admin KDadm123)

if echo "$OUTPUT" | grep -q "LOGIN_SUCCESS"; then
    COOKIE=$(echo "$OUTPUT" | grep "^COOKIE=" | cut -d= -f2-)
    CSRF=$(echo "$OUTPUT" | grep "^CSRF_TOKEN=" | cut -d= -f2-)
    curl -H "Cookie: $COOKIE" -H "kd-csrf-token: $CSRF" \
         http://127.0.0.1:8080/ierp/kapi/sys/user/getCurrentUser
fi
```

### 4.4 在 CI / 自动化脚本里使用

```yaml
# .gitlab-ci.yml 片段示例
test:
  script:
    - pip install requests pycryptodome
    - python tools/cosmic_login.py "$COSMIC_BASE_URL" "$COSMIC_USERNAME" "$COSMIC_PASSWORD" > .login.out
    - export COSMIC_COOKIE=$(grep '^COOKIE=' .login.out | cut -d= -f2-)
    - python tools/run_smoke_test.py
```

---

## 5. 输出格式

脚本统一输出 KEY=VALUE 行，可被任意工具直接 grep 解析。

### 5.1 登录成功

```
LOGIN_SUCCESS
COOKIE=KERPSESSIONIDxxx=yyy; other=zzz
CSRF_TOKEN=abc123
ACCOUNT_ID=1565321489509515264
USER_ID=12345
```

### 5.2 列数据中心（未传密码时的模式）

```
DATACENTERS_COUNT=3
  DC: id=100001  name=开发中心
  DC: id=100002  name=测试中心
  DC: id=100003  name=生产中心
```

### 5.3 登录失败

```
LOGIN_FAILED: 用户名或密码错误
```

---

## 6. 登录成功后

拿到 Cookie 后，按目标项目约定写入即可，三种常见做法：

1. **写入配置文件** — 更新 `config.py` / `.env` / `settings.json` 里的 cookie 字段
2. **导出环境变量** — `export COSMIC_COOKIE="<cookie>"`，下游脚本用 `os.environ` 读
3. **直接传参** — 在后续 API 调用中 `headers={"Cookie": cookie, "kd-csrf-token": csrf_token}`

典型用法：

```bash
# 例：用 cookie 调元数据 OpenAPI
curl -H "Cookie: $COSMIC_COOKIE" -H "kd-csrf-token: $CSRF" \
     "http://127.0.0.1:8080/ierp/kapi/v2/.../getMetaFields?formId=hspm_ermanfilereform"
```

---

## 🛠️ 常见问题排查

### Q1: `RSA 加密库不可用`

**原因：** `pycryptodome` 与 `rsa` 都未安装。

**解决方案：**
```bash
pip install pycryptodome
# 或备选：
pip install rsa
```

### Q2: `获取公钥失败` / 连接超时

**可能原因：**
1. base_url 拼错（缺 `/ierp` 后缀 / 协议写错）
2. 苍穹服务器不可达（VPN / 内网穿透 / 防火墙）
3. 服务端 `/auth/getPublicKey.do` 接口被禁用

**排查步骤：**
```bash
# 直接 ping 接口
curl -v "${COSMIC_BASE_URL}/auth/getAllDatacenters.do"

# 确认能拉到 JSON 而不是 HTML 登录页
```

### Q3: `检测到 N 个数据中心`，登录中断

**原因：** 多数据中心环境必须显式指定 `datacenter_id`，避免误登错租户。

**解决方案：**
```bash
# 先列出所有数据中心 id
python cosmic_login.py http://127.0.0.1:8080/ierp

# 取需要的 id 作为第 4 个参数
python cosmic_login.py http://127.0.0.1:8080/ierp admin KDadm123 100002
```

### Q4: `登录失败：用户名或密码错误`

**排查：**
1. 在浏览器手工登录确认凭据有效
2. 确认账号未被锁定 / 强制改密
3. 确认数据中心 ID 与该账号有权限的租户对应

### Q5: 登录成功但调 API 返回 HTTP 403

**原因：** Cookie 合法但当前账号在该数据中心**没有 kapi 调用权限**。

**解决方案：** 在苍穹管理后台 → 用户角色 → 开启对应应用 / OpenAPI 调用权限。

### Q6: `check_session` 总是返回 False

**可能原因：**
1. Cookie 已过期（默认会话 30 分钟，不活动会断）
2. 服务端重启了，之前的 session 全部失效
3. Cookie 字符串拷贝时多了空格 / 换行

**解决方案：** 直接重新 `auto_login()`，本 Skill 设计上鼓励"过期就重登"而不是手工续期。

### Q7: pycryptodome 在内网机器装不上

**解决方案：** 装 `rsa` 库即可，脚本会自动检测并降级。

```bash
pip install rsa
```

性能差异可忽略（一次登录加密只跑一次）。

---

## 📚 进阶用法

详见同目录的两份补充文档：

- [`reference.md`](reference.md) — 函数级 API 参考（`list_datacenters` / `login` / `auto_login` / `check_session` 的完整签名与返回结构）
- [`examples.md`](examples.md) — 5 个端到端使用示例（slash command、CLI、Python import、shell 脚本、多数据中心场景）

---

## 🔄 与下游工具的协作矩阵

| 下游工具 | 何时调用 kingdee-cosmic-login | 用 Cookie 干什么 |
|----------|----------------------|-----------------|
| `cosmic-env` | 列应用 / 列表单 / 探元数据前 | 调 `EnvProbe` / `CosmicOpenApiClient` |
| `cosmic-replay` | YAML 用例执行前 | 注入到 HAR 回放的 HTTP 头 |
| `cosmic-hr-knowledge-ingest` | 各阶段元数据采集前 | 反复调 `getMetaFields` / `queryOne` |
| `cosmic-dev` | 真发 buildMeta / addRule 前 | 调元数据治理 OpenAPI |
| 自定义脚本 / CI 任务 | 任意苍穹 kapi 调用前 | 直接放进 `headers["Cookie"]` |

---

## 📁 目录结构

```
kingdee-cosmic-login/
├── README.md          # 本文档（详细说明 + 排错）
├── SKILL.md           # Skill 元数据（自动唤起的描述与触发规则）
├── cosmic_login.py    # 自包含登录脚本（唯一代码文件，零项目依赖）
├── reference.md       # 函数级 API 参考
└── examples.md        # 端到端使用示例
```

接收方只需：

1. 把整个目录拷贝到任意位置
2. `pip install requests pycryptodome`
3. 直接 `python cosmic_login.py ...` 调用，或在 Python 代码内 `import`

---

## 📜 变更日志

- **v1.0** — 初版：3 步 RSA 加密登录、多数据中心识别、`--check` 探活、KEY=VALUE 输出
- **v1.1** — 新增 `pycryptodome → rsa` 双后端兜底，DER 重构密钥兜底
- **v1.2** — 完善 CSRF Token 三级回退提取策略

---

## ⚠️ 安全提示

- **不要把账号密码硬编码到脚本或仓库**，请用环境变量或 `.env`（且 `.env` 加入 `.gitignore`）
- **Cookie 与 CSRF Token 等同账号密码**，输出后请避免持久化到日志、告警群、issue 评论等可被检索的地方
- 多数据中心环境务必**显式指定 datacenter_id**，避免误登生产
- 本 Skill **仅限内部测试与开发环境使用**，不要用来对生产环境做任何写操作前未经授权的调用