---
name: skill-installer
description: Skills 目录分发：软链接同步到多 AI 工具，支持审计和冲突检测。
metadata:
  author: anfeng
  version: "0.2.1"
  license: MIT
  tags: [skills, symlink, sync, distribution]
---

# Skill Installer

> **Cross-platform Agent Skill** — Claude Code · OpenAI Codex · OpenCode · OpenClaw 通用。
> 跨平台 SKILL.md，遵循开放 Agent Skill 规范。

## 触发边界
- 用户要安装、同步、卸载本地 skill 到多个 AI 工具，检查软链接是否正确，补齐缺失链接，预览将发生的链接变化时使用。
- 只修改单个 skill 内容、不涉及分发目录时不要触发。
- 只做市场安装或远程下载但不落入 active 源目录时不要触发；本 skill 只管 active 源目录和各工具 skills 目录之间的安装与分发。

## 默认事实源
- 源目录默认是当前 active 仓库根目录；可用 `--source-root`、`AI_SKILLS_HOME` 或 `skill-installer/config.json` 覆盖
- v1 目标目录固定为 `AI_HOST_HOME`（默认当前系统 home）下的：
  - `.codex/skills`
  - `.claude/skills`
  - `.junie/skills`
  - `.agents/skills`
  - `.hermes/skills`

跨平台配置文件：
- macOS/Linux：`$XDG_CONFIG_HOME/skill-installer/config.json`，无 XDG 时用 `~/.config/skill-installer/config.json`
- Windows：`%APPDATA%\skill-installer\config.json`
- Windows 分发目录链接使用 junction；macOS/Linux 使用 symlink

其中 Hermes 例外：
- Hermes 技能发现优先走 `~/.hermes/config.yaml` 里的 `skills.external_dirs`
- 不再推荐给 Hermes 创建“skill 目录本身就是软链接”的分发方式
- `~/.hermes/skills` 里的旧软链接只作为兼容保留，不再作为 Hermes 主发现路径

## 快速工作流
### 安装 skill

1. 任何 AI 工具安装 skill 时，只能安装到 active 源目录，不要直接写宿主目录：
   - 不要直接写 `~/.codex/skills`
   - 不要直接写 `~/.claude/skills`
   - 不要直接写 `%USERPROFILE%\.codex\skills`
2. 默认先 dry-run：
   ```bash
   node bin/skill-installer.mjs install ./my-skill --category auto --json
   ```
3. 确认 `category / targetPath / status` 后再 apply：
   ```bash
   node bin/skill-installer.mjs install ./my-skill --category meta --apply
   ```
4. 分类规则：
   - 明确分类时使用 `--category core|automation|kingdee|meta`
   - 不确定时使用 `--category auto`
   - 自动分类失败会放入 `skills/incoming/<skill>`，不会自动分发

### 同步 skill

1. 先确认源 skill 是否存在且包含 `SKILL.md`。
2. 默认先跑 dry-run，不直接改链接：
   ```bash
   # 全量审计
   node bin/skill-installer.mjs --json
   
   # 指定 skill
   node bin/skill-installer.mjs --skill web-access --skill skill-installer --json
   
   # 指定工具和 skill
   node bin/skill-installer.mjs --tool codex --tool claude --skill web-access --json
   ```

3. 读 dry-run 输出，确认 `action / status / reason` 没有冲突。
   对于 Hermes，重点看：
   - `managed_via_external_dir`：正常，说明 Hermes 已通过 `skills.external_dirs` 接入
   - `optional_host_unavailable`：默认全量审计中 Hermes 未安装或未配置，跳过且不阻塞其他工具
   - `needs_external_dir_config`：显式指定 `--tool hermes` 时，源目录还没配进 `~/.hermes/config.yaml`
   - `hermes_local_shadow_conflict`：本地 `~/.hermes/skills/<skill>` 有真实目录或错误链接，会遮住 external dir

4. 只有在用户确认后，才执行真实链接变更：
   ```bash
   node bin/skill-installer.mjs --tool codex --tool hermes --skill web-access --skill skill-installer --apply
   ```

5. 执行后再次 dry-run 验证结果是否幂等；需要查看链接时使用当前平台的目录查看命令。
   Hermes 场景下，再额外验证一次 slash 命令或 `skills_list` 是否能发现目标 skill。

## 预期行为
- 默认 `dry-run`
- 只管理 5 个白名单工具目录，不接受任意自定义输出目录
- 只管理源自当前 active 仓库根目录 `<source-root>/<skill>` 且带 `SKILL.md` 的 skill
- `skills/incoming/<skill>` 不参与默认分发
- `install` 只写入 active 源目录的分类子目录，不直接写宿主工具目录
- 对 Codex/Claude/Junie/Agents 只创建新软链接；已存在但指向外部来源的软链接视为冲突，不自动改写
- 对 Hermes 不创建新的目录级软链接；默认全量审计中未配置 Hermes 只记为 optional host skip，显式指定 `--tool hermes` 时才要求校验 `skills.external_dirs`
- 同名真实目录或真实文件视为冲突，停止并报告
- 已经正确链接的目标只记为 `noop`
- 允许按 skill 名称和白名单工具范围过滤

## 用户确认检查点

| 场景 | 停住确认内容 |
|------|-------------|
| dry-run 后有 `planned` 链接 | "计划创建/更新 {N} 个软链接，涉及 {tools}，确认执行 apply？" |
| dry-run 发现冲突（real_path_conflict / external_symlink_conflict） | "发现 {N} 个冲突，不自动覆盖。请确认处理方式后再执行。" |
| 默认全量审计显示 `optional_host_unavailable` | 不需要停住；该宿主未配置，不阻塞其他工具 |
| 显式指定 Hermes 显示 `needs_external_dir_config` | "Hermes 未配置 external_dirs；如需使用 Hermes，请先配 ~/.hermes/config.yaml。" |
| 用户要求覆盖冲突 | "冲突覆盖不可逆，确认手动处理以下路径：{paths}" |
| 全量同步（不指定 --skill） | "将同步所有 {N} 个 skill 到 {tools}，确认执行？" |
| install 目标为 `incoming` | "自动分类不确定，已计划放入 incoming，不会分发，确认是否 apply？" |

## 边界与回退

| 异常 | 处理 |
|------|------|
| 源目录不存在 | 报告路径不存在，停止 |
| install 源目录无 `SKILL.md` | `invalid_source`，停止 |
| install 目标目录已存在 | `target_exists`，不覆盖 |
| 默认全量审计中目标工具目录不存在 | `optional_host_unavailable`，跳过该工具 |
| 显式指定工具时目标目录不存在 | `missing_target_root`，报告并跳过该工具 |
| 已存在外部来源软链接 | `external_symlink_conflict`，不覆盖，等用户决定 |
| 已存在真实目录/文件 | `real_path_conflict`，不覆盖，等用户决定 |
| Hermes 本地 shadow 冲突 | `hermes_local_shadow_conflict`，报告会遮住 external_dirs |
| `sync-links.mjs` 执行失败 | 报告脚本错误，检查 Node.js 环境和文件权限 |
| apply 后验证失败 | 用 `ls -l` 或再次 dry-run 确认，报告差异 |

## Guardrails
- 未经用户确认，不执行 `--apply`。
- 不覆盖真实目录或真实文件；发现冲突后先报告，再等用户决定。
- 不把外部来源软链接自动改写成 active 来源；先报告现状，再由用户决定是否人工处理。
- 不把市场、缓存、vendor 或来源不明的 skills 目录当作默认分发目标。
- 不删除用户未选中的 skill 链接，也不清空整目录。
- 涉及代码、注释、文档或提交时，署名遵守全局规则：不用 AI，统一用 `anfeng`。

## 状态速查

| status | 含义 | 是否需要用户处理 |
|--------|------|----------------|
| `already_linked` | 已正确链接到 active | 否 |
| `managed_via_external_dir` | Hermes 通过 external_dirs 接入 | 否 |
| `optional_host_unavailable` | 默认全量审计中宿主未安装或未配置 | 否 |
| `planned` | 目标缺失，计划创建链接 | 是（需确认后 apply） |
| `missing_skill` | 源目录无此 skill | 是（检查路径/名称） |
| `invalid_source` | 源目录存在但无 SKILL.md | 是（检查 skill 完整性） |
| `missing_target_root` | 显式指定的目标工具目录不存在 | 是（创建目录或跳过） |
| `real_path_conflict` | 目标存在真实目录/文件 | 是（不自动覆盖） |
| `external_symlink_conflict` | 目标软链接指向外部来源 | 是（需人工决定是否改写） |
| `hermes_local_shadow_conflict` | Hermes 本地目录遮住 external_dirs | 是（清理本地 shadow） |
| `needs_external_dir_config` | 显式指定 Hermes 时未配置 external_dirs | 是（配 config.yaml 或跳过 Hermes） |
| `target_exists` | install 目标目录已存在 | 是（改名或人工处理） |
| `needs_review` | install 进入 incoming | 是（人工审核后移动分类） |

## Output
使用简体中文，先给结论：源目录 → 目标目录 → dry-run 结果 → 待确认动作 → 执行后验证与风险。

支持两种输出格式：
- **表格格式**（默认）：终端展示，人类可读
- **JSON 格式**（`--json`）：脚本解析，自动化集成

### 示例 1：表格格式（终端展示）
```
**结论**：web-access 已同步到 codex/claude，junie/agents 待补链接，Hermes 通过 external_dirs 管理。

**dry-run 结果**：
| 工具 | 动作 | 状态 |
|------|------|------|
| codex | noop | already_linked |
| claude | noop | already_linked |
| junie | create_link | planned |
| agents | create_link | planned |
| hermes | noop | managed_via_external_dir |

**待确认动作**：
- 补 junie + agents 的软链接（2 个）
- 执行：node bin/skill-installer.mjs --tool junie --tool agents --skill web-access --apply

**验证**：
- apply 后运行 ls -l ~/.junie/skills/web-access ~/.agents/skills/web-access
- Hermes 验证：检查 slash 命令或 skills_list 能否发现 web-access

**风险**：
- 无冲突，幂等操作
```

### 示例 2：JSON 格式（脚本解析）
```json
{
  "ok": true,
  "summary": {
    "total": 5,
    "already_linked": 2,
    "planned": 2,
    "managed_via_external_dir": 1,
    "conflicts": 0
  },
  "records": [
    {
      "tool": "codex",
      "skill": "web-access",
      "status": "already_linked",
      "action": "noop",
      "targetPath": "/Users/you/.codex/skills/web-access"
    },
    {
      "tool": "junie",
      "skill": "web-access",
      "status": "planned",
      "action": "create_link",
      "targetPath": "/Users/you/.junie/skills/web-access"
    }
  ]
}
```
