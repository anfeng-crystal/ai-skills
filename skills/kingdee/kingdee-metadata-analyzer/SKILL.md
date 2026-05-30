---
name: kingdee-metadata-analyzer
description: "Kingdee metadata forensics: entities, forms, plugin mount points, field R/W, dependencies."
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [kingdee, cosmic, metadata, analysis, plugin-binding]
---

# Kingdee Metadata Analyzer
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 触发边界
- **适用场景**：按实体标识分析苍穹元数据、绑定插件、页面/操作挂载点、插件源码、字段读写、服务调用和上下游单据关系。
- **不适用场景**（应交给其他 skills）：
  - SDK API 用法查询（如"如何使用 SaveServiceHelper"）→ 使用 `kingdee-sdk-helper`
  - 代码实现指导（如"如何写表单插件"）→ 使用 `kingdee-cosmic`
  - 运行时错误排查（如"NullPointerException 怎么解决"）→ 使用 `kingdee-cosmic`
  - 业务逻辑咨询（如"单据保存流程是什么"）→ 使用 `kingdee-cosmic`
  - KingScript 脚本开发 → 使用 `kingdee-kingscript`
  - 仅依赖源码、编译输出、日志、diff 或版本控制状态即可完成的任务 → 不使用本 skill
- 本 skill 是元数据证据采集与分析能力，不是阻断器，也不负责最终实现/修复；当用户目标还包含 Java 实现、诊断或改造时，先尽力产出可用证据，再交回 `kingdee-cosmic` 主控流程继续推进。
- 只有当前问题的字段、表单、插件挂载点或上下游关系无法从本地证据判断，且会影响结论或实现安全时才使用本 skill。

## 工作模式

### 快速查询模式（Quick Query）
**适用场景**：开发时快速查字段、操作、枚举，且输出完整、无关键警告、不需要证明字段层级或页面链路。
**工具**：`<METADATA_SKILL_ROOT>/scripts/quick-query.py`
**命令口径**：
- `METADATA_SKILL_ROOT` 是当前加载的 `kingdee-metadata-analyzer` skill 根目录；从本文件路径向上取一级即可，不要从业务仓库相对路径推断。
- `scripts/` 指本 skill 目录下的脚本，不是当前业务仓库的 `scripts/`；在项目目录执行时使用 `$METADATA_SKILL_ROOT/scripts/...` 的绝对路径。
- 先解析用户要求的环境口径，再选择配置；未指定环境时默认 dev，用户指定 prod/test/dev 时该环境是目标环境，不把其它可连环境当成等价替代。
- 配置选择从当前目录向上查找项目根，优先使用目标环境的显式配置（如 `ok-cosmic.<env>.json`），再看同级通用配置；不要只在当前子模块找一个默认文件后就停止。
- 一个配置或环境不可用时，必须继续做“失败分类 + 候选切换 + 证据降级”：区分配置不存在、`metadataAnalyzer.enabled=false`、缺凭据、网络/数据库不可达、实体不存在、脚本依赖失败；再尝试同项目其它候选配置、已有 analyzer 产物、quick-query 缓存、源码/JAR 证据或设计 XML。只有目标结论必须依赖目标环境在线元数据且所有替代证据都不足时，才停住询问用户。
- 缺少 Python 依赖时先主动运行 `$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py` 创建/复用本地 venv 并安装依赖；只有安装失败才说明降级原因。
- bootstrap 安装依赖时先尊重 `KINGDEE_METADATA_ANALYZER_PIP_INDEX_URLS` / `KINGDEE_METADATA_ANALYZER_PIP_INDEX_URL`，未配置时自动尝试默认源和内置镜像。
- macOS/Linux 用 `python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- ...`；Windows PowerShell 用 `py -3 "$env:METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- ...`。

**用法**：
```bash
METADATA_SKILL_ROOT=<当前 kingdee-metadata-analyzer skill 根目录>

# 查询字段列表
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" <entityNumber> --config <resolved-ok-cosmic.json> --fields

# 查询操作列表
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" <entityNumber> --config <resolved-ok-cosmic.json> --ops

# 查询已绑定插件
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" <entityNumber> --config <resolved-ok-cosmic.json> --plugins

# 查询枚举字段
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" <entityNumber> --config <resolved-ok-cosmic.json> --enums

# 查询所有信息（概览）
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" <entityNumber> --config <resolved-ok-cosmic.json> --all

# 模糊搜索实体
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" --search "关键词" --config <resolved-ok-cosmic.json>
```

**特点**：
- 仅查询数据库，不做 JAR 反编译和源码分析
- 输出简洁，适合快速查询
- 查询速度快（秒级）
- 字段列表默认确认字段标识、名称和类型；如果任务需要物理数据库列名、字段布局位置、是否只读或是否进入 PC/移动详情，必须追加查设计元数据或让用户在设计器侧确认，不把字段标识推断为物理列名。
- 看到 `WARNING`、`ERROR`、`...`、`省略`、`truncated`、`showing first`、`仅展示前`、缓存写入失败、连接重试、字段列表不完整等信号时，quick query 只能作为摸底结果，不能作为最终事实；必须改用 `--all`、全景分析、直接读取 `t_meta_entitydesign.fdata` / `t_meta_formdesign.fdata`，或明确写为“未确认”。
- 需要证明“单据头 vs 单据体/分录”“字段类型/枚举值/复选框口径”“生产 vs dev 环境差异”时，不能只凭平铺字段清单；必须拿到字段所属控件层级、父容器/entry、字段类型和环境配置来源后再下结论。
- 苍穹字段类型不止固定白名单；`CheckBoxField`、`QuerySelectField`、`BasedataPropField`、`BigIntField`、`QtyField`、`TextAreaField`、`MulComboField` 等平台字段都应识别为字段。quick query 遇到未知 `*Field` 标签时必须展示原始类型，不能因为类型未匹配就当字段不存在。
- `--plugins` 必须同时输出实体操作插件和关联表单页面插件，并保留 `operation`、`formPage`、`pageElement` 三类挂载证据；页面插件类名可能存放在 `ClassName` 或 `oid`，快查不能漏掉 `oid` 形式。
- 操作 XML 只有 `action=edit` 且没有 `Key/Name/OperationKey` 时，快查和全景分析只能输出 `edit#N[oid]` 这类无语义标签；不能按固定顺序推断成暂存、提交、审核或反审核，真实业务语义必须看插件描述、源码或操作设计元数据。
- 如果任务要判断 `MobileBillFormAp`、`MobileListFormAp`、`CardEntryViewAp` 或 `ztjg_riskcheck_*` 这类派生表单页面到底命中哪个插件，quick query 只能作为插件清单摸底；源码证据、JAR 反查和最终执行链路仍必须切到全景分析。

---

### 全景分析模式（Full Analysis）
**适用场景**：插件绑定分析、上下游关系、复用建议、深度挖掘
**工具**：`scripts/cosmic-metadata-analyzer.py`
**用法**：见下方"快速工作流"

**特点**：
- 数据库 + JAR 反编译 + 源码分析
- 生成结构化产物（`inventory.json` + `sources/*`）
- 新产物默认写入本机缓存目录；读取结果必须以脚本打印的 `__INVENTORY_PATH__` / `__OUTPUT_DIR__` 为准，不假设在业务仓库 `build/` 下
- 识别可复用途径
- 分析时间较长（分钟级）

---

## 快速工作流（全景分析模式）
1. **触发判断**（检查点）：
   - 确认用户问题是否需要元数据证据（插件绑定、字段结构、挂载点、上下游关系）。
   - 如果只需要快速查字段/操作/枚举，且不影响实现或结论安全，可以使用**快速查询模式**（`quick-query.py`）；一旦输出有警告、截断、省略或缺层级证据，立即升级到完整证据链。
   - 如果用户要确认“同一业务实体下哪个 PC/移动表单真正生效”或“实体插件为什么和移动页面执行链路不一致”，直接使用**全景分析模式**，不要先停在 quick query。
   - 如果是 SDK 用法、代码实现、错误排查或业务逻辑问题，提示用户："该问题应使用 `kingdee-sdk-helper` 或 `kingdee-cosmic`，不需要元数据分析。"
   - 如果当前目标只需要一个字段清单、一个插件清单或一个枚举值，且 quick query 结果完整无警告，不升级到全景分析。
   - 只有明确需要全景分析时才继续。
2. 确认项目编码、实体标识、分析目标、环境口径和输出用途；未指定环境时默认使用 dev；用户指定环境时不要用其它环境结果冒充目标环境事实。
3. 从当前目录向上定位项目根并枚举候选配置：目标环境显式配置 → 同项目通用配置 → 其它环境显式配置（仅作对照/降级证据） → `${AI_KNOWLEDGE_ROOT}/kingdee/cosmic/projects/config-table.md`。未配置 `AI_KNOWLEDGE_ROOT` 只作为降级信息，不直接报环境缺失。
4. 运行 `python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/cosmic-metadata-analyzer.py" check-config --config <ok-cosmic.*.json>`；Windows PowerShell 使用 `py -3 "$env:METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- ...`。缺少依赖时由 bootstrap 主动创建本地 venv 并安装；安装源可用 `KINGDEE_METADATA_ANALYZER_PIP_INDEX_URLS` 覆盖。
5. `check-config` 通过后，按脚本内置顺序解析凭据：当前进程环境变量 `passwordEnv` → 项目配置的 `envFiles` / 同名 `.env` / 项目 `.env` → 既有 `ok-cosmic.json` 的 `database.password` 兼容字段。不要要求用户把每个项目密码都长期保存到全局环境变量。
6. 目标配置失败时不要卡死在单一路径：记录失败类型和配置路径，按候选顺序尝试下一个可用证据源；若切到其它环境，只能输出“对照环境事实/推断”，并明确目标环境未确认。
7. 缺凭据、缺网络或缺产物路径时，先区分失败类型；若已有 `inventory.json`、`sources/*`、quick-query 缓存、项目源码、JAR 或可直接解析的 `fdata` 证据能支撑当前目标，继续给出带边界的结论；只有当前目标必须在线扫库且没有任何可用证据时，才询问用户补充凭据、切换环境、允许重试或指定历史产物。
8. 运行 `python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/cosmic-metadata-analyzer.py" <entityNumber> --config <ok-cosmic.*.json>`；若因依赖安装、数据库拒绝连接或网络中断失败，区分环境安装、配置、凭据、连通性和实体不存在，不把运行前提失败表述成”没有元数据”或”没有能力”。
   - 反编译源码、`javap` 文本和 `inventory.json` 是本地证据缓存，默认写入 `KINGDEE_METADATA_ANALYZER_OUTPUT_DIR` 或系统临时目录；不要把新产物写进业务仓库或 skill 仓库。
   - 只有用户明确要求把产物落到仓库且接受 Git/CodeGraph 扫描成本时，才使用 `--allow-git-output` 或 `KINGDEE_METADATA_ANALYZER_ALLOW_GIT_OUTPUT=1`。
9. 按脚本打印的 `__INVENTORY_PATH__` 和 `__OUTPUT_DIR__` 读取 `inventory.json` 和 `sources/*`；旧 `build/reports/cosmic-metadata-analyzer/...` 只能作为历史产物降级读取，不作为新运行的默认位置。
   - 输出字段证据时要分层标注：`fieldKey`、中文名、字段类型、物理列名、PC/移动布局位置分别来自哪里；缺少任一层证据时写“未确认”，不要把其它层证据外推。
   - 涉及单据字段时必须标注字段在单据头还是具体分录/子单据体；只证明“实体里有这个 fieldKey”不等于证明“目标代码可按单据头读取”。
   - 输出插件挂载证据时至少同时核对 `className`、`pageElement`、`formPage` 三层；同一个类在业务实体、移动表单、移动列表上可重复出现，不能因为类名相同就默认是同一个执行入口。
10. 需要给其它 Kingdee skill 消费时，运行 `scripts/metadata_contract.py --inventory <inventory.json> --environment <dev|prod|test|unknown>` 生成 machine-readable 摘要；如果只有 quick query 缓存，可用 `--quick-cache scripts/.metadata_cache/<entity>.json` 补字段摘要。
11. **用户确认检查点**：展示关键发现摘要（插件数量、高风险关系、可复用资源），询问用户：”是否需要深入分析某个插件或关系？”等待用户确认后再生成完整报告。
12. 按 references 生成分析报告；如果已经存在可复用的插件源码、模板、helper、服务调用链或标准平台能力，也在报告中点明，避免后续重复实现。

## References
- 分析口径：`references/analysis-rubric.md`
- 报告模板：`references/report-template.md`
- 配置说明：`references/config.md`
- 页面挂载：`references/page-binding.md`
- 字段证据：`references/field-evidence.md`
- 输出契约：`references/output-contract.md`
- SDK 查询协作：当需要查询插件中使用的 SDK API 详情时，使用 `kingdee-sdk-helper` skill

## Guardrails
- 不读取原始市场包的 `config.json`。
- 优先使用向上定位到的项目根显式环境配置；不要默认拿某个子目录或泛化 `ok-cosmic.json` 触发缺密码提示，也不要因为第一个配置失败就放弃元数据 skill。
- 一个环境不可用时，输出必须包含“目标环境状态、已尝试候选、可用替代证据、仍未确认项”；跨环境结果只能作为对照或推断，不得包装成目标环境已确认事实。
- 新的 analyzer 产物默认不落入 Git 工作树；相对 `metadataAnalyzer.output.reportDir` 不再表示项目内输出位置，读取结果时必须信任脚本打印路径。
- 检测到输出目标在 Git 工作树内时，默认使用本机缓存目录；除非用户明确要求保留仓库内产物，否则不要启用 `--allow-git-output`。
- 元数据查询缺少 Python 依赖时，先用 `$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py` 主动创建/复用本地 venv 并安装依赖；不要只提示用户手工安装，也不要把解释器 fallback 当成最终方案。
- 依赖安装失败要报告具体失败类型和 pip 源；允许用户配置 `KINGDEE_METADATA_ANALYZER_PIP_INDEX_URLS` 后重试。
- 不在 skill、报告、聊天输出或新增模板中写数据库明文密码；既有项目 JSON 含 `database.password` 时只作为兼容读取来源，不主动复制、展示或要求新增。
- 检测到项目配置里存在 `metadataAnalyzer.database.password` 明文密码时，默认主动迁移：在同项目 `.env` 中写入对应 `passwordEnv` 变量，JSON 只保留 `passwordEnv` 并移除 `password`；`.env` 必须确认被 Git 忽略，迁移过程和交付说明不得打印密码值。
- `metadataAnalyzer.enabled=false` 时不连接数据库。
- 凭据解析顺序以脚本为准；缺全局环境变量或缺 `AI_KNOWLEDGE_ROOT` 不等于缺凭据，先检查当前项目显式配置、配置中的 `.env` 声明、同名 `.env`、项目 `.env` 和既有 JSON 兼容字段。
- 遇到数据库连接失败、网络中断时，不把“当前会话缺少运行前提”表述成“没有元数据”或“没有这个能力”；先说明失败类型，再基于已有产物、源码或 JAR 证据继续能完成的部分。
- 缺少在线运行前提但已有 `inventory.json`、`sources/*` 等产物时，先基于现有产物继续给出稳定事实，并明确说明时效性边界。
- 在线扫库是强证据，不是唯一证据；如果当前任务是实现、排查或复用建议，可以用项目源码、同类实现、已有 analyzer 产物和平台 reference 组合推进，并标明证据等级。
- 有警告、截断或层级缺失的元数据输出不能包装成确定结论；先补完整证据，补不到就把该字段列为待确认，不用快速结果替代完整结果。
- 字段不存在只能由完整字段扫描、设计 XML 或目标环境证据支撑；不能由“快查没有识别某个字段类型”推导。
- 分析报告只写稳定事实、业务口径、调用关系、风险边界和待确认项。
- 已有插件源码、模板、helper、标准服务或平台能力能覆盖当前需求时，在报告里明确标出可复用途径，不建议重复造轮子。
- 不把执行过程、排查过程、命令流水或交付口径写入报告正文。

## Output
使用简体中文：配置状态（只写凭据来源类型，不写值） → 采集结果 → 整体概述 → 插件分析 → 外部关系 → 复用途径 → 风险与待确认项
