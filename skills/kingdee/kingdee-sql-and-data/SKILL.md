---
name: kingdee-sql-and-data
description: "校验金蝶 KSQL、生成预置数据/DDL、填充平台数据导入模板，或核对与变更数据库数据；ISCB SQL/DML 服务流程交 iscb-script。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.2.0"
  tags: "kingdee, cosmic, ksql, data, database"
---

# Kingdee SQL And Data
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 按任务执行

| 任务/模式 | 入口 | 完成点 |
|---|---|---|
| KSQL 本地校验 `validate` | [语法规范](references/ksql-spec.md)、`scripts/validate_ksql.py <SQL>` | 校验结果与方言限制，不连接数据库 |
| 预置数据 `generate` | [生成器](references/preset-data-script.md)、[配置发现](references/config-management.md) | 按授权窄查源数据，生成 DELETE/INSERT 审阅稿，不执行目标写入 |
| 元数据转 DDL `generate` | [DDL 契约](references/metadata-ddl-contract.md) | 生成 CREATE TABLE/INDEX；不连接、不执行、不生成 DROP/ALTER |
| 业务数据 `query-readonly` | [只读查询](references/db-query.md) | 补齐必要映射后实际查询并解释结果；已有生产只读授权不重复确认 |
| 修改计划/批准执行 `execute-approved` | [数据变更契约](references/approved-data-change.md) | 计划只读；批准后按精确范围执行并复核 |
| 平台导入模板 | [模板回填](references/import-workbook.md) | 保留系统模板结构，按授权分别完成填充、检查和导入 |

字段、表/列、分录和路由事实由 `kingdee-metadata-analyzer` 提供；查数据只读取必要映射，不做全量元数据分析。ISCB SQL/DML 服务交 `iscb-script`，Java、KingScript 和安全 POC 返回对应领域 skill。

## 执行规则

1. 明确环境、对象和用户要求的完成点。说“先出计划/我来审核”时保持计划态，后续精确批准才进入执行。
2. 按任务加载上表的一份流程。缺项先用现有配置、元数据和工具补齐；仍影响结论时报告 `contract_incomplete`，不把初始未知当最终阻塞。
3. KSQL 特有函数/语法按项目的苍穹版本和目标数据库类型/版本核实；二者不能混同。本地检查通过只证明对应检查范围。
4. 字典赋值先闭合“业务字段 → 实际引用实体 → 编码 → 转换 → 外部接口值”；相似名称不能证明等价。目标对象纠正后重算范围。
5. 批准写入前读取数据变更契约并运行 `scripts/validate_change_contract.py --contract <文件>`；它只校验合同，不执行 SQL。失败先确认回滚，再重算当前范围和并发条件。

## 工具与配置

所有相对路径以当前 skill 根为准，路径独立传参；POSIX 用 `python3`，Windows 用 `py -3`。

- `scripts/config_resolver.py --cwd <项目根> --print`：解析 KSQL 配置路径，显式传给预置数据生成器。示例模板不是生产连接。
- `scripts/metadata_to_ddl.py inspect|generate`：参数和输入格式见 DDL 契约；字段未知不能猜列名或回退 `VARCHAR(255)`。
- `scripts/git_secret_guard.py --repo <项目根> --json`：只读敏感信息检查，不修改 Git 或配置。

## 输出与验证

输出实际模式、环境、范围、结果和影响结论的缺项；生成物标明未执行，工具不可用标 `generated_not_executed`。可给任务所需的路由、库/表标识，凭据、连接串、内部地址和业务敏感值不回显。

脚本变更运行受影响的 `scripts/tests`；共用生成或契约逻辑变更运行 `python3 -m unittest discover -s scripts/tests -p 'test_*.py'`。纯说明变更检查引用和差异。
