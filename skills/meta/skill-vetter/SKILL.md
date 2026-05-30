---
name: skill-vetter
description: "需要审查第三方或 incoming skill 的来源可信度、脚本行为、宿主写入、破坏性命令、密钥暴露或安装风险时使用。"
metadata:
  author: anfeng
  version: "0.2.0"
  license: MIT
  tags: [security, skill, review, static-analysis]
---

# Skill Vetter

> Cross-platform Agent Skill: 只做静态审查；不执行目标脚本，也不安装 incoming skill。

## 触发
- 安装、引入、复用、分发或信任第三方/incoming skill 前使用。
- 输入可以是 skill 根目录、`SKILL.md`、解包仓库路径或 marketplace/download 目录。
- 优化自己的本地 skill 转 `darwin-skill`。
- 审查通过后的安装/同步转 `skill-installer`。

## 契约
- 输出等级只能是 `allow`、`review_needed` 或 `block`。
- 证据来自本地文件、frontmatter、脚本、安装说明、文件系统写入、破坏性命令、网络/密钥模式、人工复核项。
- 必须明确风险等级、阻塞证据、人工检查点和下一步。
- 默认只做静态审查，不联网查信誉，不执行目标脚本。

## 工作流
1. 解析精确 skill root。多个 `SKILL.md` 时停止，让用户指定目标。
2. 从本 skill 目录运行静态检查：
   ```bash
   node scripts/inspect-skill.mjs --path /absolute/path/to/skill --json
   ```
   看人类摘要可去掉 `--json`；自动化门禁需要非 `allow` 失败时加 `--strict`。
3. 先看 `recommendation`，再看 `findings`、`destructiveOps`、`filesystemWrites`、`secretHits`、`networkDbAccess`、`manualReview`。
4. 只有 high/critical 或需要判断意图时，才手动读被引用文件。
5. 判定：
   - `allow`：当前静态证据下无阻断风险。
   - `review_needed`：宿主写入、软链接变更、联网 bootstrap、shell 执行、密钥或中高风险歧义。
   - `block`：破坏性命令、强制覆盖宿主、远程管道执行或明显凭据外泄风险。

## 风险信号
- 破坏性：`rm -rf`、`git reset --hard`、`chmod -R 777`、强制覆盖/删除。
- 远程执行：`curl|sh`、`wget|bash`、不透明安装器。
- 宿主写入：`.codex/skills`、`.claude/skills`、`.agents/skills`、`.junie/skills`、`.hermes/skills`。
- 密钥：token/password/API key、Basic Auth、cookies、env dump。
- 不安全执行：`shell=True`、未校验 subprocess、eval 类路径。
- 本地硬编码：绝对路径、用户 home 假设。

## 结果解读
- 先看 `recommendation`，再按 severity 处理 `findings`：critical > high > medium > low。
- `destructiveOps` 非空：至少 `review_needed`；critical 时 `block`。
- `filesystemWrites` 命中宿主 skills 目录：`review_needed`。
- `secretHits` 和 `networkDbAccess` 同时存在：`review_needed`。
- `autoActionHits` 非空：`review_needed`。
- 输出按 destructive、filesystem、secrets、network、manualReview 分组。

## 门禁
- 不执行目标 skill 的脚本、测试、安装器或生成命令。
- 不说第三方 skill “安全”；只能说“当前静态证据下可继续”。
- 路径不存在、目标不清或无 `SKILL.md` 时停止并说明原因。
- `review_needed` 或 `block` 后用户仍要安装，必须明确接受具名风险。
- 同一目录多个 skill root 时停止，让用户指定目标；不要把整仓风险套到单个子 skill。

## 输出
简体中文：
- 推荐等级：allow / review_needed / block。
- 关键风险：severity、file:line、影响。
- 人工复核：未解决的具体检查点。
- 下一步：安装/同步、拒绝或先修复。

## 参考资料
- 审查清单：`references/checklist.md`
- 风险模型：`references/risk-model.md`
- 决策矩阵：`references/decision-matrix.md`
