---
name: skill-installer
description: "需要把本地 skill 安装到统一源目录，或同步到 Codex、Claude Code、OpenCode、Grok Build、Junie、Agents、Hermes 等宿主时使用。"
license: MIT
metadata:
  author: "anfeng"
  version: "0.3.1"
  tags: "skills, symlink, sync, distribution"
---

# Skill Installer

> Cross-platform Agent Skill: 审计显式 dry-run；安装与同步按入口语义执行授权范围内动作，不覆盖冲突目标。

## 触发
- 安装、同步、迁移、分发审计、缺失软链接检查、宿主 skill 目录漂移时使用。
- 只改 skill 内容时不用。
- 第三方 skill 安全审查先用 `skill-vetter`。

## 契约
- skills 源目录和选定宿主链接要么同步成功，要么给出精确冲突。
- 证据包含 source root、目标工具、dry-run JSON、冲突状态、apply 后验证。
- 所有 apply 必须来自用户明确要求或已批准方案，并二次验证。

## 源和目标
- 源目录优先来自 `--source-root`、`AI_SKILLS_HOME`、config 或当前 source tree；不要在 skill 规则里写死某台机器的 home 路径。
- 目标工具白名单：`codex`、`claude`、`claude-code`、`junie`、`agents`、`hermes`、`qoder`、`qoderwork`、`workbuddy`、`trae`、`openclaw`、`opencode`、`antigravity`、`antigravity-cli`、`antigravity-desktop`。
- macOS/Linux 使用 symlink；Windows 需要时使用 junction。
- Hermes 优先 `skills.external_dirs`；目录级 symlink 只作兼容。
- 配置路径：macOS/Linux 用 `$XDG_CONFIG_HOME/skill-installer/config.json` 或 `~/.config/skill-installer/config.json`；Windows 用 `%APPDATA%\\skill-installer\\config.json`。
- 宿主目录固定在 `AI_HOST_HOME`（默认 home）下：`.codex/skills`、`.claude/skills`、`.junie/skills`、`.agents/skills`、`.hermes/skills`、`.qoder/skills`、`.qoderwork/skills`、`.workbuddy/skills`、`.trae/skills`、`.openclaw/workspace/skills`、`.config/opencode/skills`。
- `grok` / `grok-build` 显式目标复用 Agent Skills 公共用户目录 `.agents/skills`，不另造一份 Grok 专用副本。

## 入口脚本（四个相关入口）

active checkout 下有四个相关入口。`sync-and-install.mjs` 是同步安装主入口；根 `install.mjs` 默认 `apply`/安装，审计必须显式 `--dry-run`；内部 CLI 位于 skills source root 下的 `meta/skill-installer/bin/skill-installer.mjs`，其 `install` 子命令用 plan/apply 分离预览、source tree 写入和宿主链接同步。

命令中的 `<skills-root>` 必须解析为包含分类目录（如 `core/`、`meta/`）的 skills source root；`<active-root>` 是它的父目录，包含 `install.mjs` 和 `scripts/`。二者都不是当前已安装 skill 目录（例如 `~/.codex/skills/skill-installer`）。优先使用 `AI_SKILLS_HOME` 作为 `<skills-root>`；没有环境变量时，从当前 `SKILL.md` 的安装路径不能可靠反推出源目录，应让用户显式提供 `--source-root`，不要猜测。

| 脚本 | 用途 | 执行顺序 |
|------|------|----------|
| `<active-root>/scripts/sync-and-install.mjs` | **主入口**：pull → install → doctor | 三合一 |
| `<active-root>/install.mjs` | 安装；带 `--dry-run` 时审计 | 仅步骤 2 |
| `<skills-root>/meta/skill-installer/bin/skill-installer.mjs` | `install` 默认只生成安装计划；`--apply` 写 source tree，并按分类决定是否同步宿主链接 | 按参数 |
| `<active-root>/scripts/doctor.mjs` | 健康诊断（`--source-root` + `--home`） | 仅步骤 3 |

### 1. 一站式同步 + 安装 + 诊断（推荐）

```bash
# 先确定 source root；以下命令均使用 source root/active root 的绝对路径。
SKILLS_ROOT="${AI_SKILLS_HOME:?set AI_SKILLS_HOME or pass an explicit skills root}"
ACTIVE_ROOT="$(cd "$SKILLS_ROOT/.." && pwd)"

# dry-run：预览所有操作，不执行
node "$ACTIVE_ROOT/scripts/sync-and-install.mjs" --tool hermes --dry-run

# apply：执行 pull → install → doctor
node "$ACTIVE_ROOT/scripts/sync-and-install.mjs" --tool hermes

# 选项
#   --home <path>     目标宿主 HOME（默认 $AI_HOST_HOME 或 OS home）
#   --tool <name>     限定目标工具（可重复）
#   --skill <name>    限定目标 skill（可重复）
#   --skip-doctor     跳过诊断
#   --no-pull         跳过 git pull（远端已最新时用）
#   --dry-run         仅打印计划，不执行
```

### 2. 仅安装 / 审计链接

```bash
# 审计 Hermes 链接（显式不 apply）
node "$ACTIVE_ROOT/install.mjs" --home "$HOME" --tool hermes --dry-run

# 根 install.mjs 默认安装；--dry-run 才审计；两者不要混用
node "$ACTIVE_ROOT/install.mjs" --home "$HOME"
node "$ACTIVE_ROOT/install.mjs" --home "$HOME" --dry-run

# bin 的 install 先生成计划；确认后只对选定宿主 apply
node "$SKILLS_ROOT/meta/skill-installer/bin/skill-installer.mjs" install /path/to/local-skill \
  --source-root "$SKILLS_ROOT" --category auto --tool codex
node "$SKILLS_ROOT/meta/skill-installer/bin/skill-installer.mjs" install /path/to/local-skill \
  --source-root "$SKILLS_ROOT" --category auto --tool codex --apply

# 不指定 --tool 可能把已选分类同步到更大的宿主范围；需要明确收窄时始终指定它。
```

### 3. 仅医生诊断

```bash
node "$ACTIVE_ROOT/scripts/doctor.mjs" --source-root "$SKILLS_ROOT" --home "$HOME"
```

审计命令必须带 `--dry-run`。真实安装、同步或 pull 只有用户明确要求或已批准方案点名时才执行；执行前确认范围，执行后再次 dry-run 或检查链接。

## 安装分类
- `--category` 省略时默认 `auto`。
- 匹配优先级：kingdee -> automation -> meta -> core -> tags 派生 -> incoming。
- tag 可派生新分类；无 tag 才进入 `incoming/`。
- `incoming/<skill>` 不参与默认分发；需要人工复核/分类后再同步。
- 内部 CLI 的 `install <source>` 无 `--apply` 只生成安装计划，不写 source tree 或宿主目录。
- `install <source> --apply` 先复制到 source tree 的分类子目录；分类不是 `incoming` 时，再构造并 apply 选定宿主链接；对于 `incoming` 分类，apply 仅完成 source tree 写入，不默认分发。

## 工作流与状态处理
- `already_linked`、`managed_via_external_dir`：通过。
- `optional_host_unavailable`：默认全量审计中跳过，不阻塞。
- `planned`、`ready_to_migrate`：需要 apply 确认。
- `missing_skill`、`invalid_source`、`missing_target_root`、`target_exists`：路径/源未修好前阻塞。
- `real_path_conflict`、`external_symlink_conflict`、`hermes_local_shadow_conflict`：阻塞；报告精确目标，不覆盖。旧 `active/skills` 托管软链接会规划为 `replace_link`。
- `orphan_link`：全量同步中发现指向当前 source root 内部但目标已不存在的托管 symlink；`--apply` 时只删除该 symlink。
- `needs_external_dir_config`：Hermes 需要配置或跳过。
- `needs_review`：install 被归到 `incoming`；审核/分类前不分发。
- `migrated`：根级迁移完成。

## 门禁
- 没有用户要求或已批准 handoff，不执行真实安装、同步或 pull；内部 CLI 的 `install` 先看无 `--apply` 计划，再按确认范围执行 `--apply`。
- 不删除真实目录、外部链接或未知文件；只清理可证明指向当前 source root 内部的断裂托管 symlink。
- 不接受白名单外任意目标目录。
- 根 `install.mjs` 只有显式 `--dry-run` 才审计，默认行为是 apply；`--dry-run` 与 `--apply` 不应混用。
- 内部 CLI 的 `install` 无 `--apply` 不写入；`--apply` 写入 source tree，并仅为非 `incoming` 分类 apply 选定宿主链接。
- apply 后必须再次 dry-run 或检查链接。
- 全量同步、不指定 `--skill`、发现冲突、Hermes 显式缺 external_dirs、migrate 根级 skill 时，先报告范围再执行。

## 陷阱

### Hermes external_dirs 下同名 skill 分别在根目录和分类子目录会触发 ambiguous skill 错误
源目录中如果同时存在 `<skill>/SKILL.md` 和 `skills/<category>/<skill>/SKILL.md` 两个同名入口，Hermes 扫描会报 ambiguous skill 并阻塞 `skill_view` 和技能加载。
- **修复**：从源目录删除/合并重复入口，只保留一个 SKILL.md。分类目录优先，避免裸根 duplication。
- **注意**：这不是 install/sync 脚本能自动处理的，需要在源技能仓库归一化 skill 的位置。

### Hermes `external_dirs` 模式下无需"重新安装"
如果 `~/.hermes/config.yaml` 的 `skills.external_dirs` 已指向源目录，Hermes 直接从源目录实时读取技能——远端更新拉取后自动生效。此时 `install.mjs` 会报告所有技能为 `managed_via_external_dir` / `wouldChange: 0`，不需要也不应该做额外安装或 symlink 操作。

### 稳定异常门禁

- Hermes 同名入口、真实目录/外部链接冲突、缺少 `external_dirs` 或 `incoming` 未审核时，报告精确对象并停止，不覆盖、不递归删除；废弃 skill 由源目录的正常变更流程处理。

## 输出
简体中文：
- 结论：已同步 / 待 apply / 阻塞。
- 源目录：解析后的 source root 和 skill 名。
- 目标：工具和目标根目录。
- Dry-run：summary 和冲突。
- 执行：实际运行的 apply 命令，以及 source tree / 宿主链接分别是否写入。
- 验证：apply 后证据。
