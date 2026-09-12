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

## 安装分类
- `--category` 省略时默认 `auto`。
- 匹配优先级：kingdee -> automation -> meta -> core -> tags 派生 -> incoming。
- tag 可派生新分类；无 tag 才进入 `incoming/`。
- `incoming/<skill>` 不参与默认分发；需要人工复核/分类后再同步。
- 内部 CLI 的 `install <source>` 无 `--apply` 只生成安装计划，不写 source tree 或宿主目录。
- `install <source> --apply` 先复制到 source tree 的分类子目录；分类不是 `incoming` 时，再构造并 apply 选定宿主链接；对于 `incoming` 分类，apply 仅完成 source tree 写入，不默认分发。
