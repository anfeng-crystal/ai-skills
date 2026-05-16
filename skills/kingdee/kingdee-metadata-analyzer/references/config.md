# 配置说明

## 项目入口
- 项目配置表：`${AI_KNOWLEDGE_ROOT}/kingdee/cosmic/projects/config-table.md`
- 项目配置文件：表中 `ok-cosmic 配置` 列指向的 `ok-cosmic.json`

## metadataAnalyzer
| 字段 | 说明 |
|---|---|
| `enabled` | 是否允许连接元数据数据库并采集插件清单 |
| `envFiles` | 可选，项目级 `.env` 文件列表；相对路径按项目根目录解析 |
| `database.host` | PostgreSQL 主机 |
| `database.port` | PostgreSQL 端口 |
| `database.dbname` | 元数据库名 |
| `database.user` | 只读数据库用户 |
| `database.passwordEnv` | 可选，数据库密码变量名；可来自当前进程环境变量或 `.env` 文件 |
| `database.envFiles` | 可选，数据库凭据专用 `.env` 文件列表；优先级低于项目级 `envFiles` 的同名变量 |
| `database.password` | 兼容既有项目配置的明文密码字段；不要在新模板或报告中新增、复制或展示 |
| `database.schema` | 元数据表所在 schema |
| `workspace.projectRoot` | 二开源码根目录 |
| `jarLibPaths` | 苍穹服务端 JAR 搜索目录 |
| `decompiler.enabled` | 是否允许 CFR 反编译 |
| `decompiler.cfrJarPath` | CFR JAR 路径 |
| `output.reportDir` | 分析产物输出目录 |

## 凭据解析顺序
脚本按以下顺序解析数据库密码，命中后停止，并且任何输出都只能写来源类型，不能写密码值：

1. 当前进程环境变量：`database.passwordEnv` 指定的变量名。
2. `.env` 文件中的同名变量：先读 `metadataAnalyzer.envFiles`，再读 `database.envFiles`。
3. 约定 `.env`：`ok-cosmic.dev.json` 会尝试 `ok-cosmic.dev.env`，然后尝试配置目录 `.env` 和项目根目录 `.env`。
4. 既有 JSON 兼容字段：`metadataAnalyzer.database.password`。

推荐新项目使用项目级 `.env` 或同名 `.env`，避免把多个项目密码都放到全局 shell 环境变量里。已经存在的本地 `ok-cosmic.json` 可以继续被读取，但不要把密码写进 skill、报告、模板或聊天输出。

## 安全规则
- 不在 skill、报告、模板或聊天输出中写数据库密码值。
- 新建配置优先用 `.env`；既有配置含 `password` 字段时只兼容读取，不主动扩散。
- `enabled=false` 时只能做配置检查，不连接数据库。
- 相对输出目录按项目根目录解析。
