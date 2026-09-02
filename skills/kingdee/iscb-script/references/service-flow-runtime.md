# 服务流程运行合同

用于修改已有服务流程拓扑、原生节点、分页、查询、保存、流程摘要或通用脚本函数。静态结构通过不等于目标平台已运行。

## 拓扑与状态矩阵

- 优先保留现有 `DataRetriever`、`DataLoader` 和平台原生节点；Script 只补原生节点不能表达的逻辑。成功数、失败数、分页数和加载结果以原生节点实际输出为准，不另造无法被平台监控的脚本统计。
- 对新增、命中更新、历史修复、放弃/终态逐支列：进入条件、单据状态、流程状态、来源标识、允许写字段和出口。连线标题、节点名、创建时间或当前值分布都不是业务来源证据。

## DTS 只读解析

先解析结构，再讨论优化；不要用正则截取 `define_json_tag`，不要把整个多记录 DTS 当成单个 JSON，也不要按节点 ID 或坐标虚构顺序。

```bash
python3 scripts/analyze_service_flow.py <flow.dts-or-zip> --flow <exact-number> --format json
python3 scripts/analyze_service_flow.py <flow.dts-or-zip> --flow <exact-number> --format markdown --output <report.md>
python3 scripts/analyze_service_flow.py <flow.dts-or-zip> --flow <exact-number> --format mermaid --output <topology.md>
```

- 默认只读：stdout 输出脱敏结构，包含输入 SHA-256、顶层记录、唯一流程选择、主/子流程节点与真实 `links`、Script 行数/哈希、结构诊断和证据级别；不输出脚本正文、变量默认值、条件文本、资源 ID 或连接配置。
- `--output` 和 `--extract-scripts` 都必须来自用户明确的本地落盘要求；已有目标默认拒绝覆盖。`--extract-scripts` 只写净化后的单层文件名，原文可能含凭据，不能再读入对话或报告。
- 同号流程多条、定义损坏、断链或目标不存在时保留诊断并停止目标选择；不按修改时间、版本号、文件顺序自动选一个。
- Mermaid 只画真实连线；缺 `links` 时保持无边图，不按 ID、坐标或遍历顺序补线。
- 默认最多读取 64 MiB DTS 内容和 128 个 ZIP 成员；确有更大受控输入时显式调整 `--max-input-bytes` / `--max-zip-members`，不能绕过输入上限直接整包读入。
- 此结果只能标为 `DTS 结构静态通过` 或静态诊断失败；未证明资源可用、平台脚本签名、运行时对象类型、导入发布或真实执行。

优化建议逐条绑定 `flow number + scope path + node/link id + 事实证据`，并标明 `结构错误`、`业务假设` 或 `待平台验证`。默认只给最小修改及保持不变项；分析器本身不得回写 DTS、增加版本号、修改时间或 comment。

## 受控自动改包

经验驱动的改包使用独立工具，分析器继续保持只读：

```bash
python3 scripts/patch_service_flow.py snapshot --baseline <current.dts> --flow <exact-flow-number>
python3 scripts/patch_service_flow.py inspect --baseline <current.dts> --manifest <patch.json>
python3 scripts/patch_service_flow.py generate --baseline <current.dts> --manifest <patch.json> --output <review.dts>
```

`snapshot` 只读输出 `manifest_snapshot`：其中 version 保留 DTS 中的 JSON 原生类型，comment 只输出 SHA-256、不输出正文，Script 输出 `scope_path + node_id + expected_script_sha256`。构造 manifest 时复制这些快照值，不用 `sed/jq/read` 手工拆多行 comment，也不把数字 version 改成字符串或反向转换。

最小 manifest 形态如下；脚本正文只放在同目录或子目录的 replacement 文件中：

```json
{
  "schema_version": 1,
  "input_sha256": "<baseline-64-hex>",
  "flow_number": "<exact-flow-number>",
  "metadata": {
    "expected_version": 12,
    "expected_modifytime": "2026-08-01 10:00:00.000",
    "expected_comment_sha256": "<old-comment-64-hex>",
    "new_modifytime": "2026-08-12 09:30:00.000",
    "comment_separator": " | ",
    "summary": "按已列经验生成评审副本"
  },
  "changes": [
    {
      "scope_path": ["<block-node-id>"],
      "node_id": "<script-node-id>",
      "expected_script_sha256": "<old-script-64-hex>",
      "replacement_file": "replacements/node.iscb",
      "replacement_sha256": "<replacement-64-hex>",
      "evidence_level": "experience_hypothesis",
      "experience_rules": ["EXP-OPT-HEURISTIC-001"],
      "allow_sensitive_flags": []
    }
  ]
}
```

- manifest 必须固定 `schema_version`、输入 SHA-256、唯一 `flow_number`、元数据旧值、旧 comment 哈希，以及每个 `scope_path + node_id` 的旧脚本 SHA、replacement 文件 SHA、经验规则 ID 和声明证据等级。manifest 的 `scope_path` 直接取只读 analyzer Script 元数据中的 `scope_node_ids`；路径项和 `node_id` 都使用节点对象 `id`，不是 `nodes` 字典 key，工具会唯一映射到真实 JSON key。
- `expected_version` 必须逐类型等于 `snapshot` 输出：数字仍为数字，字符串仍为字符串。`expected_comment_sha256` 必须直接复制快照值；多行 comment 不通过 shell 行读取重算。
- 同一 DTS 需要修改多个流程时，先基于同一份已批准合同列全目标，再按流程在私有临时目录串联 review copy；每一阶段都重新 `snapshot -> inspect -> generate`，最终文件联合验证后才对外交付。仍被下一阶段引用的 baseline/staging 不得提前移入废纸篓。
- replacement 只能是 manifest 目录内的 UTF-8 本地文件；不内联脚本正文。凭据字面量阻断，endpoint/connection 字面量只有 manifest 明确列入允许类别才继续。
- `comment_separator` 只允许空串、空格、` | `、一至两个换行或中文分号变体；摘要仍须通过控制字符与敏感字面量门禁。
- 工具只支持平台导出的一行一个 object record 的 plain DTS；ZIP、顶层 array、多行记录、重复 JSON key、同号流程、非 Script 节点、任一快照哈希漂移、version 非整数/数字字符串或输出目录项已存在均停止，不猜测。change 数量、单个/累计 replacement 和最终输出都有资源上限。
- 生成时只重序列化目标顶层记录；其他记录字节保持。目标记录内只允许指定 Script、`version + 1`、精确 `modifytime` 和 comment 追加变化；`proc_digest`、resources、variables、links、其他节点和子流程语义保持。
- 变更定位拆成顶层 `definition_field_pointer` 与解码后的 `decoded_definition_pointer`，并报告 `definition_storage`；不能把 JSON 字符串内部逻辑路径冒充为可直接应用于顶层 flow 的 RFC 6901 pointer。
- 输出只能是原包之外的 atomic review copy；发布采用真正的 no-replace 门禁，并在发布前后复核 baseline、manifest 和 replacement 快照，任何漂移都不交付副本。状态为 `generated_review_copy_not_imported`，始终 `requires_platform_validation=true`。
- manifest 中的 `evidence_level` 只是提交者声明。报告固定输出 `declared_evidence_level`、`evidence_verified=false` 和 `evidence_artifacts_verified=false`；实际 runtime/validator/reference 证据必须单独提供并复核，工具不会仅凭枚举值升级证据。
- 初始化只在明确新增分支、首次保存前执行；更新/历史分支默认不进入。当前放弃、终止等业务状态优先于普通初始化。

## 脚本节点基本门禁

- 子流程的输入变量数量、顺序、名称和调用参数逐项一致；独立运行只暴露真正必需的输入。
- ISCB 不是 JavaScript：不用 `else if`；动态方括号字段访问只有目标 `Dynamic.*` 能力已确认时才用。
- 先比较、后赋值；至少一个白名单业务字段确定变化才进入 `DataLoader`。取值失败或类型不明不算变化。
- `ml_string`、枚举、基础资料等复杂值按目标运行对象的直接值、字符串值和已证实属性比较，不按 UI 文本猜类型。
- 已审核/已确认记录只更新白名单业务字段，不能整对象保存后重置状态、匹配标志或审计字段。

## 流程属性与变量

- `comment` 是备注，`proc_digest` 是流程摘要模板；两者分别赋值，不能互相替代。
- 摘要中的每个 `#{variable}` 必须在流程变量定义中存在，并能追溯到脚本赋值或节点输出；未定义/未赋值即阻断交付。
- 自定义函数使用的查询字段、连接、游标和条件通过形参或函数内常量显式提供；不要假设 FC18/目标 runtime 支持捕获外层局部变量。

## 分页、集合和字符串

- 首页游标先归一化成目标字段可比较的非 null 初值；快照数大于 0 时，第一页必须实际推进，否则输出专用错误并停止，不能把 `pages=0` 当正常空集。
- `bizQuery` 列表查询按 `database-platform-rules.md` 使用目标版本已验证方式；不能把集合直接塞进等值条件。
- 用 `indexOf`/分隔符计算位置后，`String.sub` 前必须验证输入非空、索引非负、起止顺序和长度；覆盖空值、短值、无分隔符和多分隔符样本。
- 目标版本运行证据证明多选基础资料值转换只保留一项时，不再让集合经过该值转换：在服务流程脚本中拆分、查询、组装完整 ID 集合，并移除对应值转换引用。此降级只针对已证明受影响的目标版本。

## 运行回归

至少覆盖：新增、命中更新、终态保护；第一页有数据/无数据；多值混合分隔符/空列表；查询字段非空；短字符串/无分隔符；无业务变化不进入 `DataLoader`。回传原生节点统计和实际变量，不能只报弱预检通过。
