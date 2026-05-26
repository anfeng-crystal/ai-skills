---
name: kingdee-cosmic
description: "Kingdee Cosmic Java dev: plugins, reports, workflows, BOTP, OpenAPI, troubleshooting. Use for 金蝶云苍穹 Java 二开、插件、报表、操作/BOTP/工作流、OpenAPI、DynamicObject、元数据关联诊断和代码质量核查；字段/表单/插件挂载证据优先交给 kingdee-metadata-analyzer，SDK/API 签名优先交给 kingdee-sdk-helper。"
metadata:
  author: anfeng
  version: "1.3.0"
  license: MIT
  tags: [kingdee, cosmic, java, plugin, BOS, SDK]
---

# Kingdee Cosmic
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## Core Rule

默认按“封装优先，原生兜底”工作：项目已有 `kd.cd.common.plugin` 扩展基类、`OpUtils`、`BotpUtils`、`QueryUtils`、`DynamicObjectUtils` 或同类 helper 能覆盖时，不再另写第二套平台封装。

## Routing

1. 先判断这是否是金蝶云苍穹 Java 二开、配置、诊断或改造任务；KingScript 用 `kingdee-kingscript`，ISCB 用 `kingdee-iscb-script`，SDK 签名查询用 `kingdee-sdk-helper`。
2. 涉及实体、字段、表单、页面/操作挂载点、插件绑定或上下游关系时，先用 `kingdee-metadata-analyzer` 取证；在线不可用时，可复用已有 analyzer 产物、项目源码、JAR 和本 skill references，但要标明证据边界。
3. 涉及宿主工程模板、登录态、配置检查或 KSQL/数据脚本时，优先转给对应专用 skill：`kingdee-cosmic-devtools`、`kingdee-cosmic-login`、`kingdee-sql-and-data`。
4. 报表任务先读 `references/report-development.md`，再按本 skill 的字段/API/验证门禁执行。

## Required First Checks

- 在目标项目根目录执行 `python3 <SKILL_ROOT>/scripts/cosmic-config-check.py`。`ERROR` 阻断生成代码；`WARNING` 只说明在线能力降级，并限制后续在线脚本调用。
- 业务话术先读 `rules/intent-routing.md`，再按 `rules/decision-matrix.md` 选插件、配置、脚本或诊断路径。
- 生成或修改 Java 前，先读 `rules/platform-baseline.md`、`rules/cheat-sheet.md` 和最接近的 `assets/*.java` 模板；事件顺序不确定时读 `references/event-lifecycle.md`。
- 字段、`entityId`、枚举值、`refType`、SDK 方法签名和 `@Override` 事件签名不能凭记忆猜；用元数据、项目依赖、`kingdee-sdk-helper` 或本 skill 脚本确认。

## Workflow

1. 明确任务类型、目标对象、插件类型、事件点、事务边界和验证方式。
2. 读取最小资料集：
   - 插件/配置选择：`rules/decision-matrix.md`
   - API 速查：`rules/cheat-sheet.md`
   - BOTP：`references/botp-convert.md`
   - DataSet/报表取数：`references/query-dataset.md`、`references/report-development.md`
   - DynamicObject：`references/dynamic-object.md`
   - 生命周期：`references/event-lifecycle.md`
   - 故障诊断：`references/diagnostics/issue-analysis.md`
   - 代码质量：`references/quality/cosmic-java-scan.md`
3. 先查当前项目源码、同类实现、模板和 snippet；能复用现有 helper 时不新增公共能力。
4. 编码后执行模块级 Gradle 编译/测试；无法定位模块时执行 `python3 <SKILL_ROOT>/scripts/cosmic-post-check.py <file_or_dir> --fix-hint`。
5. 收口时按 `rules/post-check.md` 给出依据、改动、验证和风险。

## Scripts

- 配置预检：`scripts/cosmic-config-check.py`
- API/知识库查询：`scripts/cosmic-api-knowledge.py`
- 表单/字段元数据：`scripts/cosmic-form-metadata.py`
- 基础资料查询：`scripts/cosmic-basedata-query.py`
- 业务拓展点查询：`scripts/cosmic-extpoints-query.py`
- 代码后检：`scripts/cosmic-post-check.py`
- lint 规则：`scripts/lint/`
- 历史质量扫描：`scripts/scan/`

## Guardrails

- 最小必要修改；不改公共接口、依赖或文件结构，除非用户明确要求或方案已确认。
- 不把实施过程、排查路径或交付口径写入代码注释、README、skills 或长期操作说明。
- 新增类、公共方法、复杂私有方法、关键平台调用、事务/跨库/回写/DataSet/工作流边界只写长期有效的功能性注释。
- 不直接 SQL，不拼接 SQL/KSQL 条件字符串；验证性数据核对可用独立只读脚本完成，不作为业务交付实现。
- `DataSet` 必须关闭；禁止循环内访问数据库、Redis 或反复 `view.updateView()`；禁止 `printStackTrace()`。

## Output

使用简体中文，先给结论，再给依据、边界和风险。实现类任务按“依据 -> 改动 -> 验证 -> 风险/待确认项”收口。
