---
name: skill-installer
description: "需要把本地 skill 安装到 active 源目录，或同步 active skills 到 Codex、Claude、Junie、Agents、Hermes 时使用。"
metadata:
  author: anfeng
  version: "0.2.1"
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
- active 源目录和选定宿主链接要么同步成功，要么给出精确冲突。
- 证据包含 source root、目标工具、dry-run JSON、冲突状态、apply 后验证。
- 所有 apply 必须来自用户明确要求或已批准方案，并二次验证。

## 源和目标
- 源目录默认 active repo root；只用 `--source-root`、`AI_SKILLS_HOME` 或 config 覆盖。
- 目标工具白名单：`codex`、`claude`、`junie`、`agents`、`hermes`。
- macOS/Linux 使用 symlink；Windows 需要时使用 junction。
- Hermes 优先 `skills.external_dirs`；目录级 symlink 只作兼容。
- 配置路径：macOS/Linux 用 `$XDG_CONFIG_HOME/skill-installer/config.json` 或 `~/.config/skill-installer/config.json`；Windows 用 `%APPDATA%\\skill-installer\\config.json`。
- 宿主目录固定在 `AI_HOST_HOME`（默认 home）下：`.codex/skills`、`.claude/skills`、`.junie/skills`、`.agents/skills`、`.hermes/skills`。

## 工作流
安装外部本地 skill 到 active 源：
```bash
node bin/skill-installer.mjs install /absolute/path/to/skill --json
node bin/skill-installer.mjs install /absolute/path/to/skill --apply
```

迁移根级 skill 到 `skills/{category}/`：
```bash
node bin/skill-installer.mjs migrate --json
node bin/skill-installer.mjs migrate --apply
```

审计或同步宿主链接：
```bash
node bin/skill-installer.mjs --json
node bin/skill-installer.mjs --skill web-access --skill skill-installer --json
node bin/skill-installer.mjs --tool codex --tool claude --skill web-access --json
node bin/skill-installer.mjs --tool codex --skill web-access --apply
```

任何真实变更前先 dry-run。只有用户明确要求 apply，或已批准方案点名 apply，才执行。

## 安装分类
- `--category` 省略时默认 `auto`。
- 匹配优先级：kingdee -> automation -> meta -> core -> tags 派生 -> incoming。
- tag 可派生新分类；无 tag 才进入 `skills/incoming/`。
- `skills/incoming/<skill>` 不参与默认分发；需要人工复核/分类后再同步。
- `install` 只写 active 源目录分类子目录，不直接写宿主目录。

## 状态处理
- `already_linked`、`managed_via_external_dir`：通过。
- `optional_host_unavailable`：默认全量审计中跳过，不阻塞。
- `planned`、`ready_to_migrate`：需要 apply 确认。
- `missing_skill`、`invalid_source`、`missing_target_root`、`target_exists`：路径/源未修好前阻塞。
- `real_path_conflict`、`external_symlink_conflict`、`hermes_local_shadow_conflict`：阻塞；报告精确目标，不覆盖。
- `needs_external_dir_config`：Hermes 需要配置或跳过。
- `needs_review`：install 被归到 `incoming`；审核/分类前不分发。
- `migrated`：根级迁移完成。

## 门禁
- 没有用户要求或已批准 handoff，不加 `--apply`。
- 不删除、不覆盖、不强制 relink、不做清理。
- 不接受白名单外任意目标目录。
- install 只写 active 源目录；host 目录链接由 sync 管。
- apply 后必须再次 dry-run 或检查链接。
- 全量同步、不指定 `--skill`、发现冲突、Hermes 显式缺 external_dirs、migrate 根级 skill 时，先报告范围再执行。

## 输出
简体中文：
- 结论：已同步 / 待 apply / 阻塞。
- 源目录：解析后的 source root 和 skill 名。
- 目标：工具和目标根目录。
- Dry-run：summary 和冲突。
- 执行：实际运行的 apply 命令。
- 验证：apply 后证据。
