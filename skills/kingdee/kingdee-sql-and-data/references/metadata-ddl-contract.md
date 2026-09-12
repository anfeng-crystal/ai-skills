# 元数据到 DDL 契约

## 输入证据

DDL 生成前先用 `kingdee-metadata-analyzer`、当前项目元数据文件或目标环境只读查询确认：物理表、字段列名、字段类型、长度/精度、可空性、主键、索引和 `dbRoute`。表单字段标识不能直接当物理列名。

生成器只接受归一化 JSON：

- 根字段：`table`（或 `table_name`）、可选 `db_route`、`columns`（或 `fields`）、可选 `indexes`。
- 列字段：`name`（或 `column_name`）、`type`（或 `data_type`）、`nullable`；字符串必须给 `length`，decimal 必须给 `precision` 和 `scale`，主键用 `primary_key=true`。
- 索引字段：`name`、`columns`、可选 `unique`。

未知类型、缺失长度/精度、非法标识、重复列/索引、索引引用未知列或 `default`/`default_sql` 都必须失败；不得静默回退为 `VARCHAR(255)`。

## 确定性生成器

```text
python3 scripts/metadata_to_ddl.py inspect --metadata <schema.json> --dialect postgresql
python3 scripts/metadata_to_ddl.py generate --metadata <schema.json> --dialect postgresql --output <schema.sql>
```

支持 `postgresql`、`mysql`、`oracle` 的共同基础类型：`string`、`text`、`integer`、`bigint`、`decimal`、`boolean`、`date`、`datetime`、`binary`。生成器只生成 `CREATE TABLE` 和显式索引，不生成连接配置、不读取数据库凭据、不执行 DDL、不生成 DROP/ALTER。

这些是本地生成器的目标方言，不代表已生成符合二开安装包要求的 KSQL。用于二开安装包时还需单独确认 KSQL 兼容性；不能把某数据库方言生成通过写成安装包可移植性验证通过。依据：[二开安装包制作](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=475348205593507584&id=43334364940533760&type=Knowledge&productLineId=29&lang=zh-CN)的 SQL 上传说明（更新于 2026-07-30，未标最低版本）。

输出已存在时必须显式传 `--overwrite`。路径使用 UTF-8，支持空格和当前平台分隔符；POSIX 上也兼容相对 Windows `\` 分隔符。

## 执行契约

- `inspect` / `generate` 是本地只读或本地文件生成，不代表数据库应用成功。
- 若用户另行要求执行 DDL，必须先具备环境、数据库路由、schema、对象清单、变更窗口、影响评估、备份/回滚、授权引用和执行工具；契约完整后可按批准范围执行，不重复确认。
- 生产只读元数据核对在目标、范围、授权、分页/超时已知时可以直接执行。
- 数据库执行工具不可用时输出 `generated_not_executed`；不得用本 skill 的生成器假装已部署。
