# Template Map

## Source

- Upstream update XML: `https://tool.kingdee.com/kddt/idea-updatePlugins.xml`
- Parsed plugin version: `2.3.5-GA`
- Source archive: `kingdee-developer-tools-for-idea-2.3.5-GA.zip`
- Template source JAR: `kddt-core-1.0.3.jar`

这些字段描述本 Skill 随包保存的版本快照，不承诺与上游最新版一致。2026-09-07 读取上述官方 update XML 时，当前入口为 `2.4.3-GA`；不能据此直接改写本地资产版本或套用新模板规则。已有项目仍按实际模板/Gradle/资源合同处理，模板升级需核对真实新资产并执行相应验证。

开发工具版本不代表目标苍穹版本。模板中的 SDK 类型、方法和依赖只能在目标实际依赖/声明或适用版本的官方依据确认后进入目标实现；`project_flag` 或生成器通过不证明 7.0/8.0 兼容。版本未明时保留已完成的候选骨架并列出未验证项，不将模板更新当作平台升级授权。

官方更新记录的 `2.4.2-GA` 说明区分开发助手独立资源目录与 CosmicStudio 环境目录；详见 `env-update.md`。这里的项目标识与 `*-sub.zip` 映射只对当前随包模板负责，不宣称所有未来 KDDT 版本布局相同。

## Project Templates

`project_flag` decides whether to use the new project layout. It is optional because older Cosmic projects do not have a project identifier.

| Operation | template_type | With project_flag | Without project_flag |
|---|---|---|---|
| create project | `multi` | `code-2.zip` | `code.zip` |
| create project | `app` | `code-app-2.zip` | `code-app.zip` |
| create project | `cloud` | `code-cloud-2.zip` | `code-cloud.zip` |
| add module | `multi` | `code-2-sub.zip` | `code-sub.zip` |
| add module | `app` | `code-app-2-sub.zip` | `code-app-sub.zip` |
| add module | `cloud` | `code-cloud-2-sub.zip` | `code-cloud-sub.zip` |

## Placeholders

The script replaces these stable placeholders in paths and text files:

| Placeholder | Meaning |
|---|---|
| `devflg` | developer flag |
| `projectflg` | project flag, only when present |
| `cloudflg` | cloud flag |
| `appflg` | application flag |
| `generate_date` | generation timestamp |
| `defualt_static_res_path` | static resource path |
| `defualt_zk_url_value` | zookeeper URL |
| `defualt_mc_url_value` | MC URL |
| `defualt_project_dir_value` | project directory |

## Module Add Rules

- Add-module never creates root project files from a full template.
- Existing project shape is detected from `cosmic.json` and `gradle.properties`.
- If the existing project has `COSMIC_PROJECT_FLAG` or `systemProp.project_flag`, use the `*-2-sub.zip` template.
- If not, use the old `*-sub.zip` template and keep `project_flag` empty.
- After extraction, append idempotent `include` and `projectDir` lines to `settings.gradle`; update debug module dependencies when a debug `build.gradle` exists.

## Java Templates

| Kind | Template |
|---|---|
| inherited plugin | `CreateInheritPlugin.java.template` |
| extension-point plugin | `CreateExtendPointPlugin.java.template` |
| micro service | `CreateService.java.template` |
