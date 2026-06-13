# Kingdee Cosmic Agent Skills

金蝶云苍穹(Cosmic / 星瀚)二次开发的一组 Agent Skill,兼容 **Claude Code** 与 **Codex**(均以 `SKILL.md` 为约定)。结构可移植:仓库相对/占位路径,无硬编码用户目录,无本地环境依赖。

## 技能清单

| Skill | 适用场景 | 使用方式 |
|---|---|---|
| `kingdee-cosmic` | 苍穹 Java 二开主控:插件、工作流、BOTP、OpenAPI 服务端、DynamicObject、诊断、代码质量 | 描述 Java 二开/插件/诊断需求即触发;字段证据自动转 metadata-analyzer,SDK 签名转 sdk-helper,报表转 kingdee-report |
| `kingdee-report` | 报表插件取数、DataSet/Algo 流水线、GroupbyDataSet 聚合、Algo API 精确签名 | "写报表取数插件""DataSet 怎么 JOIN/聚合""Algo leftJoin 签名" |
| `kingdee-metadata-analyzer` | 元数据取证:实体/字段/插件挂载点/字段读写/依赖;跨环境 diff、基础资料引用检查、导出 | "查实体字段""分析插件挂载""对比 dev/test 元数据差异""检查基础资料引用" |
| `kingdee-sdk-helper` | SDK 类定义、方法签名、Javadoc、API 归属查询 | "SaveServiceHelper 怎么用""这个方法在哪个包" |
| `kingdee-kingscript` | KingScript 脚本插件:SDK 声明、语法、运行错误、风险审查 | "写 KingScript 脚本""KingScript 基类×事件" |
| `kingdee-frontend-script` | 前端页面脚本/扩展 JS(index.js/index_m.js)/表格树自定义渲染/前后端通信/自定义 CSS | "页面脚本字段联动""扩展 JS 移动端入口""给字段加自定义样式" |
| `kingdee-openapi-client` | 调用苍穹/星瀚 OpenAPI:OAuth2 取 token、queryOpenApi、参数探测、Java/Python 调用代码 | "调用 OpenAPI 提交单据""getToken 怎么刷新""生成 Java 调用代码" |
| `kingdee-isc-service` | 集成服务云(ISC)报错离线诊断:值转换/事件触发/字段映射/数据库/EAS/连接/OpenAPI/性能 | 提供 DC 错误日志或报错关键词即诊断;纯离线只读 |
| `kingdee-cosmic-devtools` | KDDT 工程创建、插件类生成、资源包 staging/apply/rollback | "用 KDDT 建工程""拉取/更新资源包" |
| `kingdee-cosmic-login` | 测试环境登录、数据中心列表、Cookie/CSRF 验证 | "登录苍穹测试环境""列数据中心" |
| `kingdee-sql-and-data` | KSQL 兼容性校验、预置数据脚本生成、项目级 SQL 配置、只读数据核对 | "校验这段 KSQL""生成预置数据脚本" |
| `kingdee-testing` | 单元测试生成、Gradle 测试运行、本地 Java harness、运行时验证 | "给这个插件写单测""跑 Gradle 测试" |
| `kingdee-security-review` | 安全审计、OpenAPI 端点审查、漏洞验证、POC、红队 lite | "审计这个 OpenAPI 端点""检查越权" |
| `iscb-script` | ISCB 集成云 DSL 脚本:编写/解释/重构、值转换规则、服务流程节点、自定义 API/WebAPI 脚本,按需校验 | "写一个 ISCB 数据集成脚本""值转换规则脚本怎么写" |

## 安装

两宿主统一由 `skills/meta/skill-installer` 管理(macOS/Linux 用 symlink,Windows 用 junction):

```bash
# 预览(dry-run)
node skills/meta/skill-installer/bin/skill-installer.mjs --tool claude-code --tool codex --json
# 确认无 conflict 后应用
node skills/meta/skill-installer/bin/skill-installer.mjs --tool claude-code --tool codex --apply
```

- Claude Code 目标目录:`~/.claude/skills`
- Codex 目标目录:`~/.codex/skills`

也可手动把所需 skill 目录软链到对应宿主 skills 目录。详见 `adapters/claude-code/adapter.md`、`adapters/codex/adapter.md`。

## 可移植性约定
- 路径用仓库相对或占位符(`<active-root>`、`{api_host}` 等),不写用户主目录;详见 `shared/platform/path-policy.md`。
- 不含真实地址、账号、密码、内网信息;示例一律占位。
- 部分技能依赖大文件/二进制(如 SDK 索引、反编译器 jar、ISCB 运行时 jar)。再分发已获授权(2026-06-13),随仓库 `publish`;第三方开源 jar(CFR、JavaParser)按其自身 license 保留并在 NOTICE 标注。详见 `cleanup/publish-authorization-matrix.md`。

## 协作边界(避免重复/误触发)
查询(metadata-analyzer / sdk-helper)与实现(cosmic / report / frontend-script)、脚本(kingscript)、集成(openapi-client / isc-service)、工程(devtools)、登录(login)、数据(sql-and-data)、测试(testing)、安全(security-review)各司其职;每个 skill 的 `evals/trigger_eval.json` 含正负例界定边界。
