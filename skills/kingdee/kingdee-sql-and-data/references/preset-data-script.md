# Preset Data KSQL Script Generation

本资料来自下载素材 `ksql-script-generator/SKILL.md`，保留为详细参考；`SKILL.md` 只放入口和边界。

## Capability

生成器从关系型数据库查询苍穹预置数据，并输出逐行交替的 `DELETE` + `INSERT` KSQL 脚本。支持 PostgreSQL、MySQL、Oracle、SQL Server。

支持类型：

| type | 参数 | 数据库 | 说明 |
|---|---|---|---|
| `coderule` | `--entity` | Sys_DB | 编码规则 |
| `import` | `--entity` | Sys_DB | 导入导出模板 |
| `event` | `--entity` | Workflow_DB | 订阅事件 |
| `perm` | `--number` | Sys_DB | 权限项 |
| `schdule` | `--number` | Sys_DB | 调度计划，沿用来源工具的拼写 |
| `basedata` | `--entity --filter` | Meta_DB + Biz_DB | 基础资料预置数据 |
| `openapi` | `--number` | Sys_DB | 开放 API 服务 |

## Usage

先解析配置：

```bash
CONFIG=$(python3 scripts/config_resolver.py --cwd /path/to/project --print)
```

再显式传入生成器：

```bash
python3 scripts/ksql_generate/cli.py generate --type coderule --entity bd_currency --config "$CONFIG"
python3 scripts/ksql_generate/cli.py generate --type perm --number QXX0114,QXX0115 --config "$CONFIG" -o perm_script.sql
python3 scripts/ksql_generate/cli.py generate --type basedata --entity bd_currency --filter "fnumber in ('CNY','USD')" --config "$CONFIG"
python3 scripts/ksql_generate/cli.py serve --config "$CONFIG"
```

## Output Rules

- 每张表输出 `DELETE FROM ... WHERE ...;` 后紧跟对应 `INSERT INTO ... VALUES ...;`。
- 主表默认按 `FID` 删除。
- 多语言表 `_L` 默认按 `FPKID` 和 `FID` 删除。
- 分录表默认按 `FENTRYID` 删除。
- 日期时间格式化为 `ts{'yyyy-MM-dd HH:mm:ss'}`。
- 字符串单引号转义为两个单引号。
- `NULL` 直接输出，不加引号。

## Dependencies

Python 3.10+。按数据库类型安装对应 DB-API 驱动：

```bash
pip install psycopg2-binary  # PostgreSQL
pip install pymysql          # MySQL
pip install oracledb         # Oracle
pip install pymssql          # SQL Server
```

## Review Notes

- `basedata` 会读取元数据库实体 XML 并按表分组生成脚本，生成前要确认过滤条件足够窄。
- 生成器会连接真实数据库；不要用模板配置直接运行。
- 输出脚本执行前必须按目标环境人工复核 DELETE 条件。
