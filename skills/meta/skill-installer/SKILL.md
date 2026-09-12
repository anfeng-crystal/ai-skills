---
name: skill-installer
description: "将本地 Skill 安装到统一源、同步到选定宿主，或诊断分发与链接漂移；不负责下载远程 Skill。"
license: MIT
metadata:
  author: "anfeng"
  version: "0.3.1"
  tags: "skills, symlink, sync, distribution"
---

# Local Skill Distribution

> Cross-platform Agent Skill: 审计显式 dry-run；安装与同步按入口语义执行授权范围内动作，不覆盖冲突目标。

## 触发
- 安装、同步、迁移、分发审计、缺失软链接检查、宿主 skill 目录漂移时使用。
- 只改 skill 内容时不用。本入口负责统一源和跨宿主分发；系统同名 `skill-installer` 负责 curated/GitHub 下载，先区分任务，不能向错误入口试参数。
- 第三方 skill 安全审查先用 `skill-vetter`。

## 契约
- skills 源目录和选定宿主链接要么同步成功，要么给出精确冲突。
- 证据包含 source root、目标工具、dry-run JSON、冲突状态、apply 后验证。
- apply 由用户请求或已批准方案授权；完成后验证实际 source tree 和宿主链接。

## 按任务选择入口

- 运行安装、同步、链接审计或 doctor：读 [入口、参数与目标](references/commands-and-targets.md)，解析 source root、active root 和选定宿主，再执行对应入口。
- Hermes 同名入口、`external_dirs` 或重复安装疑问：读 [Hermes 排障](references/hermes.md)。
- 只改正文无需分发。审计使用显式 `--dry-run` 或只读 doctor；安装请求已覆盖目标时，核对计划后完成 apply 和验证，不逐阶段追加确认。

## 工作流与状态处理
- `already_linked`、`managed_via_external_dir`：通过。
- `optional_host_unavailable`：默认全量审计中跳过，不阻塞。
- `planned`、`ready_to_migrate`：核对待应用计划；既有授权覆盖精确目标与动作时继续，否则请求缺失授权。
- `missing_skill`、`invalid_source`、`missing_target_root`、`target_exists`：路径/源未修好前阻塞对应对象及依赖操作。
- `real_path_conflict`、`external_symlink_conflict`、`hermes_local_shadow_conflict`：阻塞对应对象及依赖操作；报告精确目标，不覆盖。旧 `active/skills` 托管软链接会规划为 `replace_link`。
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

### 冲突与独立目标

- Hermes 同名入口、真实目录/外部链接冲突、缺少 `external_dirs` 或 `incoming` 未审核时，报告精确对象并停止对应对象及依赖操作，不覆盖、不递归删除；废弃 skill 由源目录的正常变更流程处理。
- 现有入口能独立选定、且授权与检查均完整的其他目标继续完成。共享前置条件失效或入口只能原子执行时，停止该批次并说明具体依赖，不通过拆分规避原有门禁。

## 输出
简体中文：
- 结论：按目标分别报告已同步 / 待 apply / 阻塞，不以一个目标的阻塞代替其他目标的结果。
- 源目录：解析后的 source root 和 skill 名。
- 目标：工具和目标根目录。
- Dry-run：summary 和冲突。
- 执行：实际运行的 apply 命令，以及 source tree / 宿主链接分别是否写入。
- 验证：apply 后证据。
