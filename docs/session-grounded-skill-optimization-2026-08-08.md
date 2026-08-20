# 基于真实会话错误的 Skill 优化审计 — 2026-08-08

## 结论

- 收口快照时间为 `2026-08-08 10:00:18 +0800`；当时扫描当前与归档目录中的 303 个 JSONL 文件，确认 88 个主会话，其中当前 14 个、归档 74 个。文件总数包含随后被主会话过滤器排除的子代理文件。
- 主会话包含 1144 条用户消息；关键词仅筛出 360 条候选，随后逐条回看前一代理行为、任务授权和运行证据。会话目录是动态数据源，后续新增任务不改变本快照的证据结论。
- 本轮只对 10 个 skill 做了有证据的修补；其余 14 个保留 skill 没有发现新的高置信缺口，或现有规则已经覆盖，因此不重复堆规则。
- 这不是根据 SKILL.md 文案做静态“美化”。每项保留修改都必须形成“真实错误 → 最小规则/检查器 → 原场景回放或确定性测试”闭环。

## 证据口径

候选发现由 `skills/meta/darwin-skill/scripts/extract-session-evidence.mjs` 完成。默认同时读取 `~/.codex/sessions` 与 `~/.codex/archived_sessions`，并排除：

- `thread_source=subagent`，或 `source` 对象指向 `subagent` / `thread_spawn` 的子代理会话；
- realtime voice 会话；
- system/developer、recommended plugins、memory、环境上下文等注入块；
- 只有关键词但没有前一错误行为的消息；
- 用户新增范围、纯措辞/排版偏好，以及已由当前规则完整覆盖的历史错误。

抽取结果只是 `candidate_requires_context_review`，不能自动判定 skill 有错。确认缺陷至少需要以下一组证据：

1. 用户明确纠正，并能定位紧邻的错误方案或错误执行；
2. 真实编译、平台运行、页面、数据库或脚本输出证明先前判断错误；
3. 当前 skill 确实缺少相应门禁，且修补不会把项目专属值泛化成平台规则。

## 已修改的 10 个 Skill

| Skill | 主会话证据 | 已确认错误 | 最小修补与验证 |
|---|---|---|---|
| `iscb-script` | 见证据附录 | 批量恢复被推定成同一旧状态；SQL Server 裸 `TRIM` 反复漏扫；把 DSL 与 SQL 函数混同；列表参数、闭包、首游标、短字符串、原生节点统计和流程摘要字段处理错误；来源/状态靠名称推断；旧 DTS 与测试报文没有随字段语义一起失效；保存后初始化或普通路径覆盖终态 | 增加逐行 before-image 恢复、目标方言扫描、外发字段契约、真实值 provenance、服务流程运行契约、生命周期矩阵和 `comment/proc_digest` 规则；新增两个确定性检查器。把重复细节下沉后，主卡片从 20,403 字节降到 14,192 字节，执行级别与任务类型改为正交概念。 |
| `kingdee-sql-and-data` | 见证据附录 | 实体迁移漏 `_L`；关系重建用了待修复旧字段而非权威外键；用状态相关性替代页面故障因果链并扩大批量更新；`NOT NULL` 映射缺失仍进入执行计划；失败后沿用旧计数 | 新增批准数据变更契约和验证器，分别约束关系重建、实体迁移、症状修复；存储类别必须用 `present/confirmed_absent + evidence_ref`，空数组和 `unknown` 不能自证完整，并逐表核对父键、ID 映射、导入顺序和前后行数。当前回归 10 项。 |
| `kingdee-cosmic` | 见证据附录 | 共表被误当同实体/同布局；Long/String/`entityField` 连续猜测；用 `safeSetValue` 掩盖不存在字段；准备删除原节点单字段可编辑/必录；混淆 `.process` 与已发布 `.scheme`、漏列表布局并试图绕过正式入口；真实全资产检查又发现 47 个 A 层错误 | 增加工作流/布局变更契约、四方类型合同、安全写边界和挂载授权；明确 Scheme 基线、共表实体隔离、列表布局、节点例外和 Scheme 已证实的正式入口。工程启动/页面联调上下文只路由到 devtools；修复 45 个 `DataSet` 生命周期样例及分页/异常语义，并增加全资产回归。 |
| `kingdee-report` | 本轮本地 SDK 索引复核 | 其自称权威的 Algo 签名集缺少 `Algo.newContext()` / `AlgoContext`，无法为异常安全的多 DataSet 作用域提供精确合同 | 通过 SDK 索引确认类、接口继承、`newContext()` 与 `close()` 完整签名，补入唯一权威 reference 和标准 import；由 Cosmic 全资产与正反例回归验证使用方式。 |
| `kingdee-metadata-analyzer` | `019f5a95…`、`019fb3f3…`、`019fc7cb…`、`019fdbc9…` | 由物理表推断实体/入口；把详情页当列表证据；截图 7 行误读成 6 行；`runpy` 重跑生成器覆盖用户人工确认文件；只盘点表单布局而漏列表布局 | 明确实体、表单、列表、菜单、挂载分别取证；人工标注输入先哈希并只读；导出写新路径且按主清单对账；截图逐行枚举并与用户总数核对。 |
| `kingdee-ui-testing` | `019f5a95…`、`019fdbc9…` | 在错误页面类型上通过列表用例；未从真实首页/菜单入口验证 | 页面断言前强制记录 route、`formId`、`pageType`、`pageElement`；详情页不能替代列表页，错误页面证据标记 `blocked_wrong_page`。 |
| `kingdee-testing` | `019f6aa1…`、`019fcf95…`、`019fdbc9…` | 临时测试被带入生产分支；`NO-SOURCE` 被当测试通过；只请求重启就交付；用户要求启动本地环境时实际未启动；未走真实首页 | 新测试先标 `task-local/formal`，Git handoff 前检查 staged `src/test`；区分命令成功、服务恢复和业务入口验证；本地可测试需进程、端口、ready 和页面标记。 |
| `kingdee-cosmic-devtools` | `019fb612…` | 为绕过当前仓库启动问题自动另建隔离工程，导致静态资源和页面上下文失真 | 本地页面联调默认复用当前仓库启动脚本、配置和静态资源；只有用户明确要求或当前仓库已证实不可用时才隔离。 |
| `kingdee-cosmic-login` | 本轮可执行脚本检查 | SKILL 要求不回显 Cookie/CSRF，但 CLI 成功分支会打印原值 | CLI 改为只输出可用性标记，保留 Python API 返回合同；成功、失败、check 和敏感值不回显回归 6 项。未做真实网络登录。 |
| `darwin-skill` | 本轮真实会话语料运行 | 原流程没有可靠覆盖归档主会话；长文本在 UTF-16 中间截断 emoji，输出无法被 `jq` 解析；初版仍暴露 object-shaped 子代理、绝对路径及多类身份/网络值 | 新增双目录主会话抽取器；排除 object-shaped subagent source；只输出 basename 与 JSONL 行号；覆盖 JSON/header 凭据、URL/DSN、邮箱、手机、IP、UUID、长业务 ID 和本机路径脱敏；按 Unicode code point 截断，JSON 回归 3 项。 |

## 已回看但没有重复修改

以下历史错误已由当前规则或工具覆盖，重复写入只会增加 token：

- `kingdee-observability`：`019fc630…` 的“只凭 Git/硬编码 ID 宣称根因”已有同一 trace、最终 SQL 和证据链门禁。
- `playwright`：`019fad97…` 的 HTTPS/HTTP 猜测和未抓 network/console 已由现有工作流覆盖。
- `iscb-script`：多选基础资料缓存、子流程参数、`else if`、动态方括号字段、无变化不保存、状态字段保护、`bizQuery` 首参 `ConnectionWrapper` 均已有检查器或明确规则。
- `kingdee-cosmic`：`019fc7d5…` 的绕过正式入口已被新增工作流契约覆盖；通用 reference 不固化项目节点 key，证据附录仍保留该会话事实。
- `kingdee-ui-testing`：F7 语义必须来自当前元数据/用户规则，不把某个项目的组织层级固化为通用语义。

没有发现新的高置信缺口、因此本阶段不改的 14 个保留 skill：

`playwright`、`web-access`、`kingdee-custom-control`、`kingdee-frontend-script`、`kingdee-kcs-ops`、`kingdee-kingscript`、`kingdee-observability`、`kingdee-openapi-client`、`kingdee-sdk-helper`、`kingdee-security-review`、`html-output-quality`、`multi-search`、`skill-installer`、`skill-vetter`。

它们是否保留仍以独立的 with-skill/no-skill 价值审计为准，见 `docs/skill-value-audit-2026-08-08.md`；“本轮没有新增规则”不等于未经验证保留。

## 原错误场景回放

使用更新后的 skill 在只读模式回放 4 个复合场景，结果 4/4 达到预期门禁：

1. ISCB：区分 DSL `String.trim` 与 SQL Server `TRIM`，递归扫描独立 DTS、嵌套流程和 ZIP，并覆盖游标、`bizQuery`、`proc_digest` 与真实流程统计。
2. SQL：只给生产修复计划，不执行；覆盖元数据、stage、权威关系、不可空映射、因果链、精确行数、before-image、失败后重新计算和 compare-before-restore。
3. Cosmic：以当前 `.scheme` 为基线，保留该回放场景中的正式提交节点 `UserTask3`、节点单字段例外和每个实体自己的列表布局；共用物理表不合并实体或入口，通用规则不固化节点 key。
4. Testing：拒绝把 `NO-SOURCE`、重启请求或服务恢复称为测试/部署完成；临时测试按归属处理，并要求真实首页业务入口验证。

本轮曾尝试再生成一组隔离 no-skill 对照，但空 HOME 仍复现了更新后的专有合同词和规则，说明运行环境存在不可见污染；这组基线已拒绝，不能写入价值分数。删除/保留决策继续使用此前通过污染检查的 114 组默认模型对照与 42 组轻量模型删除复核。

### 回放记录

四次均为真实 `codex exec` 只读运行，不是人工 dry-run；模型为 `gpt-5.6-terra`，`eval_mode=full_test`。临时原始日志按 darwin-skill 规则在收尾删除，报告保留完整 prompt、检查点计数和最终输出 SHA-256：

| Prompt ID | Skill | Prompt | 结果 | 输出 SHA-256 |
|---|---|---|---|---|
| `iscb-runtime-regressions` | `iscb-script` | 当前服务流程含 SQL Server 内嵌 SQL、分页游标、`bizQuery` 列表参数、流程摘要变量；历史交付重复漏掉裸 `TRIM`。如何修复并验证全包没有遗漏？ | 6/6：方言区分、目录/ZIP/嵌套扫描、游标、列表查询、摘要变量、真实节点统计 | `73da7b93d1a8add2f4a3eac4f684fb9507b145bd0255ea0a2633e90bb7967f1a` |
| `sql-plan-only` | `kingdee-sql-and-data` | 只审核生产组织关系重建计划；不可空外键、部分映射缺失、页面异常因果未证明、失败后旧计数可能失效。怎样制定门禁？ | 8/8：只读计划、元数据、stage、权威关系、不可空策略、因果链、重算、并发回滚 | `1afed15bdc4a22debc5b16731b44c05dbb878484553ab4063ff4a7fa719b49ff` |
| `cosmic-shared-table-workflow` | `kingdee-cosmic` | 多实体共表，输入有 `.process` 与当前发布 `.scheme`；修改审批布局和工作流时，现有正式节点、单字段可编辑必录和各自列表布局必须处理。 | 6/6：Scheme 基线、实体隔离、正式入口、节点例外、列表布局、真实入口/流程验证 | `5ad398051ac24917f837db122bfd38a442bd57c60afdf5896404eaf165905e70` |
| `testing-completion-evidence` | `kingdee-testing` | `test NO-SOURCE`、重启请求已返回、存在临时 `src/test`，且用户要从首页测试；能否称完成？ | 5/5：NO-SOURCE、重启状态、测试归类、服务证据、真实首页 | `427f930c5d54832bb549c00f4549b41d878e99bd6c7b54d66f16bd7d5759cfd0` |

## 脱敏证据附录

下表只保留会话 UUID、日期、JSONL basename、证据行号和纠错转述；不复制凭据、生产值或客户数据。`A` 表示前一代理行为，`U` 表示用户纠正，`R` 表示运行证据。

| Session UUID / 日期 | JSONL basename / 行号 | 脱敏后的闭环与归属 |
|---|---|---|
| `019f5a95-1cee-7d43-ac9a-7b56b8512473` / 07-13 | `rollout-2026-07-13T16-25-49-019f5a95-1cee-7d43-ac9a-7b56b8512473.jsonl`; U4016/U4160/U7390 | 共表不等于同实体；详情页不能替代列表证据。`metadata-analyzer`、`ui-testing`、`cosmic`。 |
| `019f6aa1-bf27-7b71-b277-9f272b6cd1ad` / 07-16 | `rollout-2026-07-16T19-13-32-019f6aa1-bf27-7b71-b277-9f272b6cd1ad.jsonl`; A1774/U1799/U1812 | 声称未带临时测试，实际测试类进入生产分支。`testing`。 |
| `019f8f01-2d4c-7980-b933-cce819be2c38` / 07-23 | `rollout-2026-07-23T20-44-06-019f8f01-2d4c-7980-b933-cce819be2c38.jsonl`; A141/U148 | 迁移只列主表，漏多语言表。`sql-and-data`。 |
| `019f9683-d65c-7f00-9070-3978bd7e3852` / 07-25 | `rollout-2026-07-25T07-44-10-019f9683-d65c-7f00-9070-3978bd7e3852.jsonl`; A2332/A2342/U2349 | 将一批记录统一恢复为同一状态，用户要求逐行恢复真实原值。`iscb-script`。 |
| `019fa643-dd16-7cd3-9b38-e421149f5ab8` / 07-28 | `rollout-2026-07-28T09-08-13-019fa643-dd16-7cd3-9b38-e421149f5ab8.jsonl`; A3869/R3883/A3908 | 弱静态检查遗漏目标 SQL Server 不支持的 SQL 函数。`iscb-script`。 |
| `019fad97-b821-7e32-b66b-03a62b84f548` / 07-29 | `rollout-2026-07-29T19-17-09-019fad97-b821-7e32-b66b-03a62b84f548.jsonl`; U884/A946/U1017 | URL 协议猜测和未抓 network/console；现有 Playwright 已覆盖，因此不重复改。 |
| `019fb238-0963-74e3-969e-4b392e02f6c9` / 07-30 | `rollout-2026-07-30T16-50-44-019fb238-0963-74e3-969e-4b392e02f6c9.jsonl`; R956/A975/U1107/R1191 | 裸 `TRIM` 再次漏扫；多选缓存和目标版本集合丢项。`iscb-script`。 |
| `019fb2b7-50ae-7593-8e0e-b643799cc17a` / 07-30 | `rollout-2026-07-30T19-09-46-019fb2b7-50ae-7593-8e0e-b643799cc17a.jsonl`; R962/A984/R1260/A1281/U1722/A1732/R2948/A3372/R3655/A3671 | `bizQuery` 列表/作用域、纯脚本替代原生节点、首游标和短字符串连续运行错误。`iscb-script`。 |
| `019fb3f3-0a37-77f1-adb5-3ab1c070f1ba` / 07-31 | `rollout-2026-07-31T00-54-37-019fb3f3-0a37-77f1-adb5-3ab1c070f1ba.jsonl`; A296/U336/A343 | 截图 7 行误读成 6 行。`metadata-analyzer`。 |
| `019fb612-909a-7163-8161-8feb22cfcdb9` / 07-31 | `rollout-2026-07-31T10-48-17-019fb612-909a-7163-8161-8feb22cfcdb9.jsonl`; U612/A616/A1935/U1963/U2169 | 本地联调擅自换隔离工程；越权准备挂载并重复页面已有过滤。`cosmic-devtools`、`cosmic`。 |
| `019fc57b-a5e4-78f3-ad1e-7e77d7c42c0e` / 08-03 | `rollout-2026-08-03T10-37-22-019fc57b-a5e4-78f3-ad1e-7e77d7c42c0e.jsonl`; U746/U761 | 由连线名/时间推断新增路径，来源标识与状态矩阵错误。`iscb-script`。 |
| `019fc630-74b9-7661-8ab5-d7022528cd7f` / 08-03 | `rollout-2026-08-03T13-54-52-019fc630-74b9-7661-8ab5-d7022528cd7f.jsonl`; U301 | 先凭 Git 历史宣称根因；现有 observability 同 trace 门禁已覆盖，不重复改。 |
| `019fc7cb-e911-7732-9a0a-7a634f8c0dad` / 08-03 | `rollout-2026-08-03T21-24-17-019fc7cb-e911-7732-9a0a-7a634f8c0dad.jsonl`; U283/A302/A338/A873/U879/A900 | `runpy` 覆盖人工确认文件；摘要写入 `comment` 而非 `proc_digest` 且变量未定义。`metadata-analyzer`、`iscb-script`。 |
| `019fc7d5-85df-7290-ac07-4d73759ddd0f` / 08-03 | `rollout-2026-08-03T21-34-47-019fc7d5-85df-7290-ac07-4d73759ddd0f.jsonl`; A1436/U1442/A1448 | 拟绕过当前正式提交入口；由通用“保留 Scheme 正式入口”规则覆盖，不固化节点 key。 |
| `019fcb8f-2921-76b1-9dd9-99ba32bff61d` / 08-04 | `rollout-2026-08-04T14-56-24-019fcb8f-2921-76b1-9dd9-99ba32bff61d.jsonl`; A476 | 关系重建按旧目标编码回填，正确关系应来自权威外键且目标集合计数不同。`sql-and-data`。 |
| `019fcc7b-3a12-7c23-b2c1-efe22cf56f22` / 08-04 | `rollout-2026-08-04T19-14-15-019fcc7b-3a12-7c23-b2c1-efe22cf56f22.jsonl`; U1425/A1431 | Long/String/`entityField` 连续试错。`cosmic`。 |
| `019fcc88-9c3b-7ae3-b6eb-e448d0e0dfe6` / 08-04 | `rollout-2026-08-04T19-28-52-019fcc88-9c3b-7ae3-b6eb-e448d0e0dfe6.jsonl`; U1905/A1971/A2674/A2694 | 布局问题被扩大为无因果证据的状态批量修复。`sql-and-data`。 |
| `019fcf95-3114-7dc2-a994-d7bb0256db73` / 08-05 | `rollout-2026-08-05T09-41-28-019fcf95-3114-7dc2-a994-d7bb0256db73.jsonl`; A759/U768/A772 | 用户要求启动本地环境，实际未启动便交回测试。`testing`。 |
| `019fd4cd-1d04-7913-b2f0-b46ab856f0fa` / 08-06 | `rollout-2026-08-06T10-00-39-019fd4cd-1d04-7913-b2f0-b46ab856f0fa.jsonl`; U1212/U1245/U1916/U2728 | 文本/编码语义和类型反复错误；测试值不是权威真实数据；字段说明更新后旧 DTS/payload 未同步失效。`iscb-script`。 |
| `019fd51b-699c-77e1-a203-321cce699d84` / 08-06 | `rollout-2026-08-06T11-26-11-019fd51b-699c-77e1-a203-321cce699d84.jsonl`; U1313/R1990 | 阶段字段范围不同；映射缺失触发不可空外键错误。`sql-and-data`。 |
| `019fd5d7-6db8-76e2-af5f-6779e533bff1` / 08-06 | `rollout-2026-08-06T14-51-33-019fd5d7-6db8-76e2-af5f-6779e533bff1.jsonl`; U253/U421 | 用安全写掩盖不存在字段，并猜错组织编码体系。`cosmic`。 |
| `019fd73a-f9f4-70f2-87e0-37bbdc748671` / 08-06 | `rollout-2026-08-06T21-19-54-019fd73a-f9f4-70f2-87e0-37bbdc748671.jsonl`; U222/U278/U451/U526/U1058 | 保存后补写、新增/更新/历史路由和终态优先级错误。`iscb-script`。 |
| `019fd78e-b235-7bb1-9f7d-356688b96d29` / 08-06 | `rollout-2026-08-06T22-51-21-019fd78e-b235-7bb1-9f7d-356688b96d29.jsonl`; U516/U571/U573 | 不应删除原节点单字段可编辑/必录，节点例外应覆盖布局锁定。`cosmic`。 |
| `019fdbc9-8c91-7193-b881-56678c2fc014` / 08-07 | `rollout-2026-08-07T18-34-06-019fdbc9-8c91-7193-b881-56678c2fc014.jsonl`; U1179/U2677/U2895/U10123/U13080 | 漏列表布局、混淆独立布局、臆造平台对象、交付包未分类、用开发平台代替首页验证。`cosmic`、`metadata-analyzer`、`testing`、`ui-testing`。 |

## 自动验证

最终矩阵：

- 第一方 Python 单测：101/101。覆盖 ISCB 26、登录 6、Cosmic post-check 7、自定义控件 10、前端脚本 4、KCS 8、元数据 4、可观测性 6、安全审查 7、SQL/data 10、testing 6、UI testing 7。
- Node 单测：28/28；其中会话抽取 3、安装器 15、仓库/runtime-card/vetter 10。
- ISCB bundle：168/168 精确签名、186/186 文档示例、18/18 curated cases、3/3 真实 runtime selftest。
- 跨平台校验：24/24 skill；runtime-card 8/8，0 error、0 warning；Darwin 资产校验 24 skill，0 error、0 warning。
- `kingdee-cosmic` 依赖按 `requirements.txt` 装入全新 Python 3.14 环境：`tree-sitter==0.26.0`、`tree-sitter-java==0.23.5`；post-check 7/7，覆盖全资产、`AlgoContext` 正反例和主键游标分页正反例，`pip check` 通过。旧 0.24 API 兼容路径此前的 4 项核心回归同为 4/4。
- 4 个只读原场景模型回放：4/4；完整 prompt、模型、检查点和输出 hash 见上表。
- `git diff --check`：通过。

独立只读质量复核提出的 6 个 P1 均已关闭：空拓扑自证、抽取器 source/脱敏、formal/task-local 冲突、ISCB 双模式与常驻膨胀、审计可复现性、跨 skill 重复和项目节点 key。

后续全资产复核又把原 47 个 Cosmic error 归并成 3 个根因并逐项关闭：DataSet Cookbook 改用本地 SDK 索引确认的 `AlgoContext` 异常安全作用域；分页改成带正页大小门禁、稳定主键游标和 `finally` 关闭线程池，`STYLE-015` 用正反例识别而非靠搬 helper 绕过；SHA-256 缺失按 JVM 不变量处理，不伪装成业务异常。

## 已知剩余风险与边界

- `kingdee-cosmic/assets/` 全量扫描已从 47 个 A 层错误降为 0 error；仍有 5 个 warning 和 4 个 info（`STYLE-002/013/026/027`），属于不阻断门禁的 SDK 偏好与国际化提示，未在缺少精确合同的情况下机械改写。
- 未连接 DEV/TEST/PROD，未执行数据库写入、元数据挂载、部署、发布、Git 暂存、提交或推送。
- 本轮只修改本地 skill、检查器、测试和审计材料；真实平台行为仍需在具体业务任务获得相应授权后验证。
