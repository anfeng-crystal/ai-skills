# 已批准数据变更契约

用于生产或重要环境的数据修改计划与批准执行。计划阶段只读；执行阶段只运行用户已批准的精确对象、范围和 SQL，不把凭据或业务值写入报告。

## 元数据与范围

1. 先从目标环境元数据库确认 entity、field、entry、物理列、可空性和 dbRoute，再进入目标业务库/表做窄查询。同一物理表上的不同实体、阶段或布局必须分别确认业务入口和字段语义。
2. 把目标拆成独立赋值规则。外键、展示字符串、阶段字段分别列适用范围，不能因一列共表而扩大另一列范围。
3. stage 中保留业务主键、旧值、目标值、映射证据和拒绝原因；对 key、目标值和映射做唯一性检查。
4. 对不可空列，映射缺失只能 `preserve_old` 或 `stop`。只有用户明确批准、列允许空且业务语义要求清空时，才可写 `NULL`。

### 关系重建

- 区分权威外键、旧目标值和业务编码。正在被修复/重建的目标列不能作为唯一关联键，除非目标环境已证明它与权威关系双射。
- 预检至少输出源记录数、唯一目标数、冲突组数、未映射数和源/目标 ID 集合差集；业务验收使用目标 ID 集合相等，不以“看起来接近”的计数代替。

### 实体迁移

- 枚举完整存储拓扑：主表、多语言 `_L`、分录/子分录、关系/多选表，以及引用基础资料是复用还是迁移。
- 每类表使用 `present` 或 `confirmed_absent`，并给非占位的 `evidence_ref`；空数组本身不能证明该类表不存在，主表必须至少一张。
- 为每张已确认表分别记录父键、旧新 ID 映射、结构化导入顺序、迁移前后行数检查和孤儿检查。未完成显式枚举时，不得称迁移范围完整。

### 症状修复

- 批量 SET 前建立因果目标：异常与正常样本、真实页面/formId、字段读取/布局路由链、活动流程实例、每个 SET 列如何影响症状，以及业务级后置断言。
- 只有分组相关性、状态分布或字段名猜测时保持只读；用户补充业务状态矩阵不自动授权把历史数据全量归一化。

## 事务执行

- 在单一事务中重算 stage 和待更新数，要求 `expected_rows <= max_rows` 且实际命中等于批准计数。
- 更新前保存 before image；UPDATE 的 WHERE 同时比较主键与旧值，防止覆盖并发变化。
- SQL 只从已验证 stage 取目标值；stage 中存在重复 key、未映射、冲突或越界行时停止，不做部分提交。
- 检查精确影响行数、目标一致性、残留异常和备份完整性后才提交。任何门禁失败都回滚。
- 回滚也必须 compare-before-restore：只有当前值仍等于本次目标值时才恢复旧值；检测到后续修改则停止并报告。

## 失败恢复

数据库报错或执行回滚后，先确认事务状态和 DDL 副作用。然后重新读取当前目标数据、映射和约束，重新生成 stage、冲突清单、`expected_rows` 和备份计划；不能沿用失败前的 56/142/560 等旧计数或旧 stage。

若出现 `NOT NULL` 违规，直接追查哪个赋值表达式或连接把目标列变成 `NULL`；不能只根据失败行里其它空字段推断。修订计划必须补齐未映射策略和不可空列断言。

## 可验证 contract

```json
{
  "version": 1,
  "mode": "plan-only",
  "change_kind": "direct",
  "environment": "prod",
  "target": {
    "database": "target_db",
    "schema": "public",
    "table": "target_table",
    "key_columns": ["fid"]
  },
  "scope": {
    "where_sql": "bounded predicate",
    "expected_rows": 10,
    "max_rows": 10
  },
  "stage": {
    "enabled": true,
    "unique_key": ["fid"],
    "rejects_unmapped": true
  },
  "assignments": [
    {
      "column": "fk_target_org",
      "nullable": false,
      "mapping_missing": "preserve_old"
    }
  ],
  "transaction": true,
  "before_image": {"enabled": true},
  "concurrency": {"compare_old_values": true},
  "rollback": {"compare_before_restore": true},
  "verification": {"exact_affected_rows": true, "postcheck": true},
  "failure_recovery": {"rollback": true, "recompute_scope": true}
}
```

`mode=execute-approved` 时额外要求非空 `approval_ref`。`change_kind` 可为 `direct`、`relationship-remap`、`entity-migration` 或 `symptom-repair`；后三种还必须分别提供 `relationship`、`storage_topology` 或 `causal_target` 证据对象。运行：

`entity-migration` 的 `storage_topology` 使用以下结构；`unknown`、`tbd`、`n/a` 等占位值不能通过：

```json
{
  "enumerated": true,
  "classes": {
    "main": {"status": "present", "tables": ["t_main"], "evidence_ref": "metadata mapping ref"},
    "multilingual": {"status": "confirmed_absent", "tables": [], "evidence_ref": "field storage audit ref"},
    "entries": {"status": "confirmed_absent", "tables": [], "evidence_ref": "entry metadata audit ref"},
    "relations": {"status": "confirmed_absent", "tables": [], "evidence_ref": "relation metadata audit ref"}
  },
  "reference_strategy": "reuse verified target references",
  "import_order": ["t_main"],
  "parent_keys": {"t_main": "root table; primary key fid"},
  "id_mapping": {"t_main": "old fid to new fid mapping"},
  "row_count_checks": {"t_main": {"before": "bounded source count", "after": "exact target count"}},
  "orphan_check": true
}
```

```text
python3 scripts/validate_change_contract.py --contract change-contract.json
```

退出码 `0` 表示契约门禁齐全，`1` 表示安全门禁缺失，`2` 表示输入格式错误；它不连接数据库，也不代表 SQL 已执行。
