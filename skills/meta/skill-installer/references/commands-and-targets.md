# 本地分发入口与目标

执行安装、同步、链接审计或 doctor 前，按任务选择下方入口；不要求运行全部入口。

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

命令中的 `<skills-root>` 必须解析为包含分类目录（如 `core/`、`meta/`）的 skills source root；`<active-root>` 是它的父目录，包含 `install.mjs` 和 `scripts/`。二者都不是当前已安装 skill 目录（例如 `~/.codex/skills/skill-installer`）。优先使用 `AI_SKILLS_HOME` 作为 `<skills-root>`；无明确配置时可解析安装入口的真实软链接目标，并核对分类目录、`install.mjs` 与 `scripts/doctor.mjs`；不能唯一确定时才询问 `--source-root`，不按目录名猜测。

| 脚本 | 用途 | 执行顺序 |
|------|------|----------|
| `<active-root>/scripts/sync-and-install.mjs` | **主入口**：pull → install → doctor | 三合一 |
| `<active-root>/install.mjs` | 安装；带 `--dry-run` 时审计 | 仅步骤 2 |
| `<skills-root>/meta/skill-installer/bin/skill-installer.mjs` | `install` 默认只生成安装计划；`--apply` 写 source tree，并按分类决定是否同步宿主链接 | 按参数 |
| `<active-root>/scripts/doctor.mjs` | 健康诊断（`--source-root` + `--home`） | 仅步骤 3 |

### 1. 一站式同步 + 安装 + 诊断（推荐）

先按“入口脚本”中的解析规则确定 source root 和 active root。以下是跨平台参数示意：`<node>` 是已核实的 Node 可执行文件，`<host-home>` 是目标用户目录；优先进程参数数组传参。使用 shell 时按实际 shell 引用含空格路径，PowerShell 调用带引号的可执行文件用 `&`，不依赖 Bash 变量展开或命令替换。

```text
# dry-run：预览所有操作，不执行
<node> <active-root>/scripts/sync-and-install.mjs --tool hermes --dry-run

# apply：执行 pull → install → doctor
<node> <active-root>/scripts/sync-and-install.mjs --tool hermes

# 选项
#   --home <path>     目标宿主 HOME（默认 $AI_HOST_HOME 或 OS home）
#   --tool <name>     限定目标工具（可重复）
#   --skill <name>    限定目标 skill（可重复）
#   --skip-doctor     跳过诊断
#   --no-pull         跳过 git pull（远端已最新时用）
#   --dry-run         仅打印计划，不执行
```

### 2. 仅安装 / 审计链接

```text
# 审计 Hermes 链接（显式不 apply）
<node> <active-root>/install.mjs --home <host-home> --tool hermes --dry-run

# 根 install.mjs 默认安装；--dry-run 才审计；两者不要混用
<node> <active-root>/install.mjs --home <host-home>
<node> <active-root>/install.mjs --home <host-home> --dry-run

# bin 的 install 先生成计划；确认后只对选定宿主 apply
<node> <skills-root>/meta/skill-installer/bin/skill-installer.mjs install <local-skill> --source-root <skills-root> --category auto --tool codex
<node> <skills-root>/meta/skill-installer/bin/skill-installer.mjs install <local-skill> --source-root <skills-root> --category auto --tool codex --apply

# 不指定 --tool 可能把已选分类同步到更大的宿主范围；需要明确收窄时始终指定它。
```

### 3. 仅医生诊断

```text
<node> <active-root>/scripts/doctor.mjs --source-root <skills-root> --home <host-home>
```

安装/同步入口用于审计时必须带 `--dry-run`；doctor 本身是只读诊断，无须不存在的参数。真实安装、同步或 pull 只有用户明确要求或已批准方案点名时才执行；执行前确认范围，执行后再次 dry-run 或检查链接。

内部 CLI 拒绝同时传入 `--dry-run` 和 `--apply`，参数错误返回退出码 `1`。未知长选项（如 `--dryrun`）和未支持的等号写法（如 `--tool=codex`）在执行前报参数错误；带值选项使用 `--tool codex` 形式，错误只回显参数名。同步、`install`、`remove`、`migrate` 的已识别冲突返回退出码 `2`，包括只读预览；调用方仍须检查 JSON 的具体状态。`remove` 指定白名单外工具时阻塞该批次，不执行链接删除或 `--purge`。

`diff` 的获取/本地文件失败、`update` 的获取失败和 `--check-updates` 的检查失败返回 `2`；未记录上游或有效本地源仍是可识别的跳过/成功状态。`update --all` 保留检查失败证据，即使没有可更新项也不报告成功。`history` 文件不存在时返回空结果；其他读取错误返回 `1`，不伪装成空历史。

`--check-updates` 未指定 Skill 及 `update --all` 复用分发入口的源发现规则，覆盖根级和分类路径，默认排除隐藏目录和 `incoming/`。`update --sync` 沿用 `--home`、`--tool` 与配置选择目标，执行后重新核对链接；`updated_sync_incomplete` 返回 `2`，表示源已更新而宿主同步未完成。根据 `syncVerification` / `syncError` 修复目标，再用默认同步入口的 `--skill <分类路径> --tool <目标> --apply` 仅重试链接；`update --all` 也在汇总中保留该失败。

`update` / `diff` 先解析来源分支的 commit，再按该 commit 下载一次 `SKILL.md`；版本字段 `lastUpstreamHash` / `upstreamHash` / `toHash` 使用 commit。更新只替换 `SKILL.md`，不更新上游其他脚本或资源。无法解析 commit 或获取内容时返回失败并保留本地源；单项和全量 `update --dry-run` 不写源内容、元数据、历史或宿主链接。

缺少 `lastUpstreamHash` 时，检查返回 `baseline_unknown` 和已查询到的 `upstreamHash`，退出 `2`；不会把远端版本当作本地已安装版本写入，也不会宣称已是最新。先用 `diff <skill>` 核对内容，再按授权显式 `update <skill>`，由成功下载的 commit 建立基线。`update --all` 保留未知对象为 `checkErrors`，继续更新其他已知版本且可更新的对象；dry-run 同样暴露未知状态并保持文件不变。

`--check-updates --only-updatable` 的 `skills` 仅列出可更新项，检查失败（含未知基线）保留在 `checkErrors`，文本输出也展示失败对象和原因。`summary`、`ok` 和退出码仍按全部已检查对象计算；没有可更新项不等于所有检查成功。未加过滤选项时保持完整 `skills` 输出。

单项检查中发生异常（如检查时间无法写入元数据）时，批量结果将该项标记为 `check_failed` 并保留错误 `code`，继续检查后续对象，退出 `2`。`update --all` 也保留该项在 `checkErrors`，只更新检查成功且可更新的对象。

元数据文件缺失仍视为未记录来源；非法 JSON 或其他读取错误不再视为成功跳过。显式 `diff` / `update` 返回 `metadata_read_failed` / `ok:false`，退出 `2`，保留 Skill 和稳定错误码，并继续后续独立对象；检查与 `update --all` 沿用 `check_failed` / `checkErrors`。这些初次读取失败不改源、元数据、历史或链接，也不获取上游内容；原始解析/I/O异常文本不进入结果。合法 JSON 的来源字段仍按既有规则处理，读取器不承担完整元数据 schema 校验。

`migrate --apply` 完成移动后核对选定宿主链接；`migrated_sync_incomplete` 返回 `2` 并保留已移动的源和成功链接。按结果中的新 `targetRelativePath` 修复后只重试同步。零个根级候选时不执行链接同步；迁入 `incoming` 的对象保持待审核。

移动阶段失败返回 `migration_incomplete` / `ok:false`，退出 `2`；逐项 `migrated` 表示已确认移动、`failed` 表示该项操作失败、`planned` 表示尚未尝试，`migrationError` 保留阶段、稳定错误码和源/目标路径。保留已移目录，停止后续移动，仍同步已确认迁移且非 `incoming` 的子集；`synced` 只表示该子集的宿主同步结果，不代表整批迁移成功。迁移和宿主同步异常只记录稳定系统错误码与固定说明，不回显底层异常原文。失败操作不保证目录完全未变，`applied:false` 也不保证没有临时写入；重试前先核对失败项路径与已移项链接。

## 安装分类
- `--category` 省略时默认 `auto`。
- 匹配优先级：kingdee -> automation -> meta -> core -> tags 派生 -> incoming。
- tag 可派生新分类；无 tag 才进入 `incoming/`。
- `incoming/<skill>` 不参与默认分发；需要人工复核/分类后再同步。
- 内部 CLI 的 `install <source>` 无 `--apply` 只生成安装计划，不写 source tree 或宿主目录。
- `install <source> --apply` 先复制到 source tree 的分类子目录；分类不是 `incoming` 时，再构造并 apply 选定宿主链接；对于 `incoming` 分类，apply 仅完成 source tree 写入，不默认分发。

内部 CLI 接受 Git 源时，clone 使用本次创建的独立临时目录：clone 失败、计划抛错、计划冲突和 dry-run 结束都会清理；可执行的 apply 计划保留该目录至复制与同步结束，再清理。临时目录清理不作用于本地输入源、安装目标或其他临时目录；操作系统拒绝清理时仍会报告错误，不保证强制终止进程后的自动回收。

复制失败返回 `install_incomplete` / `ok:false`，退出 `2`，不执行宿主同步。`installError` 提供失败阶段和稳定错误码；`sourceInstalled:false` 表示复制未完成，`applied:false` 不代表从未产生临时写入。`targetCreated` / `targetExists` 的 `null` 表示对应状态无法确认。

目标在计划后出现时返回 `target_exists`，保留目录、文件或断链。复制失败的清理仅对本次确认创建的文件执行 `unlink`、空目录执行 `rmdir`；外部新增、替换、修改或复制异常后归属不明的残留会保留。`cleanup.status` 为 `not_needed`、`removed` 或 `incomplete`。确认 `targetExists:false` 后可重试安装；目标仍在或未知时先核对 `cleanup.errors` 与精确路径，不递归删除。此恢复不保证文件系统事务或抵御检查与操作之间的恶意置换。

## 更新持久化失败

`update_incomplete` / `ok:false` 表示本项更新在持久化阶段未完成，退出 `2`；`updateError.phase` 区分 `source_write`、`metadata_write`、`update_history`、`sync_history`，`code` 仅保留已识别系统错误码或 `METADATA_UNAVAILABLE`，错误摘要不含原始异常。显式批量和 `update --all` 保留每项结果并继续其他独立对象。

`sourceUpdated`、`metadataUpdated`、`updateHistoryRecorded`、`syncHistoryRecorded` 分别表示源内容、版本元数据、更新历史和同步历史的写入状态：`true` 为调用确认完成，`false` 为未尝试该写入，`null` 为已尝试但异常后无法确认。异常可能发生在部分或全部写入之后，不能把 `null` 当作未改动；`METADATA_UNAVAILABLE` 表示写源后无法再次读取元数据，未尝试写版本基线。先核对实际文件及错误阶段，保留已完成内容，不盲目重跑下载、追加历史或回滚。

`syncAttempted` 区分是否进入宿主同步；同步后的历史写入失败仍保留 `synced`、`syncedTools` 和 `syncVerification` 的实际结果。`summary.updated` 只统计完整的 `updated` 项，可能少于 `sourceUpdated:true` 的项数；`summary.failed` 包含持久化失败，`summary.syncIncomplete` 只统计已尝试但未完成同步的项。dry-run 不进入以上写入阶段。
