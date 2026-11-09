# 配置与环境

## 定位输入

从当前目录向上定位项目根。优先目标环境显式配置，其次同项目通用配置；项目索引为 `${AI_KNOWLEDGE_ROOT}/kingdee/cosmic/projects/config-table.md` 的 `ok-cosmic 配置` 列。其它环境配置仅作对照。

| 输入 | 来源与用途 |
|---|---|
| 元数据库 | `metadataAnalyzer.database`，用于实体和页面设计；不是业务库或管理中心库 |
| 数据中心 | 当前任务明确 ID 优先，其次同环境项目/登录配置的 `accountId`，缺失才按元数据库映射反查 |
| 管理中心、业务库 | 按 [业务库定位](database-routing.md) 从现有入口和路由配置确定 |
| 凭据 | 复用当前环境配置，按下文顺序解析；不为查询迁移或另建凭据 |

数据中心仅在业务路由查询中需要。路由入口自动查找项目及子模块的 `login-<env>.properties`，可用 `--login-config` 指定其它已知路径，或用 `--datacenter-id` 传入任务明确值；已有值无需复制到元数据配置。候选不唯一时补配置来源，不能任取第一条。

## metadataAnalyzer 字段

| 字段 | 说明 |
|---|---|
| `enabled` | 是否允许连接与在线采集 |
| `envFiles` | 项目级 `.env` 文件列表，相对项目根目录 |
| `database.host/port/dbname/user` | PostgreSQL 元数据库连接 |
| `database.schema` | 元数据表所在 schema |
| `database.connectTimeoutSeconds` | 连接超时秒数 |
| `database.passwordEnv` | 密码环境变量名 |
| `database.envFiles` | 凭据专用 `.env` 列表，同名变量优先级低于项目级 `envFiles` |
| `database.password` | 仅兼容既有明文配置；不复制到新模板、报告或日志 |
| `workspace.projectRoot` | 二开源码根目录 |
| `jarLibPaths` | 服务端 JAR 搜索目录 |
| `decompiler.enabled/cfrJarPath` | CFR 开关及路径 |
| `output.reportDir` | 分析产物目录；默认使用系统缓存 |

业务库定位只需连接和凭据，不依赖源码、JAR 或反编译配置。全量分析再校验相应资源。

## 密码解析

1. `passwordEnv` 指向的当前进程变量。
2. `metadataAnalyzer.envFiles`、`database.envFiles` 中同名变量。
3. 同名环境文件、配置目录 `.env`、项目根目录 `.env`。
4. 既有 `database.password`。

只输出来源类型。新配置优先用项目 `.env`；明文迁移属于配置写入，须有任务授权并保留备份与回滚。

## 运行与产物

- bootstrap 支持 `KINGDEE_METADATA_ANALYZER_PIP_INDEX_URLS` / `KINGDEE_METADATA_ANALYZER_PIP_INDEX_URL`；失败区分依赖、配置、凭据和网络。
- 产物默认使用 `KINGDEE_METADATA_ANALYZER_OUTPUT_DIR` 或系统缓存。相对 `reportDir` 仅作历史产物线索，不用于新输出。
- 输出指向 Git 工作树时会重定向缓存，除非显式使用 `--allow-git-output` 或 `KINGDEE_METADATA_ANALYZER_ALLOW_GIT_OUTPUT=1`。读取路径以脚本输出为准。
