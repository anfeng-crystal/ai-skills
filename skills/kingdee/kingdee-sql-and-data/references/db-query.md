# 只读查询

1. 按 [业务库定位](../../kingdee-metadata-analyzer/references/database-routing.md) 取得目标环境的数据中心、路由和实际主表。只补本次查询需要的字段、分录与关联实体映射；复用已验证连接和结果，不跑全量配置分析。
2. 以用户指定编号、主键或范围参数化查询，使用 schema 限定表名、只读事务、超时和结果上限。跨库按限定关联 ID 分步读；达到上限时分页或标未完整，结束后关闭连接。
3. 按实际问题解释字段，区分无记录、NULL、0、日期缺失与页面显示为空。报表期次先确认是业务期号还是排序序号，截图列只作线索。
4. 分开说明源数据、报表处理与页面显示；本地源码不证明生产运行版本。失败按路由入口返回的阶段和错误类别处理，只补缺失证据。

只读调查不改配置、权限或数据。写入另按 [数据变更契约](approved-data-change.md)。

## 旧工具资产

旧 `db-query/libs` 的 JDBC/PowerShell、class 和 DTS 运行时未随 Skill 迁移。普通查询复用已有工具；若另行迁移，核对以下资产、JDK、连接模板及 OpenAPI scope/凭据合同。这些指纹不代表工具已安装。

| Source file | sha256 |
|---|---|
| `db-query/libs/ojdbc8-21.1.0.0.jar` | `0ffdd8cf8b5012ef3b3c810ddbbaafc7c14bdcf93324d2cab45b0de79b2bde19` |
| `db-query/libs/postgresql-42.7.5.jar` | `69020b3bd20984543e817393f2e6c01a890ef2e37a77dd11d6d8508181d079ab` |
| `db-query/libs/DbQuery$ConnInfo.class` | `b30b4a23528118812ec2468d3fad1896cc9d304d2518f3400cecb2b48d8585ab` |
| `db-query/libs/DbQuery.class` | `7ccaa17ac776000014fa4808587c8a8fc239044864e03551ff2e86fc9bc2289b` |
