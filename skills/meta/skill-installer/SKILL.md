---
name: skill-installer
description: "需要把本地 skill 安装到统一源目录，或同步 skills 到 Codex、Claude、Junie、Agents、Hermes 时使用。"
metadata:
  author: anfeng
  version: "0.3.1"
  license: MIT
  tags: [skills, symlink, sync, distribution]
---

# Skill Installer

> Cross-platform Agent Skill: 先 dry-run 再 apply；不自动覆盖真实文件或外部来源 skill 链接。

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
- 宿主目录固定在 `AI_HOST_HOME`（默认 home）下：`.codex/skills`、`.claude/skills`、`.junie/skills`、`.agents/skills`、`.hermes/skills`、`.qoder/skills`、`.qoderwork/skills`、`.workbuddy/skills`、`.trae/skills`、`.openclaw/workspace/skills`、`.opencode/skills`。

## 入口脚本（三个入口）

源目录根 (`active/`) 下有三个入口，**推荐使用 `sync-and-install.mjs` 一站式完成**：

| 脚本 | 用途 | 执行顺序 |
|------|------|----------|
| `scripts/sync-and-install.mjs` | **主入口**：pull → install → doctor | 三合一 |
| `install.mjs` | 链接审计 / 安装（`--home` + `--tool`） | 仅步骤 2 |
| `scripts/doctor.mjs` | 健康诊断（`--source-root` + `--home`） | 仅步骤 3 |

### 1. 一站式同步 + 安装 + 诊断（推荐）

```bash
# dry-run：预览所有操作，不执行
node scripts/sync-and-install.mjs --tool hermes --dry-run

# apply：执行 pull → install → doctor
node scripts/sync-and-install.mjs --tool hermes

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
# 审计 Hermes 链接（不 apply）
node install.mjs --home "$HOME" --tool hermes

# 审计所有宿主 + apply
node install.mjs --home "$HOME" --json --apply
```

### 3. 仅医生诊断

```bash
node scripts/doctor.mjs --source-root /path/to/skill-source-root --home "$HOME"
```

任何真实变更前先 dry-run。只有用户明确要求 apply，或已批准方案点名 apply，才执行。

## 安装分类
- `--category` 省略时默认 `auto`。
- 匹配优先级：kingdee -> automation -> meta -> core -> tags 派生 -> incoming。
- tag 可派生新分类；无 tag 才进入 `incoming/`。
- `incoming/<skill>` 不参与默认分发；需要人工复核/分类后再同步。
- `install` 只写源目录分类子目录，不直接写宿主目录。

## 状态处理
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
- 没有用户要求或已批准 handoff，不加 `--apply`。
- 不删除真实目录、外部链接或未知文件；只清理可证明指向当前 source root 内部的断裂托管 symlink。
- 不接受白名单外任意目标目录。
- install 只写源目录；host 目录链接由 sync 管。
- apply 后必须再次 dry-run 或检查链接。
- 全量同步、不指定 `--skill`、发现冲突、Hermes 显式缺 external_dirs、migrate 根级 skill 时，先报告范围再执行。

## 陷阱

### Hermes external_dirs 下同名 skill 分别在根目录和分类子目录会触发 ambiguous skill 错误
源目录中如果存在 `neat-freak/SKILL.md` 和 `skills/meta/neat-freak/SKILL.md` 两个入口，Hermes 扫描时会报 `Ambiguous skill name 'neat-freak': 2 skills match across your local skills dir and external_dirs.`，直接阻塞 `skill_view` 和技能加载。
- **修复**：从源目录删除/合并重复入口，只保留一个 SKILL.md。分类目录优先，避免裸根 duplication。
- **注意**：这不是 install/sync 脚本能自动处理的，需要在源技能仓库归一化 skill 的位置。

### `git stash push -u` 会吞噬未提交的新脚本
`sync-and-install.mjs`、`install.mjs` 等新增脚本如果在工作区但尚未 `git add`，`git stash push -u`（含 untracked）会把它们藏进 stash 并从工作区删除，导致后续 `node scripts/sync-and-install.mjs` 报 `MODULE_NOT_FOUND`。
- **修复**：`git stash pop` 恢复。
- **预防**：清理前先用 `git status` 确认未跟踪文件列表；或用 `git stash`（不含 `-u`）。

### Hermes `external_dirs` 模式下无需"重新安装"
如果 `~/.hermes/config.yaml` 的 `skills.external_dirs` 已指向源目录，Hermes 直接从源目录实时读取技能——远端更新拉取后自动生效。此时 `install.mjs` 会报告所有技能为 `managed_via_external_dir` / `wouldChange: 0`，不需要也不应该做额外安装或 symlink 操作。

### 废弃旧技能：源目录删掉即可
当旧技能被新技能取代（如 `skill-linker` → `skill-installer`）且 Hermes 使用 `external_dirs` 时，直接从源目录删除旧技能目录（`rm -rf <source>/skills/<category>/<old-skill>`）即可移除。不需要运行 install/sync 脚本——下一次 Hermes 扫描就会自动消失。确认已无 cron 引用后提交源仓库。

## 输出
简体中文：
- 结论：已同步 / 待 apply / 阻塞。
- 源目录：解析后的 source root 和 skill 名。
- 目标：工具和目标根目录。
- Dry-run：summary 和冲突。
- 执行：实际运行的 apply 命令。
- 验证：apply 后证据。
