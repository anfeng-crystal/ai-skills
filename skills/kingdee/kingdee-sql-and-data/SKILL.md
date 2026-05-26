---
name: kingdee-sql-and-data
description: Use when validating Kingdee Cosmic KSQL, generating preset-data DELETE plus INSERT scripts, resolving project ksql config.ini, or doing read-only database data checks for Kingdee projects.
metadata:
  author: anfeng
  version: "0.1.0"
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
python3 scripts/validate_ksql.py "select top 10 * from T_BD_MATERIAL"
python3 scripts/config_resolver.py --cwd /path/to/project --print
python3 scripts/git_secret_guard.py --repo /path/to/project --json
```

生成预置数据脚本时，先解析配置，再显式传入生成器：

```bash
CONFIG=$(python3 scripts/config_resolver.py --cwd /path/to/project --print)
python3 scripts/ksql_generate/cli.py generate --type coderule --entity bd_currency --config "$CONFIG"
```

## References

- `references/ksql-spec.md`：KSQL 语法规范和兼容性细节。
- `references/preset-data-script.md`：预置数据脚本生成器的类型、参数和输出规则。
- `references/config-management.md`：项目级 `config.ini` 发现顺序、模板和凭据规则。
- `references/db-query.md`：直连数据库和 OpenAPI 降级查询的迁移边界。

## Boundaries

- `scripts/git_secret_guard.py` 只做只读检查，不修改 Git、配置或源码。
- `templates/config.example.ini` 是脱敏模板，不应写入真实密码。
- 未迁移 `db-query/libs` 的 JDBC/PowerShell 资产；原因见 `references/db-query.md`。
