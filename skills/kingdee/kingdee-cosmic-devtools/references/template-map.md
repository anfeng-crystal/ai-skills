# Template Map

## Source

- Upstream update XML: `https://tool.kingdee.com/kddt/idea-updatePlugins.xml`
- Parsed plugin version: `2.3.5-GA`
- Source archive: `kingdee-developer-tools-for-idea-2.3.5-GA.zip`
- Template source JAR: `kddt-core-1.0.3.jar`

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
