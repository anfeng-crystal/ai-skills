# ISCB 平台数据库规则

## Profile

- 本文件用于数据集成、值转换、服务流程、自定义 API 等真实平台节点；本地 JAR 只验证 engine 语法，不能否定官方平台节点能力。
- 连接、实体、物理表、字段和 `dbRoute` 以目标环境元数据或只读证据为准；本 bundle 不携带元数据快照。
- 写入继续执行 `database-dml-contract.md` 的授权、预检、影响行数和回滚门禁。

## 官方常见 route 标签

`hr -> @HR`、`swc -> @SWC`、`sys -> @SYS`、`tmc -> @TMC`、`wtc -> @WTC`、`fi -> @FI`、`scm -> @SCM`、`epm -> @EPM`、`eip -> @EIP`、`wfs -> @WFS`、`drp -> @DRP`、`cal -> @CAL`、`cr -> @CR`、`lms -> @LMS`、`fias -> @FIAS`、`bcm -> @BCM`、`pmc -> @PMC`、`imsc -> @IMSC`。

这只确认 route 标签拼写，不确认某实体属于哪个库；实体到 route 的映射必须读取目标环境证据。

## SQL 值转换的连接与路由

- SQL 类型值转换先选连接、再解析路由。查询目标系统时使用 `use $tar;`，后续 `@ROUTE` 由目标苍穹连接解析；不能把带路由的 SQL 直接交给外部 JDBC 源库。
- `use $tar;` 是 SQL 编辑器的连接选择指令；脚本类型中的 `$tar` / `$this` 是 `ConnectionWrapper`，两者不能混写。
- 同一段 SQL 不同时访问苍穹的多个业务库路由；需要跨路由时，用 `#{临时变量}` 串联多段查询。
- `SQLRule` 堆栈后接源库 JDBC 驱动，且错误对象含 `@ROUTE`，优先判定为连接未切换；核实 `use $tar;`、源/目标系统和实际路由后再修改，不直接删路由或改脚本类型。

最小模式：

```sql
use $tar;
SELECT fid AS result FROM target_table@ROUTE WHERE fnumber = #{param};
```

## 查询结果

| 函数 | 官方平台语义 |
|---|---|
| `query_value` | 首行首列；无数据返回 null |
| `query_row` | 首行只读 `DataRow`；字段 key 小写 |
| `query_row2` | 首行可修改 `Map`；字段 key 小写 |
| `query_list` | 只读 `DataRow` 列表 |
| `query_list2` | 可修改 `Map` 列表 |
| `query_column` | 首列组成的 Java List；无数据为空列表 |

`query_column` 使用 `.length` 和 `[i]`；不使用 `.size()`、`.map()` 或 `.push()`。它只接收一组参数，不能把二维参数当批量查询。

## 参数与批处理

- SQL 值使用 `?`、`params`、`types` 同位置绑定；类型使用 `BIGINT`、`VARCHAR`、`TIMESTAMP` 等常量。
- PostgreSQL 的 bigint 条件声明 `BIGINT`；时间字符串先用 `T(...)` 构造并声明 `TIMESTAMP`。
- `execute_batch` 的 batch 必须是二维且每行参数数量一致。
- 平台节点需要动态构造 batch 时，官方写法使用 `java.util.ArrayList`；这是 platform profile，不送 bundled engine JAR 编译：

```text
var batch = new java.util.ArrayList();
var row = new java.util.ArrayList();
row.add(fid);
batch.add(row);
```

## 多选基础资料值转换缓存

- 目标字段为多选基础资料且值转换直接返回 `fid` 列表/Collection 时必须 `iscached=false`；多选枚举最终返回逗号字符串不自动套用本规则。
- 独立值转换 DTS 与服务流程内嵌同名规则同时修改；不得为测试缓存临时开启集合结果缓存。
- 交付前运行 `python3 scripts/check_dts_multiselect_cache.py <dts-or-zip> ...`；任何受影响规则仍为 `iscached=true` 都阻断交付。

## SQL 兼容默认值

- 先从服务流程 resource、数据源配置或目标环境证据确认数据库产品和版本；未确认时只可做通用静态检查，不能宣称内嵌 SQL 可运行。
- DSL `String.trim(...)` 与数据库 SQL `TRIM(...)` 是两个能力目录；脚本函数存在不能证明同名 SQL 函数存在。对旧版 SQL Server 等明确不支持裸 `TRIM` 的目标，独立 DTS 和服务流程内嵌规则都必须扫描为 0 命中，并用目标方言支持的等价表达式；可运行 `python3 scripts/check_dts_sql_dialect.py --dialect sqlserver-legacy <paths...>`。
- 官方平台节点模板默认把 SQL 写成单个字符串，不用 `+` 拼接多段；本地 engine 接受拼接不能证明目标平台节点接受。目标版本有可复现实例时可覆盖该默认值。
- SWC 场景默认不用嵌套子查询/`EXISTS`，改为先窄查 ID、再分步查询或参数化批处理；目标环境证据确认支持时可调整。
- 表名、列名、排序方向、资源别名和 `@ROUTE` 不接受用户字符串直拼，必须来自目标环境白名单证据。

`bizQuery` 不是嵌入式 SQL。不得把嵌入式 SQL 的 `IN` 集合展开语义套到 `bizQuery` 等值过滤；列表参数必须使用目标版本已验证的原生查询方式。`requires` 在每个调用点必须确定非空；自定义函数不得依赖外层局部变量或闭包，除非目标 runtime 已用最小样本证明支持，应优先改成显式形参或函数内常量。

## 选择模板

- 单值：`query_value`
- 单行只读/可修改：`query_row` / `query_row2`
- 多行只读/可修改：`query_list` / `query_list2`
- 单列：`query_column`
- 单次 DML：`execute_update`
- 同构批量 DML：`execute_batch`
- 存储过程：`execute_call`，并按目标数据库区分 function/procedure 调用形式

## 官方模板能力落点

| 需求 | 生成策略 |
|---|---|
| 条件批量删除/更新 | 先用同条件只读预检并取得主键，再构造二维 batch，最后执行带主键 `WHERE` 的 `execute_batch`；写入仍受批准范围和 `max_rows` 约束 |
| 单值/单行/列表查询 | 分别选择 `query_value`、`query_row`/`query_row2`、`query_list`/`query_list2` |
| 批量插入 | 校验每行参数数和类型一致后使用二维 batch；ID 来源必须已确认 |
| 多表关联且目标库限制子查询 | 先查主表窄 ID 集，再按单组参数循环或分批查询子表；不得把二维参数传给 `query_column` |

这些是生成结构，不是写入授权；生产或数据库写操作继续执行 `database-dml-contract.md`。
