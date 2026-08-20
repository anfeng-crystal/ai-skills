# 服务流程现场经验台账

用于吸收外部/历史服务流程经验，同时避免把版本相关观察误写成当前平台硬事实。优化 Script 或生成 review copy 时按规则 ID 引用；`experience_hypothesis` 也可以进入评审副本，但必须保留目标平台验证项。

本表首批经验来源标记为 `candidate_xinghan_service_flow_optimization`：来自用户提供的本地“星瀚服务流程解析与优化”skill 及其语法手册。来源未给出可复核的平台版本和原始帮助项，本轮未安装、未执行其脚本；因此保留经验内容与冲突证据，不把来源自述直接升级为平台事实。

## 证据等级

| 等级 | 含义 | 可采取动作 |
|---|---|---|
| `bundle_runtime` | 当前随 skill 分发的 JAR 已 compile + run 复现 | 可作为当前 engine 默认；仍不替代目标平台运行 |
| `bundle_surface` | manifest/JAR 能力面存在，但未完成该参数/类型的运行验证 | 可生成条件写法，标注待 runtime |
| `platform_reference` | 当前平台资料目录支持 | 可做平台弱预检，标注资源与目标版本 |
| `experience_hypothesis` | 现场经验、旧版本观察或来源版本不明 | 保留并触发最小反例；不能单独宣称语法错误 |
| `conflict` | 经验内部矛盾，或与当前 bundle/平台证据冲突 | 不自动正则改写；列出两侧证据和安全回退 |

每条经验至少保留：`id`、`claim`、`profile`、`status`、`current_evidence`、`safe_fallback`。目标版本反例优先于本表默认值。

## 当前经验矩阵

### `EXP-CTRL-TRY-001` 异常语法

- claim：部分现场版本认为 `try/catch/throw` 不可用，应以判空代替；另有流程又要求补 `try/catch`。
- profile/status：`engine / conflict`。
- current_evidence：当前 bundle 对 `try/catch/finally/throw` compile + run 通过。
- safe_fallback：当前 engine 可使用；平台目标版本未知时先做最小 compile probe。HTTP/查询返回判空是独立健壮性规则，不能当成异常机制的等价替代。

### `EXP-CTRL-ELSEIF-001` 条件分支

- claim：候选示例使用 `else if`。
- profile/status：`engine / bundle_runtime + conflict`。
- current_evidence：当前 bundle 明确拒绝 `else if`。
- safe_fallback：写成 `else { if (...) { ... } }`；只有目标版本反例才能覆盖。

### `EXP-CTRL-FOREACH-001` colon foreach

- claim：`for(var item : list)` 可遍历集合。
- profile/status：`engine / bundle_runtime`。
- current_evidence：当前 bundle compile + run 通过；返回值与三项输入一致。
- safe_fallback：保留该语法，不自动改成索引循环；目标节点若有特殊集合类型再补类型探针。

### `EXP-COL-APPEND-001` 单项追加

- claim：`.push()` 不适用，单项追加使用 `list += element`。
- profile/status：`engine / bundle_runtime`。
- current_evidence：当前 bundle 拒绝 `.push()`，`+=` compile + run 通过。
- safe_fallback：仅把“追加单项”改为 `+=`；`pop/shift` 是移除语义，不能错误替换成追加。

### `EXP-COL-ADDALL-001` 批量追加

- claim：`Collection.addAll(target, items)` 的第二参必须是集合；传单项会 `ClassCastException`。
- profile/status：`engine / bundle_runtime`。
- current_evidence：list + list 运行通过；list + scalar 运行复现 `ClassCastException`。
- safe_fallback：单项用 `+=`；批量仅在第二参类型已证实为兼容集合时使用。未知变量类型只告警，不自动改写。

### `EXP-COL-FILTER-001` 流式集合函数

- claim：现场经验一度把 `.map/.filter/.reduce` 全部视为 JS 高阶函数并禁止。
- profile/status：`engine / conflict`。
- current_evidence：当前 DSL/manifest 支持 `.each/.filter/.group/.mapping`；标准 JS callback 形态的 `.map/.reduce` 没有当前证据。
- safe_fallback：保留 DSL `.filter(condition)`；转换用 `.each()`/`.mapping()` 或显式循环，统计用已验证聚合函数。不能因“map 不支持”误删 `.mapping()`。

### `EXP-JSON-PROFILE-001` JSON 处理

- claim：不用标准 `JSON.parse/stringify`，改用平台/engine JSON 函数。
- profile/status：`engine + platform / bundle_runtime + platform_reference`。
- current_evidence：标准 `JSON` 命名空间被当前 bundle 拒绝；`String.FormatJson()` 运行通过；`FastJsonParse/FastJsonFormat` 属于平台目录。
- safe_fallback：engine 使用 `String.ParseJson/FormatJson`；明确平台节点才使用 `FastJson*`，并标注平台弱预检。

### `EXP-DATE-001` 当前时间与日期参数

- claim：`Date.now()`、`NOW` 可用；现场文档对 `Date.add/firstDay` 参数顺序存在差异。
- profile/status：`engine / bundle_runtime + conflict`。
- current_evidence：`Date.now()` 与 `NOW` 当前运行通过；其他争议签名尚未完成类型化运行探针。
- safe_fallback：当前时间可用已验证两种写法；`Date.add/firstDay/diff` 按当前 reference 后仍须用目标类型最小样本验证，不能按经验调换参数。

### `EXP-ARRAY-SUB-001` 数组/列表切片

- claim：JS `.slice()` 改为 `Array.sub(array, start, ...)`。
- profile/status：`engine / conflict`。
- current_evidence：`Array.sub` 能力存在，但对 list literal 运行出现类型转换失败；`Collection.slice(list, start, end)` 运行通过。
- safe_fallback：List 分页/分批用 `Collection.slice`；`Array.sub` 仅用于已证实的真实 array。第三参数语义未验证前不写成“长度”硬规则。

### `EXP-HTTP-001` HTTP 入参与判空

- claim：`HttpPost` 与 `HttpInvoke` 的请求体类型不同，返回对象需逐层判空，认证失败应停止后续调用。
- profile/status：`platform / experience_hypothesis + platform_reference`。
- current_evidence：名称在能力目录中，但本地 bundle 不证明目标资源、精确签名、网络失败返回或真实调用。
- safe_fallback：保留 form/string 与 Map 的兼容经验，按目标节点 reference/样本确认；任何返回都先判空。不得输出 token、secret、host 或响应原文。

### `EXP-SQL-001` SQL 与连接资源

- claim：查询/DML 的 params 与 types 数量、顺序和字段类型必须一致，batch 使用二维参数。
- profile/status：`platform / platform_reference`。
- current_evidence：当前数据库合同支持 `query_*`、`execute_update/execute_batch` 及参数化约束。
- safe_fallback：必须使用当前节点真实引入的连接实例；不把 `DataSourceResource` 类名、`ierp_con`、`cn` 或 `@EIP` 经验名当成可猜的资源。

### `EXP-JS-BLANKET-001` JS blanket ban 边界

- claim：严格相等、`require`、箭头符号等都应按标准 JS 禁止。
- profile/status：`engine / conflict`。
- current_evidence：当前 DSL 有自己的 `===/!==`、`require` 和 `=>` 语义；它们不等于 CommonJS/ES6。
- safe_fallback：禁止的是未经证实的 Node 模块和 JS callback 写法；不得只按关键词删除 DSL 同名能力。

### `EXP-DATA-CTOR-001` Data 构造器

- claim：现场资料列出 `Data.map/Data.list`。
- profile/status：`engine / experience_hypothesis + conflict`。
- current_evidence：当前 manifest 使用 `Data.asList/Data.mapping/Data.set/...`。
- safe_fallback：生成当前 manifest 名称；`Data.map/Data.list` 仅在目标版本证据出现时使用。

### `EXP-OPT-AUTO-001` 自动改包

- claim：逐节点生成优化脚本，回写 Script，版本 +1，更新 modifytime，并把摘要追加到 comment。
- profile/status：`service-flow / field workflow`。
- current_evidence：候选只描述该工作流，未实现安全回写；本 skill 用 `scripts/patch_service_flow.py` 重建。
- safe_fallback：原包只读；baseline/manifest/replacement 快照 SHA；精确 analyzer `scope_path + node_id`；先 inspect，再以 no-clobber 发布原包之外的 atomic review copy。manifest 记录本表规则 ID 与声明证据等级；经验假设可以进入评审副本，但必须保持 `evidence_verified=false`、`requires_platform_validation=true`。

### `EXP-OPT-HEURISTIC-001` 通用优化建议

- claim：移除数量限制、统一加日志/统计、强制 TimerStarter、Script 必须搭配 DataRetriever。
- profile/status：`service-flow / experience_hypothesis`。
- current_evidence：这些结论依赖业务入口、原生节点和目标版本，不能从节点名或脚本长度直接证明。
- safe_fallback：硬编码限制先判断是否业务不变量；优先原生统计与节点；启动方式按真实 Starter；每条建议绑定 flow/scope/node/link 证据和保持不变项。

## 使用与回归

- 自动改包 manifest 的 `experience_rules` 只填本表规则 ID，`evidence_level` 仅记录提交者声明；工具输出 `declared_evidence_level` 且固定 `evidence_verified=false`，不会把经验 ID 或枚举值冒充语法验证。
- 修改本表的 `bundle_runtime` 结论时，补同一最小探针；失败型回归要区分 static、compile 与 runtime，不绑定整段本地化异常文本。
- 目标平台出现反例时，新增版本/节点上下文和 counter evidence；不要删除原经验或覆盖其他 profile。
