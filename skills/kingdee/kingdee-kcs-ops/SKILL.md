---
name: kingdee-kcs-ops
description: "金蝶 KCS 运维契约执行：在有官方或本地已验证 API 合同后检查集群或服务状态，生成审计计划，并按用户批准的精确摘要执行、验证或回滚。用于 KCS 控制面查询、服务重启和需可审核变更；COSMIC_HOME 资源更新交给 kingdee-cosmic-devtools。"
---

# Kingdee KCS Ops

> Cross-platform Agent Skill: use task-relative UTF-8 plans and the current host's Python launcher; no shell-specific command is required.

## 路由

- 负责 KCS 控制面 `inspect -> plan -> apply-approved -> verify -> rollback`。
- `COSMIC_HOME`、工程模板和资源包 staging/apply 交给 `kingdee-cosmic-devtools`。
- 业务插件、运行诊断和部署验收交给 `kingdee-cosmic` 与 `kingdee-testing`。

## 契约门禁

1. 先读 `references/verified-contracts.md`。内置证据只覆盖服务状态查询与服务重启。
2. 其他 endpoint 必须由金蝶官方一手文档、当前环境只读网络证据或已复核本地实现建立 task-local draft；下载包目录、记忆和聊天历史不能作为 API 合同。
3. 按 `references/plan-contract.md` 写 draft，再用脚本生成带 SHA-256 的不可变计划。证据不足时返回 `gate_failed`，不猜 path、字段或成功条件。

## 工作流

脚本仅依赖 Python 标准库。所有路径以当前任务根解析，UTF-8 读写，并支持空格与 Windows/POSIX 路径。

1. `inspect`：只执行计划中 `GET`/`HEAD` 的 inspect 动作；生产只读检查可在任务授权范围内直接执行。
2. `plan`：规范化 draft，核对 target、证据、风险、验证和 rollback，输出 `plan_sha256`；不联网。
3. `apply-approved`：先向用户展示 target、动作集合、风险、不可逆项、验证/rollback 与摘要。用户一次批准精确摘要后，可连续执行该摘要内动作，不逐请求重复确认。
4. `verify`：只执行计划中的只读验证，并按 `expect` 判断；写请求返回成功不等于验证通过。
5. `rollback`：只执行同一已批准摘要内的 compensating action；不存在 rollback 时明确报告不可回滚，不临时发明逆操作。

从 skill 根运行；按宿主选择 `python` 或 Windows `py -3`：

```text
python scripts/kcs_ops.py plan --draft "<task-root>/kcs-draft.json" --output "<task-root>/.kcs-ops/plan.json" --task-root "<task-root>"
python scripts/kcs_ops.py inspect --plan "<task-root>/.kcs-ops/plan.json" --task-root "<task-root>"
python scripts/kcs_ops.py apply-approved --plan "<task-root>/.kcs-ops/plan.json" --task-root "<task-root>" --expected-sha256 "<sha256>" --approval-id "<task-approval-ref>"
python scripts/kcs_ops.py verify --plan "<task-root>/.kcs-ops/plan.json" --task-root "<task-root>"
python scripts/kcs_ops.py rollback --plan "<task-root>/.kcs-ops/plan.json" --task-root "<task-root>" --expected-sha256 "<sha256>" --approval-id "<task-approval-ref>"
```

## 凭据与输出

- 凭据只通过计划里的 `headers_from_env` 引用并注入当前进程；不接受命令行密钥，不读 `.env`、MEMORY、TOOLS 或聊天历史，不写凭据文件。
- 不输出请求头、响应头、原始请求体或未脱敏错误体。JSON 响应按敏感键和值脱敏；非 JSON 只输出字节数和摘要。
- TLS 校验始终开启；拒绝跨主机重定向和非 loopback 的明文 HTTP。
- 计划或结果文件只允许写到 `--task-root` 内；写入使用同目录临时文件与原子替换。

## 变更门禁

- `apply-approved`/`rollback` 必须同时匹配计划内摘要、`--expected-sha256` 和当前任务的一次性授权引用。
- 计划 target、action、body、风险、验证或 rollback 任一变化都会改变摘要，必须重新批准。
- apply 中的 write/destructive action 必须有预定义 rollback，或写明 `irreversible_reason` 并由用户在批准摘要时接受；apply/rollback 都必须绑定只读 verify action。
- 失败时保留已完成动作的审计结果，转 `verify` 或既定 `rollback`；不扩大 endpoint 或权限范围。

## 资源

- 计划字段与摘要规则：`references/plan-contract.md`
- 当前已验证契约：`references/verified-contracts.md`
- 跨平台客户端：`scripts/kcs_ops.py`
- 本地 mock 回归：`scripts/test_kcs_ops.py`
