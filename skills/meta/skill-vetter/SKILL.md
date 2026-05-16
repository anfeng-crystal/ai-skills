---
name: skill-vetter
description: Third-party skill security: source verification, script behavior, write risk, secret exposure. For optimizing your own skills, use darwin-skill.
metadata:
  author: anfeng
  version: "0.2.0"
  license: MIT
  tags: [security, skill, review, static-analysis]
---

# Skill Vetter

> **Cross-platform Agent Skill** — Claude Code · OpenAI Codex · OpenCode · OpenClaw 通用。
> 跨平台 SKILL.md，遵循开放 Agent Skill 规范。

## 触发边界
- 用户要安装、评估、引入、分发、复用或审查第三方 skill 时使用。
- 重点处理本地路径、解包目录、market skill、临时下载目录或别人给的 skill 目录。
- 不负责真正安装、分发或修复 skill；只做审查和结论建议。

## 默认范围
- v1 只做静态审查，不联网查信誉，不执行目标脚本。
- 审查对象默认是一个本地 skill 路径；可以是 skill 根目录、`SKILL.md` 文件路径，或只包含一个 `SKILL.md` 的上层目录。
- 输出结论分三级：
  - `allow`：未发现阻断性风险，可继续后续安装/分发流程
  - `review_needed`：存在中高风险点，需要人工复核后再决定
  - `block`：存在高危命令、强覆盖宿主目录或明显危险安装路径，不建议继续

## 快速工作流
1. 先确认审查对象路径存在，并尽量指向具体 skill 根目录。
2. 运行静态检查：

```bash
node scripts/inspect-skill.mjs --path /absolute/path/to/skill --json
```

3. 如果只是想看摘要，可不加 `--json`：

```bash
node scripts/inspect-skill.mjs --path /absolute/path/to/skill
```

4. 如果要把“非 allow”当失败处理，加 `--strict`：

```bash
node scripts/inspect-skill.mjs --path /absolute/path/to/skill --strict --json
```

5. 先看 `recommendation`，再看 `findings` 和 `manualReview`。
6. 只有 `allow` 或人工明确接受风险后，才进入 `skill-installer`、`skill-installer` 或手工分发流程。

## 审查重点
- `SKILL.md` 是否存在，frontmatter 是否完整
- 是否包含安装脚本、联网安装命令、远程执行模式
- 是否写入 `.codex/skills`、`.claude/skills`、`.agents/skills`、`.junie/skills`
- 是否存在 `rm -rf`、`git reset --hard`、`curl|sh` 等高危命令
- 是否包含软链接覆盖、强制复制、绝对路径、用户目录硬编码
- 是否要求密钥、Token、密码或 Basic Auth
- 是否存在需要人工阅读的宿主集成文件，如 `AGENTS.md`、`CLAUDE.md`、安装脚本

## 常用命令

```bash
node scripts/inspect-skill.mjs --path /path/to/skills/incoming/market/ok-cosmic/raw/ok-cosmic --json
node scripts/inspect-skill.mjs --path /path/to/skills/incoming/market/kingscript-skills-main/raw/kingscript-skills-main/kingscript-code-generator --strict --json
node scripts/inspect-skill.mjs --path /path/to/skills/active/web-access
```

## 用户确认检查点

| 场景 | 停住确认内容 |
|------|-------------|
| 审查结果为 `block` | "发现 critical/high 风险，建议 block。确认继续查看详情？" |
| 审查结果为 `review_needed` | "存在中高风险，建议人工复核。确认继续安装流程？" |
| 路径下无 `SKILL.md` | "路径下未找到 SKILL.md，停止审查。请提供正确的 skill 路径。" |
| 同一目录下多个 skill root | "发现多个 skill，请确认审查哪一个后再继续。" |
| 用户要求自动安装/链接 | "本 skill 只负责审查，不执行安装或软链接。请使用 skill-installer 或手动操作。" |

## 边界与回退

| 异常 | 处理 |
|------|------|
| 路径不存在 | 报告路径不存在，停止审查 |
| 路径下无 `SKILL.md` | 停止并要求缩小路径范围 |
| 多个候选 `SKILL.md` | 停止并要求确认审查哪一个 |
| `inspect-skill.mjs` 执行失败 | 报告脚本错误，建议手动检查文件权限和 Node 环境 |
| strict 模式返回非 `allow` | 以非零退出码报告，阻断后续安装/分发流程 |
| 静态扫描可能遗漏 | 明确告知局限性：不能代替人工判断业务可信度和真实副作用 |

## 审查结果分类汇总

解读 `inspect-skill.mjs --json` 输出时，按以下优先级组织结论：

1. **先看 `recommendation`** — 决定是 allow / review_needed / block
2. **再看 `findings` 中的 severity 分布** — critical > high > medium > low
3. **重点看 `destructiveOps`** — 如果有值，标出具体文件和行号
4. **看 `filesystemWrites`** — 是否涉及宿主 skills 目录
5. **看 `secretHits`** — 是否要求 API Key/Token/密码
6. **最后看 `manualReview`** — 是否有 README、多 skill root 等需人工确认项

**分组呈现格式**：
```
高危操作（destructive）: X 处
宿主集成（filesystem）: X 处
密钥暴露（secrets）: X 处
联网行为（network）: X 处
需人工确认（manualReview）: X 项
```

## 审查结果速查

| recommendation | 含义 | 关键信号 | 下一步 |
|----------------|------|---------|--------|
| `allow` | 无阻断风险 | findings 为空或仅 low | 可进入 skill-installer 或手工分发 |
| `review_needed` | 中高风险 | 含 high 或 medium 的 symlink/host_execution/network | 人工复核 findings 后再决定 |
| `block` | 高危 | 含 critical（rm -rf、git reset --hard、curl\|sh） | 不建议继续，除非完全理解风险 |

**快速判断**：
- `destructiveOps` 非空 → 至少 `review_needed`，有 critical 则 `block`
- `filesystemWrites` 含宿主目录 → `review_needed`
- `secretHits` + `networkDbAccess` 同时存在 → `review_needed`
- `autoActionHits` 非空 → `review_needed`

## 门禁与降级
- 如果目标 skill 带安装脚本、宿主目录写入、软链接覆盖或联网 bootstrap，默认至少 `review_needed`。
- 如果发现高危命令、远程管道执行或明显覆盖宿主目录的 destructive 行为，默认 `block`。

## References
- 审查清单：`references/checklist.md`
- 风险模型：`references/risk-model.md`
- 决策矩阵：`references/decision-matrix.md`

## Guardrails
- 不执行被审查 skill 的任何脚本或安装命令。
- 不因为“看起来能用”就跳过风险说明。
- 不把静态审查结果写成绝对安全结论；只能给当前证据下的建议等级。
- 不替用户自动安装、自动软链接或自动覆盖宿主目录。
- 涉及代码、注释、文档或提交时，署名遵守全局规则：不用 AI，统一用 `anfeng`。

## Output
使用简体中文，先给结论：推荐等级 → 关键风险 → 需要人工复核的点 → 下一步建议。

### 示例
```
**推荐等级**：review_needed

**关键风险**：
- [high] system_execution: scripts/cli/adapters.py:168 → subprocess.run(cmd, shell=True)
- [high] host_integration: scripts/cli/README.md:49 → 写入 ~/.claude/skills 路径
- [medium] network_access: 95 处主动联网调用（requests.post/fetch）

**需要人工复核**：
1. shell=True 的 cmd 是否来自用户可控输入
2. 宿主目录写入是否为预期行为（如 yt-dlp cookie 配置）
3. 95 处联网调用是否全部有适当的 API Key 管理和限流策略

**下一步建议**：
- 如果仅个人本地使用：风险可控，可继续安装
- 如果团队分发：建议先处理 shell=True 和宿主路径硬编码
```
