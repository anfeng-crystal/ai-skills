---
name: kingdee-cosmic-login
description: "金蝶云苍穹 dev/test/prod 登录、数据中心枚举与 Cookie/CSRF 会话校验；仅负责鉴权，业务调用返回原任务。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.0.0"
  tags: "kingdee, cosmic, login, authentication, cookie"
---

# Kingdee Cosmic Login
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 触发与路由
- 需要枚举数据中心、登录苍穹或校验 Cookie/CSRF 时使用。
- 本 skill 只返回鉴权结果；API、元数据、测试、诊断或业务写入仍由发起任务负责。

## 契约
| 模式 | 输入 | 输出 |
| --- | --- | --- |
| `list` | `base_url` | 数据中心 id 列表 |
| `login` | `base_url`、用户名、密码；多数据中心时含 `datacenter_id` | CLI 返回登录状态和 Cookie/CSRF 可用性；Python API 在同进程返回原值 |
| `check` | `base_url`、Cookie | `SESSION_VALID` |

- 环境由当前任务决定；目标是 prod 时可使用任务相关的生产凭据，鉴权本身不改变业务数据。
- 优先复用当前任务已提供或已配置的凭据和登录态；只有关键值无法发现时才询问。
- 密码、Cookie、CSRF 和数据中心信息只在当前进程与下游任务间传递，默认不输出、不落盘、不写项目配置。
- 下游副作用由调用方的执行合同控制；本 skill 不额外禁止已获批的生产测试或写入。

## 工作流
1. 从当前 skill 目录定位 `cosmic_login.py`；不要从业务仓库或用户 home 猜路径。
2. 复用项目 Python 环境并检查 `requests` 与 `Crypto`；缺依赖时使用项目包管理方式，不做全局安装。
3. 按模式运行。POSIX 使用 `python3`，Windows 使用 `py -3`：
   ```text
   <python> <skill-root>/cosmic_login.py <base_url>
   <python> <skill-root>/cosmic_login.py <base_url> <username> <password> [datacenter_id]
   <python> <skill-root>/cosmic_login.py --check <base_url> <cookie>
   ```
4. CLI 解析 `LOGIN_SUCCESS`、`COOKIE_AVAILABLE`、`CSRF_TOKEN_AVAILABLE`、`ACCOUNT_ID`、`SESSION_VALID`，不再期待 `COOKIE=` 或 `CSRF_TOKEN=` 原值；下游需要会话材料时，在同一 Python 进程中调用 `auto_login()` 并直接传给下游工具。
5. 下游收到 403 时区分会话失效和账号缺少接口权限；会话失效才重新登录。

## 门禁与失败
- 多数据中心且当前任务无法确定目标时，返回候选 id 后请求选择；不得默认选择可能改变租户范围的账号。
- `RSA 加密库不可用` 是依赖失败；`获取数据中心失败` 是 URL/网络失败；`获取公钥失败`、`登录失败` 是账号或服务端失败；不得混写成凭据不存在。
- 不从 memory、浏览器历史或无关项目文件搜集凭据，不记录认证请求头，不把 Cookie/CSRF 写入 CI、日志或异常栈。
- 跨平台必需路径不得依赖 bash、固定盘符、`$HOME` 或 `~`。

## 输出
返回环境、模式、账号/数据中心的脱敏标识、会话是否有效和下游可执行状态；不返回秘密值。
