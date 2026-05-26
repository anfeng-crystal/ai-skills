# DB Query Migration Boundary

来源下载素材 `db-query` 是数据库直连和 OpenAPI 降级查询工具，主要由 PowerShell、Java class、JDBC jar 和 `.dts` 脚本服务资产组成。

## Not Migrated

本次未迁移 `db-query/libs` 和 `db-query/tools`，原因：

- 当前计划的 Agent B 交付重点是 KSQL 校验、预置数据脚本生成和项目级 `config.ini` 管理。
- `db-query` 依赖 PowerShell/JDBC 运行链路，与本 skill 已迁移的 Python KSQL 生成器不是同一套执行入口。
- `libs` 内含二进制 jar/class 和脚本服务定义文件；按计划若迁移需要 manifest 和更完整的运行时契约，适合后续独立纳入数据库查询 runtime。

## Source Assets Observed

| Source file | sha256 |
|---|---|
| `db-query/libs/ojdbc8-21.1.0.0.jar` | `0ffdd8cf8b5012ef3b3c810ddbbaafc7c14bdcf93324d2cab45b0de79b2bde19` |
| `db-query/libs/postgresql-42.7.5.jar` | `69020b3bd20984543e817393f2e6c01a890ef2e37a77dd11d6d8508181d079ab` |
| `db-query/libs/DbQuery$ConnInfo.class` | `b30b4a23528118812ec2468d3fad1896cc9d304d2518f3400cecb2b48d8585ab` |
| `db-query/libs/DbQuery.class` | `7ccaa17ac776000014fa4808587c8a8fc239044864e03551ff2e86fc9bc2289b` |

## Reuse Guidance

如用户要求真实数据库只读查询，先确认环境、路由、库、表和授权边界。若未来迁移 `db-query` runtime，应补齐：

- jar/class/dts manifest
- Java/JDK 发现策略
- 连接配置脱敏模板
- OpenAPI 降级的 scope 和凭据规则
