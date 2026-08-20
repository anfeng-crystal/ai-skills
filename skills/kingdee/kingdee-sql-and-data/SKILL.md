---
name: kingdee-sql-and-data
description: Use when validating Kingdee Cosmic KSQL, generating preset-data scripts, resolving project ksql config.ini, performing scoped read-only data checks, generating reviewable DDL from verified metadata, or preparing an approved database change contract. ISCB DML service-flow generation routes to iscb-script.
license: MIT
metadata:
  author: "anfeng"
  version: "1.1.0"
  tags: "kingdee, cosmic, ksql, data, database"
---

# Kingdee SQL And Data
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 触发与路由

- 处理 KSQL 兼容性、预置数据脚本、项目 KSQL 配置、只读数据核对、元数据到 DDL 和已批准的数据变更契约。
- 字段到物理表/列、类型和 dbRoute 的事实先交 `kingdee-metadata-analyzer`；ISCB 参数化 SQL 或 DML 服务流程交 `iscb-script`。
- Java 插件实现、KingScript 和安全 POC 分别交 `kingdee-cosmic`、`kingdee-kingscript`、`kingdee-security-review`。

## 模式与契约

| 模式 | 动作边界 |
|---|---|
| `validate` | 本地校验 KSQL、配置或生成器输入，不连接数据库 |
| `generate` | 生成预置数据审阅稿或 DDL 文件，不执行数据库动作 |
| `query-readonly` | 环境、路由、库/schema、表、字段、过滤范围、分页/超时、凭据来源和授权已知时执行只读查询；生产只读契约完整后不重复确认 |
| `execute-approved` | 只执行已批准的环境、对象、SQL/DDL、影响范围、变更窗口、备份/回滚和授权引用；契约完整后不重复确认或扩范围 |

缺少契约字段时输出 `contract_incomplete`；运行工具不可用时输出审阅稿或 `generated_not_executed`，不能声称数据库已变更。

用户说“创建 SQL 修改计划/先出方案/我来审核”时只进入计划态：允许只读元数据和窄查询，不执行 DDL/DML。只有后续明确批准精确方案后才切换 `execute-approved`。

## 工作流与动作

```bash
SQL_SKILL_ROOT=<当前 kingdee-sql-and-data skill 根目录>
python3 "$SQL_SKILL_ROOT/scripts/validate_ksql.py" "select top 10 * from T_BD_MATERIAL"
python3 "$SQL_SKILL_ROOT/scripts/config_resolver.py" --cwd <project-root> --print
python3 "$SQL_SKILL_ROOT/scripts/git_secret_guard.py" --repo <project-root> --json
python3 "$SQL_SKILL_ROOT/scripts/metadata_to_ddl.py" inspect --metadata <schema.json> --dialect postgresql
python3 "$SQL_SKILL_ROOT/scripts/metadata_to_ddl.py" generate --metadata <schema.json> --dialect postgresql --output <schema.sql>
python3 "$SQL_SKILL_ROOT/scripts/validate_change_contract.py" --contract <change-contract.json>
```

生成预置数据脚本时，先解析配置，再显式传入生成器：

```bash
CONFIG=$(python3 "$SQL_SKILL_ROOT/scripts/config_resolver.py" --cwd <project-root> --print)
python3 "$SQL_SKILL_ROOT/scripts/ksql_generate/cli.py" generate --type coderule --entity bd_currency --config "$CONFIG"
```

## References

- `references/ksql-spec.md`：KSQL 语法规范和兼容性细节。
- `references/preset-data-script.md`：预置数据脚本生成器的类型、参数和输出规则。
- `references/config-management.md`：项目级 `config.ini` 发现顺序、模板和凭据规则。
- `references/db-query.md`：直连数据库和 OpenAPI 降级查询的迁移边界。
- `references/metadata-ddl-contract.md`：归一化元数据、DDL 生成器和执行契约。
- `references/approved-data-change.md`：生产数据修改计划、批准执行、失败恢复和防 NULL/并发覆盖门禁。

## 门禁与失败

- 表/列、类型、dbRoute、方言和字段映射没有元数据证据时不得猜；未知类型不得静默回退为 `VARCHAR(255)`。
- 生产数据先按“元数据库 → entity/field/entry 映射 → 目标业务库/物理表 → 窄化范围”取证；同一物理表上的不同实体、阶段或布局不能互相代替。
- 生产更新计划或批准执行前必须读 `references/approved-data-change.md` 并通过 `validate_change_contract.py`。组织/基础资料映射缺失时默认保留旧外键或停止该行；不可空列不得写 `NULL`。
- 字符串展示字段与外键映射分别定义阶段范围；某阶段不更新展示字符串，不代表其它阶段或共用外键也不更新，反之亦然。
- 任一执行失败后先确认事务回滚，再基于当前数据重新计算范围、冲突和预期行数；不得复用失败前计数继续执行。
- 生成 `DELETE` / `INSERT` 预置数据脚本默认只是审阅稿；执行时进入 `execute-approved`，严格限制目标和回滚契约。
- DDL 生成器只输出 CREATE TABLE/INDEX；不读取数据库凭据、不生成 DROP/ALTER、不执行数据库操作。
- `config_resolver.py --print`、错误栈和报告输出必须脱敏数据库连接串、host/schema、账号、密码、tenant、token、内部 URL 和业务敏感字段值。
- `scripts/git_secret_guard.py` 只做只读检查，不修改 Git、配置或源码。
- `templates/config.example.ini` 是脱敏模板，不应写入真实密码。
- 未迁移 `db-query/libs` 的 JDBC/PowerShell 资产；原因见 `references/db-query.md`。

## 验证与输出

- KSQL：报告规则命中、方言风险和未确认项。
- 预置数据/DDL：报告输入证据、输出文件、生成未执行状态和执行契约缺口。
- 真实查询/写入：报告模式、环境、精确范围、受影响行数或只读结果摘要、回滚状态；不回显凭据或敏感数据。
- 修改本 skill 的脚本后运行 `python3 -m unittest discover -s scripts/tests -p 'test_*.py'`。
