---
name: kingdee-metadata-analyzer
description: "金蝶云苍穹实体、字段、表单、插件挂载、上下游关系和跨环境差异的只读元数据取证；需要真实字段或页面链路证据时使用。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.0.0"
  tags: "kingdee, cosmic, metadata, analysis, plugin-binding"
---

# Kingdee Metadata Analyzer
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 触发与路由
- 实体字段、表单/操作、插件挂载、页面链路、上下游关系、跨环境差异或元数据导出需要真实证据时使用。
- SDK 签名交 `kingdee-sdk-helper`；Java 实现和运行诊断交 `kingdee-cosmic`；报表交 `kingdee-report`；KingScript 交 `kingdee-kingscript`。
- 本地源码或编译证据足以回答且元数据不影响结论时不触发；混合任务先产出证据，再返回原实现或修复任务。

## 模式
| 模式 | 适用条件 | 主要产物 |
| --- | --- | --- |
| `quick` | 单个字段、操作、枚举或插件清单，且结果完整无警告 | 终端结果或 quick cache |
| `full` | 字段层级、PC/移动页面链、挂载点或上下游关系 | `inventory.json`、`sources/*` |
| `cross-env` | dev/test/prod 差异或引用完整性 | 环境分层证据 |
| `export` | 用户明确要求 Excel/HTML | 脱敏导出文件 |

## 契约
- 环境口径来自当前任务；未指定时用 dev。用户指定 prod/test/dev 后，不用其它环境冒充目标事实。
- 在线查询只读。生产模式限定实体、配置、必要表、分页/超时和证据用途；不扫全库、全租户或无关实体。
- 凭据解析顺序以脚本为准：当前进程 `passwordEnv` → 配置声明的 env 文件 → 同名/项目 `.env` → 既有 JSON 兼容字段。只输出来源类型，不输出值。
- `WARNING`、截断、缓存失败、层级缺失或仅展示前 N 条都表示证据不完整；升级模式或标记未确认，不能包装成确定结论。

## 工作流
1. 确定实体、证据目标、环境和模式；字段层级、派生页面、PC/移动执行链、共用物理表的多实体/多布局或流程包直接用 `full`。
2. 从当前目录向上定位项目根，按“目标环境显式配置 → 同项目通用配置 → 其它环境配置仅作对照 → 可用历史产物”选择证据源。
3. 从当前 SKILL.md 定位 skill 根。POSIX 使用 `python3`，Windows 使用 `py -3`；所有路径作为独立参数传递并允许空格。
4. 先运行：
   ```text
   <python> <skill-root>/scripts/bootstrap-python-env.py -- <skill-root>/scripts/cosmic-metadata-analyzer.py check-config --config <config>
   ```
   bootstrap 尊重 `KINGDEE_METADATA_ANALYZER_PIP_INDEX_URLS` / `KINGDEE_METADATA_ANALYZER_PIP_INDEX_URL`；安装失败时报告依赖、配置、凭据或网络的具体分类。
5. `quick` 调用 `quick-query.py` 的 `--fields`、`--ops`、`--plugins`、`--enums`、`--all` 或 `--search`；出现警告、截断或层级需求时升级到 `full`。
6. `full` 调用 `cosmic-metadata-analyzer.py <entity> --config <config>`，按脚本打印的 `__INVENTORY_PATH__` 和 `__OUTPUT_DIR__` 读取结果；默认产物留在系统缓存，不写业务仓库。
7. 在线配置失败时依次尝试同项目候选配置、已有 inventory/quick cache、设计 XML、源码和 JAR；跨环境结果只标为对照或推断。
8. 需要给其它 skill 消费时运行 `metadata_contract.py --inventory <inventory> --environment <env>`；只有 quick cache 时使用 `--quick-cache`。
9. 当前请求已包含完整分析或实现目标时连续生成所需证据，不增加中途确认；只有分析对象或副作用范围扩大时再询问。
10. `export` 前列出并哈希输入。用户人工标注的 MD/Excel/CSV 是只读权威输入；不得通过 `import`/`runpy` 执行副作用不明的生成器覆盖它。新导出写入不同路径，并按用户指定主清单做行数、主键和覆盖率对账。

## 证据判定
- `fieldKey`、中文名、字段类型、物理列、父 entry、PC/移动布局分别标注来源；任何一层缺证据都写未确认。
- 同一物理表只证明存储复用，不证明实体、字段全集、表单/列表布局、菜单、插件或工作流入口相同；每个实体和布局必须独立列证据。
- 表单布局与列表布局分别盘点。列表列、按钮、过滤、列表插件和 `ListOpenLayoutBill` 不能由表单字段清单推断。
- `inventory.json` 只按它实际包含的字段/页面/插件作证；有 warning、截断、根/叶层级缺失或未读原始 source 时，不得声称全量完整。
- 流程当前定义以目标环境发布后导出的 `.scheme` 及发布状态为准；普通 `.process` 文件存在不能证明其已生效。
- 从截图或表格提取角色、字段或挂载项时先逐行枚举，再与用户给出的总数和主键清单对账；裁切、合并单元格、备注列含义或行边界不清时标未确认，不能自行排除。
- `*Field` 未知类型保留原始标签，不因白名单缺失判定字段不存在。
- 插件挂载同时核对 `className`/`oid`、`operation`、`formPage` 和 `pageElement`；类名相同不等于入口相同。
- 无 `Key/Name/OperationKey` 的 `action=edit` 只能输出无语义标签，不能按顺序推断暂存、提交或审核。
- 字段不存在只能由完整字段扫描、设计 XML 或目标环境证据证明。

## References
- 取证评分：`references/analysis-rubric.md`
- 配置：`references/config.md`
- 页面挂载：`references/page-binding.md`
- 字段证据：`references/field-evidence.md`
- 输出合同：`references/output-contract.md`
- 跨环境与导出：`references/cross-env-diff.md`
- 报告结构：`references/report-template.md`
- 工作流/布局变更的消费规则由 `kingdee-cosmic/references/workflow-metadata-change.md` 承担；本 skill 只输出只读证据。

## 门禁与失败
- `metadataAnalyzer.enabled=false` 时不连接数据库。
- 不读原始市场包 `config.json`，不打印数据库连接串、host/schema、账号、密码、租户、内部 URL 或业务字段样例值。
- 明文密码迁移属于配置写入；只有当前任务明确授权时才备份、迁移到被 Git 忽略的同项目 `.env` 并验证回滚。
- 目标环境不可达不等于没有元数据；输出目标环境状态、已尝试证据、可用替代证据和未确认项。
- 不把命令流水和排查过程写入正式报告；报告只保留稳定事实、证据边界、复用途径和风险。

## 输出
配置状态（凭据来源类型） → 采集结果 → 字段/页面/插件证据 → 外部关系 → 可复用途径 → 脱敏项 → 风险与未确认项。
