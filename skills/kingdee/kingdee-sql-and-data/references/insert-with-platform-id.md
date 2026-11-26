# 用 SQL 新增苍穹记录

只出方案时，确认目标实体、数据库路由、必填列、主外键、唯一约束及业务操作依赖，SQL 中保留绑定参数。取正式 ID 和写入放在已批准的执行阶段。直接 INSERT 只完成数据库写入。业务要求触发保存插件、正式编号、审核或缓存刷新时，须核实对应机制。

## 按物理键选取号方式

| 已核实的键策略 | 做法 | 契约中的 `key_source` |
|---|---|---|
| 目标实体使用平台 long 主键 | 在目标集群已有的服务端执行入口调用 `kd.bos.id.ID.genLongId()` 或 `genLongIds(n)`，按 64 位整数绑定 | `platform-long` |
| 目标实体使用平台 Base39 字符串主键 | 同一入口调用 `ID.genStringId()` 或 `genStringIds(n)`，原样绑定。字段约定为 `Uuid16` 时，`Uuid16.create().toString()` 在已核实的 7.0 实现得到同类值 | `platform-base39` |
| 数据库负责发号 | 按目标列 DDL 和实体约定使用既有 identity、默认值或序列，按目标方言取回数据库实际生成的键 | `database-generated` |
| 目标表复用父键、组合键、自然键或已确认的迁移键 | 按真实映射绑定相应键列。需要独立行键的分录、多语言行单独取号 | `mapped-key` |

只有数据库连接时，先查目标列已有的生成机制及本批已经由目标平台分配的 ID。需要平台号时，复用已授权的目标运行时、现有发号接口或本批预分配清单，将实际返回值作为参数带入 SQL。运行在开发机的代码也须确认它使用目标集群的发号服务。仅有 JAR 和 JDBC 连接时，不能把 Java 方法当 SQL 函数。若上述途径均缺失，仍交付带占位参数的新增方案，并标明缺哪个目标环境的取号入口。

本地 7.0 的 `IDGenner` 使用毫秒差、worker 和同毫秒序列。自行拼雪花号、`MAX(fid)+1`、随机 UUID 或 Base36 都无法替代该实体的平台主键约定。实现细节与字符顺序见[分布式 ID](../../kingdee-cosmic/references/base/sdk/sdk-id.md)。[金蝶 ID 使用说明](https://developer.kingdee.com/article/116221178603181568)

## 从取号到回读

1. 按业务键盘点待新增集合，如“组织 + 编码”。为每个逻辑行保留稳定的来源标识，核对已存在、重复和冲突行。主表、分录、子分录及多语言行分别确认哪些列是自己的主键，哪些列指向父行。更新已有记录时沿用原键。
2. 只为确需新号的行取号。下面假设一条表头带两条分录，三行都有独立的 long 主键。将每个返回值绑定到具体行，核对数量、唯一性与映射。批量返回的 ID 逐个使用，不能按首号推算后续值。跨 JSON 或工作簿传递 long 时保留十进制文本，数据库驱动绑定时转回精确整数。

   ```java
   long headerId = kd.bos.id.ID.genLongId();
   long[] entryIds = kd.bos.id.ID.genLongIds(2);
   ```

   下列为 JDBC 参数模板。按实际 schema、列、键类型和必填字段替换示意表，每条语句均使用同一目标事务。

   ```sql
   INSERT INTO example_header (fid, fnumber) VALUES (?, ?);
   INSERT INTO example_entry (fentryid, fid, fseq) VALUES (?, ?, ?);
   ```

   第一条绑定 `(headerId, number)`。第二条分别绑定 `(entryIds[0], headerId, 1)` 和 `(entryIds[1], headerId, 2)`。仅追加分录时从目标业务键查得既有 `headerId`，只给两条新分录分配行键。
3. 事务内复核缺行与预期数量。契约按目标数据库选 `unique-constraint`（约束或唯一索引覆盖业务键）或 `serialized-write`（覆盖该范围所有写入者的串行化措施），记录约束定义或具体的锁、隔离与冲突处理依据。单次 `NOT EXISTS` 查询无法排除并发插入。任何键冲突先核对，不用覆盖、忽略冲突或先删再插来凑行数。
4. 记录实际写入的主键、业务键和行快照。提交前按批准集合检查受影响行数、必填列、父子引用及孤儿。提交后用新事务从目标写库按业务键和主键独立回读。提交结果未知时先按原映射核对。整批与本次写入一致则记录已完成，确认已回滚且全部缺失才按当前范围重试。部分存在、值不同或有外来占用时先查清。撤销已提交新增时，在同一事务内核对并保护后续引用，按子到父以主键和写后快照或可靠行版本为条件删除，精确核对删除数。出现差异即回滚。

**编码规则示例。** 新建规则时，先确认规则所属业务对象、应用范围、分段定义以及目标库的实际表结构。现有预置生成器读取的 `T_CR_CODERULE`（规则头）、`T_CR_CODERULEENTRY`（分段）、`T_CR_CODERULE_L`（名称）可作为核对起点。按目标映射为独立的行键取号，分段和名称行引用同一规则头。格式、日期和流水由业务编码规则决定。按用户要求验证启用状态和编号示例。仅预览时使用预览入口，避免消耗正式业务流水。

## 新增契约示例

以下示意一个表头。以实际证据替换发号入口、表、约束及行数。同批分录按其物理键和稳定业务键另列契约。已批准执行沿用 `mode=execute-approved` 和 `approval_ref`。

```json
{
  "version": 1,
  "mode": "plan-only",
  "operation": "insert",
  "change_kind": "direct",
  "environment": "dev",
  "target": {"database": "example_db", "schema": "example_schema", "table": "example_header", "key_columns": ["fid"]},
  "scope": {"where_sql": "source.fnumber = :number", "expected_rows": 1, "max_rows": 1},
  "stage": {"enabled": true, "unique_key": ["fnumber"], "rejects_unmapped": true},
  "insert": {
    "key_source": "platform-long",
    "evidence_ref": "示例实体的 long 主键映射及同集群服务端 ID.genLongId() 调用位置",
    "business_key": ["fnumber"]
  },
  "assignments": [
    {"column": "fid", "nullable": false, "mapping_missing": "stop"},
    {"column": "fnumber", "nullable": false, "mapping_missing": "stop"}
  ],
  "transaction": true,
  "before_image": {"confirm_absent": true},
  "concurrency": {"absence_guard": "unique-constraint", "evidence_ref": "示例表上覆盖 fnumber 的唯一约束定义"},
  "verification": {"exact_affected_rows": true, "postcheck": true, "capture_inserted_rows": true},
  "rollback": {"compare_before_delete": true},
  "failure_recovery": {"rollback": true, "recompute_scope": true}
}
```
