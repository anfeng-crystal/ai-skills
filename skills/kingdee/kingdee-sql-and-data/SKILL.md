---
name: kingdee-sql-and-data
description: Use when validating Kingdee Cosmic KSQL, generating preset-data DELETE plus INSERT scripts, resolving project ksql config.ini, or doing read-only database data checks for Kingdee projects.
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [kingdee, cosmic, ksql, data, database]
---

# Kingdee SQL And Data
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## Use This For

- 校验金蝶苍穹 KSQL 兼容性，尤其是 `UPDATE FROM`、`JOIN` 混用、`LIMIT/OFFSET`、`WITH` 等方言差异。
- 从苍穹数据库生成预置数据脚本，包括编码规则、导入导出模板、订阅事件、权限项、调度计划、基础资料和 OpenAPI 服务。
- 解析项目级 KSQL 配置文件，并避免把真实数据库凭据提交到 Git。
- 做只读数据核对方案；涉及真实查询前必须确认环境、路由、库、表和凭据边界。

## Quick Commands

```bash
SQL_SKILL_ROOT=<当前 kingdee-sql-and-data skill 根目录>
python3 "$SQL_SKILL_ROOT/scripts/validate_ksql.py" "select top 10 * from T_BD_MATERIAL"
python3 "$SQL_SKILL_ROOT/scripts/config_resolver.py" --cwd <project-root> --print
python3 "$SQL_SKILL_ROOT/scripts/git_secret_guard.py" --repo <project-root> --json
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

## Boundaries

- 默认只做 KSQL 校验、脚本生成、配置解析或只读核对；不连接生产库、不执行 DML、不写入业务数据。
- 真实查询前必须确认环境、路由、库、表、数据范围、凭据来源和只读边界；生产查询必须再次确认并限制分页/超时。
- 生成 `DELETE` / `INSERT` 预置数据脚本默认只是审阅稿；执行脚本、连接生产、写文件或覆盖已有脚本前必须二次确认目标环境和回滚方案。
- `config_resolver.py --print`、错误栈和报告输出必须脱敏数据库连接串、host/schema、账号、密码、tenant、token、内部 URL 和业务敏感字段值。
- `scripts/git_secret_guard.py` 只做只读检查，不修改 Git、配置或源码。
- `templates/config.example.ini` 是脱敏模板，不应写入真实密码。
- 未迁移 `db-query/libs` 的 JDBC/PowerShell 资产；原因见 `references/db-query.md`。
