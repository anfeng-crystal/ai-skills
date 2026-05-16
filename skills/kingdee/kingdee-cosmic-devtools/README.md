# Kingdee Cosmic DevTools

## 中文

金蝶云苍穹开发工具包提供一个跨平台 CLI，用于复用金蝶云苍穹开发助手 IDEA 插件中的工程模板、模块模板、插件模板和资源更新能力。它适用于 Windows、macOS 和 Linux，只依赖 Python 标准库。

### 主要功能

- 创建苍穹 Gradle 工程：支持 `app`、`cloud`、`multi` 三类模板。
- 给现有苍穹工程新增模块：只使用 `*-sub.zip` 增量模板，不创建完整工程，不覆盖根工程配置。
- 生成插件和服务骨架：支持继承插件、扩展点插件和微服务类。
- 检查工程状态：输出工程类型、项目标识、资源目录和环境状态。
- 更新苍穹资源环境：支持后台下载、断点续传、校验、短锁应用、备份和回滚。

### 平台和依赖

- 操作系统：Windows、macOS、Linux。
- 运行环境：Python 3.9 或更高版本。
- 第三方依赖：无。
- 内置资产：KDDT `2.3.5-GA` 工程模板、子模块模板和 Java 模板。

### 快速开始

在本目录运行：

```bash
python scripts/kddt_devtools.py --help
```

Windows 可使用：

```powershell
py -3 scripts\kddt_devtools.py --help
```

### 创建完整工程

```bash
python scripts/kddt_devtools.py create-project \
  --target /path/to/project \
  --project-name demo \
  --template-type multi \
  --developer-flag ztjg \
  --project-flag dswpt \
  --cloud-flag dswpt \
  --app-flag dsw
```

`project_flag` 可为空。为空时使用旧模板；非空时使用带项目标识的新模板。缺少参数时可加 `--interactive` 让 CLI 逐项询问。

### 新增模块

```bash
python scripts/kddt_devtools.py add-module \
  --project /path/to/existing-project \
  --template-type app \
  --developer-flag ztjg \
  --cloud-flag newcloud \
  --app-flag newapp
```

新增模块会先识别现有工程是否包含 `systemProp.project_flag` 或 `COSMIC_PROJECT_FLAG`，再选择新旧子模块模板。该命令只新增模块目录，并补充 `settings.gradle` 和调试工程依赖。

### 生成插件或服务

```bash
python scripts/kddt_devtools.py create-plugin \
  --kind inherit \
  --package kd.demo.plugin \
  --class-name DemoPlugin \
  --parent-full-name kd.bos.form.plugin.AbstractFormPlugin \
  --output-dir /path/to/src/main/java
```

`--kind` 支持：

- `inherit`：继承插件。
- `extend`：扩展点插件。
- `service`：微服务类。

默认不覆盖同名文件；需要覆盖时显式传入 `--force`。

### 更新资源环境

```bash
python scripts/kddt_devtools.py update-env start \
  --cosmic-home /path/to/cosmic-home \
  --res-url http://host/appstore/dev_env
```

常用动作：

- `start`：创建更新任务并下载到缓存和 staging。
- `status`：查看任务状态。
- `resume`：从失败或中断处继续。
- `cancel`：请求取消任务。
- `apply`：校验完成后备份并应用到 `COSMIC_HOME`。
- `rollback`：按备份恢复。

下载阶段不会直接写入正式资源目录。应用阶段会先备份目标目录，再短时间替换资源。网络中断后，已校验成功的文件不会重新下载。

### 工程检查

```bash
python scripts/kddt_devtools.py inspect --project /path/to/project
```

该命令输出工程根目录、模板类型、开发商标识、项目标识、云标识、应用标识、`COSMIC_HOME`、资源 URL 和静态资源状态。

### 字段口径

- `developer_flag`：必填，小写字母开头，2-4 位小写字母或数字。
- `project_flag`：可空；老项目没有项目标识时保持空。
- `cloud_flag`：必填，小写字母开头，2-17 位小写字母或数字。
- `app_flag`：必填，小写字母开头，2-22 位小写字母或数字。
- `template_type`：只能是 `app`、`cloud`、`multi`。

### 注意事项

- 新增模块不会迁移旧工程结构，也不会强行补项目标识。
- 资源更新优先使用 `update.json` 做文件级差异；只有 `update.md5` 时退化为包级恢复。
- `apply` 阶段会占用 `COSMIC_HOME` 目标目录；下载和校验阶段不占用正式目录。
- 内置模板资产来自金蝶云苍穹开发助手 IDEA 插件。对外发布前需要确认模板资产授权。

---

## English

Kingdee Cosmic DevTools is a cross-platform CLI package that reuses project templates, module templates, Java templates, and environment update behavior from the Kingdee Cloud Cosmic Developer Tools IDEA plugin. It works on Windows, macOS, and Linux, and depends only on the Python standard library.

### Features

- Create Cosmic Gradle projects with `app`, `cloud`, and `multi` templates.
- Add modules to existing Cosmic projects using only incremental `*-sub.zip` templates.
- Generate Java skeletons for inherited plugins, extension-point plugins, and micro service classes.
- Inspect project metadata, project identifier status, resource directories, and environment state.
- Update the Cosmic resource environment with resumable downloads, verification, staged application, backup, and rollback.

### Platform And Requirements

- Operating systems: Windows, macOS, Linux.
- Runtime: Python 3.9 or newer.
- Third-party dependencies: none.
- Bundled assets: KDDT `2.3.5-GA` project templates, submodule templates, and Java templates.

### Quick Start

Run from this directory:

```bash
python scripts/kddt_devtools.py --help
```

On Windows:

```powershell
py -3 scripts\kddt_devtools.py --help
```

### Create A Project

```bash
python scripts/kddt_devtools.py create-project \
  --target /path/to/project \
  --project-name demo \
  --template-type multi \
  --developer-flag ztjg \
  --project-flag dswpt \
  --cloud-flag dswpt \
  --app-flag dsw
```

`project_flag` is optional. When it is empty, the CLI uses legacy templates. When it is present, the CLI uses the newer templates that include a project identifier. Add `--interactive` to let the CLI prompt for missing fields.

### Add A Module

```bash
python scripts/kddt_devtools.py add-module \
  --project /path/to/existing-project \
  --template-type app \
  --developer-flag ztjg \
  --cloud-flag newcloud \
  --app-flag newapp
```

The command detects whether the existing project has `systemProp.project_flag` or `COSMIC_PROJECT_FLAG`, then selects the matching new or legacy submodule template. It only creates module files and updates `settings.gradle` plus debug project dependencies when applicable.

### Generate A Plugin Or Service

```bash
python scripts/kddt_devtools.py create-plugin \
  --kind inherit \
  --package kd.demo.plugin \
  --class-name DemoPlugin \
  --parent-full-name kd.bos.form.plugin.AbstractFormPlugin \
  --output-dir /path/to/src/main/java
```

Supported `--kind` values:

- `inherit`: inherited plugin.
- `extend`: extension-point plugin.
- `service`: micro service class.

Existing files are not overwritten by default. Pass `--force` to overwrite explicitly.

### Update The Resource Environment

```bash
python scripts/kddt_devtools.py update-env start \
  --cosmic-home /path/to/cosmic-home \
  --res-url http://host/appstore/dev_env
```

Common actions:

- `start`: create an update job and download files into cache and staging.
- `status`: show job status.
- `resume`: continue after a failure or interruption.
- `cancel`: request job cancellation.
- `apply`: verify, back up current targets, and apply staged files to `COSMIC_HOME`.
- `rollback`: restore from a backup.

The download phase does not write into the live resource directories. The apply phase creates a backup and then replaces the target resources with a short lock window. Verified files are not downloaded again after a network interruption.

### Inspect A Project

```bash
python scripts/kddt_devtools.py inspect --project /path/to/project
```

This command prints the project root, template type, developer flag, project flag, cloud flag, app flag, `COSMIC_HOME`, resource URL, and static resource status.

### Field Rules

- `developer_flag`: required, starts with a lowercase letter, 2-4 lowercase letters or digits.
- `project_flag`: optional; keep it empty for legacy projects without a project identifier.
- `cloud_flag`: required, starts with a lowercase letter, 2-17 lowercase letters or digits.
- `app_flag`: required, starts with a lowercase letter, 2-22 lowercase letters or digits.
- `template_type`: one of `app`, `cloud`, `multi`.

### Notes

- Adding a module does not migrate legacy project structure and does not force a project identifier.
- Environment updates prefer `update.json` for file-level differences. With only `update.md5`, recovery is package-level.
- `apply` temporarily occupies target directories under `COSMIC_HOME`; download and verification do not occupy live directories.
- Bundled templates come from the Kingdee Cloud Cosmic Developer Tools IDEA plugin. Confirm asset licensing before external distribution.
