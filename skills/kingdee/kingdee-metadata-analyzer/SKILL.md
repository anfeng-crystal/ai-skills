---
name: kingdee-metadata-analyzer
description: "只读分析金蝶云苍穹实体字段、表单与列表配置、插件和规则，或定位实体的业务数据库。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.1.0"
  tags: "kingdee, cosmic, metadata, analysis, plugin-binding"
---

# Kingdee Metadata Analyzer
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 选择任务

| 需求 | 执行范围 | 入口 |
|---|---|---|
| 查单个字段、操作、枚举或插件 | 所需元数据；有警告、截断或继承缺口再扩大 | `quick-query.py` 的 `--fields`、`--ops`、`--plugins`、`--enums`、`--all`、`--search` |
| 全量元数据分析 | 字段、表单插件、界面规则、业务规则、列表配置、列表插件；含有效继承/扩展层及目标 PC/移动入口 | `cosmic-metadata-analyzer.py`，随后核对原始 entity/form/list source |
| 定位业务库、查数据库值 | 主表、所需字段/分录/关联实体与路由；不做全量配置分析 | [业务库定位](references/database-routing.md)；取值交 `kingdee-sql-and-data` |
| 跨环境比较、引用检查、Excel/HTML 导出 | 各环境独立取证后加工 | [对比与导出](references/cross-env-diff.md) |

元数据修改和基对象模板知识刷新交 `kingdee-metadata-change`；SDK 签名交 `kingdee-sdk-helper`，Java、报表和 KingScript 实现返回各自领域 skill。本地源码已足够且结论不依赖元数据时无需在线采集。

## 采集流程

1. 明确对象、环境和交付范围，按 [配置说明](references/config.md) 复用目标环境配置。用户未指定环境时用 dev；其它环境只作对照。
2. 仅业务库定位时直接运行路由入口。在线 quick/full 采集首次使用配置时先执行 `check-config`，再执行所选模式：

   ```text
   <python> <skill-root>/scripts/bootstrap-python-env.py -- <skill-root>/scripts/cosmic-metadata-analyzer.py check-config --config <config>
   <python> <skill-root>/scripts/bootstrap-python-env.py -- <skill-root>/scripts/cosmic-metadata-analyzer.py <entity> --config <config>
   ```

   POSIX 用 `python3`，Windows 用 `py -3`；路径独立传参。bootstrap 的 `--` 后直接放脚本路径，不再放解释器。
3. 读取脚本返回的 `__INVENTORY_PATH__`、`__OUTPUT_DIR__`，按实际缺口补查 source。`inventory` 不是全量完成标志；全量任务逐项核对上表六类配置，清单缺项时读取原始设计，不能以空摘要判定未配置。
4. 只补当前结论缺少的证据，复用本次同环境有效结果。连接失败按原因选择同项目配置、设计 XML、缓存、源码或 JAR；标明环境与来源差异。

## 证据与交付

- 字段、物理列、分录及关联实体按 [字段证据](references/field-evidence.md) 核对；字段不存在需要完整有效链或运行期证据，单份设计差量不足。
- 表单、列表、操作和 PC/移动入口按 [页面挂载](references/page-binding.md) 分别取证；共表或同插件类不代表入口和规则相同。
- 警告、截断、祖先缺失和旧缓存完整性未知均保留在结论中。`--fields --inherit` 是分层设计候选，不是平台合并后的有效全集。
- 跨 skill 的 JSON 摘要使用 [输出契约](references/output-contract.md) 中的 `metadata_contract.py`，保留输入的警告和证据状态。
- 回答用户的问题及实际影响结论的缺项；不输出命令流水。评分和正式报告按需读 [取证评分](references/analysis-rubric.md)、[报告模板](references/report-template.md)。

## 边界

- 在线查询只读，限目标实体与必要配置；生产查询设置超时和结果范围。业务写入由数据变更契约控制。
- `metadataAnalyzer.enabled=false` 时不连接。凭据与产物规则统一见配置说明；不读取原始市场包 `config.json`。
- 可输出任务要求的路由、库和表标识；不回显密码、账号、连接串、内部地址或业务样本，不把生产配置写入 Skill 或测试资产。
