# ISCB 数据库与 DML 服务流程契约

## 连接与 dbRoute

- SQL 函数首参必须是当前上下文实际提供的连接对象或服务流程资源变量，如 `$src`、`$tar`、`$this` 或已引入的资源别名；不能传 `'ierp'`、`'cn'` 等字符串。
- `dbRoute` 和 `@ROUTE` 后缀必须来自目标实体元数据、目标项目配置或当前环境只读证据。不得把 HR/SYS/SWC 等经验映射当成所有租户通用事实。
- 服务流程中的资源别名必须与基线 `.dts` 的 `resources[].res_alias` 一致；生成器不创建连接、不替换连接 ID。

## 已收录数据库函数

| 函数 | 契约 |
|---|---|
| `query_value(cn, sql, params?, types?)` | 返回首行首列；无结果为 `null` |
| `query_row(cn, sql, params?, types?)` | 单行只读 `DataRow`；字段 key 小写 |
| `query_row2(cn, sql, params?, types?)` | 单行可修改 `Map`；字段 key 小写 |
| `query_list(cn, sql, params?, types?)` | 多行只读 `DataRow` 列表；必须有业务过滤、分页或结果上限 |
| `query_list2(cn, sql, params?, types?)` | 多行可修改 `Map` 列表；必须有业务过滤、分页或结果上限 |
| `query_column(cn, sql, params?, types?)` | 返回首列值列表 |
| `execute_update(cn, sql, params?, types?)` | 单条 INSERT/UPDATE/DELETE，返回影响行数 |
| `execute_batch(cn, sql, batch, types?)` | 二维参数列表批量写入，返回影响行数 |
| `execute_call(cn, sql, valueList)` | 调用存储过程，返回 out/inout 参数结果 |

上述返回形态来自官方平台脚本文档；本地 JAR 不带真实连接，不能用它否定平台语义。参数、数据库兼容值和集合行为读 `database-platform-rules.md`，目标版本冲突时以目标平台验证结果修订。

## 参数化 SQL

1. 值一律放入 `params`，类型放入同位置的 `types`；`?`、参数和类型数量必须一致。
2. 类型使用 `BIGINT`、`INTEGER`、`VARCHAR`、`TIMESTAMP`、`DECIMAL` 等常量，不写成字符串。
3. 时间、长整数和小数按已确认 DSL 转换函数构造，如 `T(...)`、`L(...)`、`N(...)`。
4. `execute_batch` 的每一行参数数量必须一致；批量写入优先于循环调用 `execute_update`。
5. 表名、列名、排序方向和 dbRoute 不能通过值参数绑定；它们必须来自元数据白名单，不能直接拼接用户输入。
6. 不把账号、密码、token、Cookie、连接串或 access key 当作 SQL 参数写入服务流程文件。

## 动作模式

| 模式 | 动作 |
|---|---|
| `generate` | 生成或修订脚本，不执行外部调用 |
| `validate` | 运行本地静态/编译/runtime 校验；不等同平台执行 |
| `run-readonly` | 目标、连接、表/实体、过滤范围、结果上限、授权已知时执行只读查询；生产只读契约完整后无需重复确认 |
| `run-approved` | 仅在环境、资源别名、SQL 目标、数据范围、最大影响行数、预检、回滚/恢复方案和授权引用完整时执行已批准写入；契约完整后不重复确认 |

缺任一契约项时输出 `contract_incomplete` 并停止。运行工具不可用时输出 `generated_not_executed`，不能把生成或静态通过写成平台执行成功。

恢复/回滚必须按每条业务记录的真实 before-image、权威历史版本或已验证的逐行旧值映射执行；不能按错误时间窗、当前状态分布或单一常量把一批记录推定恢复成同一旧状态。某行原值不可证明时，将其标成 `unrecoverable_without_evidence` 并停止该行，不得用“最可能的旧值”补齐。恢复 SQL 同样需要主键、当前值 compare-before-restore、精确行数和恢复后逐行复核。

## DML 服务流程生成器

```text
python3 scripts/dml_service_flow.py inspect --baseline <current.dts> --sql-file <write.sql> --precheck-sql-file <count.sql> --parameters-file <params.json> --contract-file <contract.json>
python3 scripts/dml_service_flow.py generate --baseline <current.dts> --sql-file <write.sql> --precheck-sql-file <count.sql> --parameters-file <params.json> --contract-file <contract.json> --output <review.dts>
```

生成器契约：

- 只接受 UTF-8 的当前 `.dts` 基线，不使用内置连接、租户或流程模板。
- 只更新指定服务流程的指定 Script 节点，保留其他记录、资源、连接 ID 和节点。
- DML 仅允许单条参数化 INSERT/UPDATE/DELETE；UPDATE/DELETE 强制包含 WHERE。
- 强制提供独立 `SELECT COUNT...` 预检、参数类型、最大影响行数、回滚方案和授权引用。
- `inspect` 只返回脱敏结构摘要；`generate` 要求契约中 `approved=true`，只写用户给定的新输出路径，不导入、不发布、不执行。
- 输出已存在时必须显式传 `--overwrite`；基线文件永不原地覆盖。

参数文件结构：`params`、`types`、`precheck_params`、`precheck_types` 四个数组。契约文件至少包含 `approved`、`authorization_ref`、`environment`、`scope`、`rollback_plan`、`max_rows`、`resource_alias`、`flow_number` 和 `node_id`。
