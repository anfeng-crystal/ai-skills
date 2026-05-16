---
name: kingdee-cosmic
description: "Kingdee Cosmic Java dev: plugins, reports, workflows, BOTP, OpenAPI, troubleshooting."
metadata:
  author: anfeng
  version: "1.2.0"
  license: MIT
  tags: [kingdee, cosmic, java, plugin, BOS, SDK]
---

# Kingdee Cosmic


**核心原则**：封装优先，原生兜底。优先使用 `kd.cd.common.plugin` 包下的扩展基类（`AbstractBillPlugInExt`、`AbstractFormPluginExt`、`AbstractListPluginExt`、`AbstractOperationServicePlugInExt`）和项目封装工具类（`OpUtils`、`BotpUtils`、`QueryUtils`、`DynamicObjectUtils` 等），避免在仓库已封装的场景里退回到 BOS 原生低层 API。

## 路由总则
- 先判定是否为金蝶云苍穹 Java 二开、配置、诊断或改造任务；普通 Java、纯前端、KingScript、ISCB 或非苍穹产品不由本 skill 主控。
- 本 skill 是苍穹 Java 任务的主控入口，负责需求判断、证据整合、实现/修复方案、代码改造和最终收口。
- 需要实体、字段、表单、页面/操作挂载点、插件绑定或上下游关系证据时，先调用 `kingdee-metadata-analyzer` 取证，再回到本 skill 继续分析或实现。
- 需要类定义、方法签名、Javadoc、API 归属或 SDK 候选时，调用 `kingdee-sdk-helper` 查询，再回到本 skill 选择实现路径。
- 需要登录 Cookie/CSRF 或 COSMIC_HOME/工程模板处理时，分别调用 `kingdee-cosmic-login`、`kingdee-cosmic-devtools` 完成工具步骤，再回到本 skill 收口。

## 收敛规则
- 阶段优先于流程：按用户当前意图选择方案、实现、验证、提交或清理路径；不要把前一阶段的排查流程带入后一阶段。
- 最小证据闭环：先取得足以支撑当前结论或改动的证据；只有该证据不足以判断正确性或会影响实现安全时，才扩大查询范围。
- 工具按需升级：快速查询能回答的问题不升级到全景分析；本地源码、编译输出或日志能回答的问题不启动在线元数据查询。
- 中断即收敛：用户质疑当前方向或进度时，先停止新增搜索，说明当前证据缺口和下一步最短路径。
- 代理和宽范围扫描只用于可并行、可验证、且能实质降低风险的任务；不得作为常规排查默认动作。

## 触发边界
- 适用于金蝶云苍穹 Java 8 / Gradle 二开、插件、报表、工作流、BOTP、动态表单、列表、操作插件、OpenAPI、代码质量核查和故障诊断。
- 普通 Java、非苍穹产品和纯前端页面不使用；KingScript 任务使用 `kingdee-kingscript`，实体元数据全景分析优先使用 `kingdee-metadata-analyzer`。
- skill 边界用于选择证据入口，不用于回避用户目标；如果任务跨 Java 实现、元数据、配置、脚本或诊断，先调用最相关的资料/脚本补证，再回到当前目标继续推进。
- 用户按实体标识要求分析插件绑定、页面/操作挂载点、字段读写或上下游关系时，优先借助 `kingdee-metadata-analyzer` 获取强证据；若在线 analyzer 暂不可用，基于已有产物、项目源码、JAR、references 和同类实现继续能完成的部分，并明确证据等级和时效边界。

## 快速工作流
0. **不确定时先查，不猜**：字段存储类型、数据库类型、组织 ID 等事实不确定时，先查元数据、源码或数据库确认，不凭假设直接写代码。
1. **元数据优先判断**（门禁检查点）：
   - 如果任务涉及具体实体标识（单据如 bd_material、报表、字段定义、插件绑定、挂载点），且这些事实会影响当前结论或实现，先调用 `kingdee-metadata-analyzer` 查元数据库获取强证据。
   - 只有以下情况跳过元数据查询：
     - 用户明确说"不查元数据"
     - 纯代码问题（如 Java 语法错误、编译错误、通用 SDK 用法）
     - 环境问题（如服务器连接失败、配置错误）
     - 当前目标只需要源码、编译输出、日志、diff 或版本控制状态即可完成
   - 不确定是否涉及实体时，默认先查元数据库。
   - 如果问题落在“同一业务实体派生出多个 PC/移动表单”的真实生效链路上，例如 `MobileBillFormAp`、`MobileListFormAp`、`ztjg_riskcheck_*` 这类入口表单，不要只看实体级 `quick-query.py --plugins`；优先让 `kingdee-metadata-analyzer` 跑全景分析，并检查 `inventory.json` 里的 `pageElement` / `formPage`。
   - 如果 quick query 输出包含 `WARNING`、`ERROR`、省略/截断提示、缓存失败、连接降级，或只给出平铺字段清单，不能据此做最终字段结论；涉及实现安全时必须升级到完整元数据、设计 XML、全景分析或生产日志证据。
2. Step 0：先做本地配置与离线能力预检，按 `scripts/cosmic-config-check.py` 区分 `ERROR` 和 `WARNING`；`ERROR` 只阻断结构性错误，`WARNING` 只表示能力降级。
3. 配置/脚本缺失、`meta` / `basedata` 在线不可用，或 VPN 导致元数据连不通时，不阻断离线可完成的任务，只标记受影响能力；如果用户目标需要元数据强证据，按 `kingdee-metadata-analyzer` 的配置选择、解释器选择、凭据解析顺序和产物复用规则处理，不把缺全局环境变量、缺 `AI_KNOWLEDGE_ROOT` 或预检 `WARNING` 当成唯一阻断条件。
   - 元数据/查询/分析类任务默认使用当前项目根目录的 dev 配置；用户明确要求生产时使用 prod 配置。具体文件名按当前项目约定选择，例如存在 `ok-cosmic.dev.json` / `ok-cosmic.prod.json` 时优先使用它们。
   - 元数据脚本缺少 Python 依赖时，先调用 active skill 目录下 `kingdee-metadata-analyzer/scripts/bootstrap-python-env.py` 主动创建/复用本地 venv 并安装依赖；在项目仓库执行时不要把相对路径 `scripts/bootstrap-python-env.py` 误判为仓库脚本。
   - 只有环境自动安装失败、配置文件不存在、凭据完全不可用、数据库连不通，或用户要求强实时元数据但当前无法连接时，才作为真实阻断说明。
4. **需求澄清**（检查点）：
   - 如果用户需求包含以下关键词但未指定具体实体，先询问澄清：
     - "单据保存/修改/删除" → 询问：哪个具体单据（如 bd_material、bd_customer）？
     - "字段联动/校验/赋值" → 询问：哪个表单？哪些字段？
     - "数据查询/过滤" → 询问：查询哪个实体？过滤条件是什么？
     - "插件开发" → 询问：哪个单据/报表？什么类型插件（表单/操作/报表）？
   - 澄清后，如果涉及具体实体，回到 Step 1 执行元数据查询。
5. 先确认任务类型、对象标识、插件类型、事件点、事务边界和验证方式。
6. 业务话术先读 `references/rules/intent-routing.md` 翻译成插件、配置、脚本或诊断场景；优先判断配置能力能否完成。
7. 生成、修改或审查 Java 代码前先读 `references/rules/constraints.md` 和 `references/rules/workflow.md`；插件任务再读 `decision-matrix.md`、`fact-confirmation.md` 和最接近的 `references/base/plugin/*.md`。
8. 涉及权限/组织/F7/导入/附件/调度等多能力交叉时，编码前先列事实清单：已确认的权限 API、动态字段、元数据字段、事务边界、现有 helper、配置能否覆盖；未确认项用项目源码、探针、官方资料或编译结果补证，仍无法确认时写明降级口径。
   - 涉及新增字段或字段重命名时，必须以当前目标环境元数据查询结果为最终字段标识来源；用户方案、历史记忆或草稿命名只能作为候选。若 dev 中实际字段标识与方案不同，代码、常量、查询字段和保存字段都必须对齐 dev 实际标识。
   - 涉及数据库字段名时，区分“字段标识”和“物理列名”：中铁项目物理列名按 `fk_开发商标识_标识名`，例如开发商标识为 `ztjg` 时使用 `fk_ztjg_xxx`；不要把字段标识直接当成物理列名。
   - 涉及单据字段时，必须证明字段处于目标读取层级：单据头字段、分录字段、子单据体字段不能混用；“实体里有这个 fieldKey”不等于“插件可按单据头字段读取”。
   - 用户要求字段必须放入字段布局面板时，优先按实体字段处理；标签、通用控件或不落库展示控件只能在用户接受非字段布局时使用。
   - 涉及移动端“默认赋值/默认带出/真实命中哪个插件”这类问题时，要区分业务实体插件、派生表单页面插件和列表插件三层证据；实体级插件清单不能直接代表移动表单或移动列表的真实执行链路。
9. 涉及表单跳转、在线编辑、WebOffice 或 `customParam` 透传时，编码前先列出 producer、参数解析类、consumer、关键回调链四段闭环；新增参数至少在这四处各核对一次。
10. 写插件代码前先读取对应 `assets/*.java` 模板；涉及高频片段时优先读 `assets/snippets/snippets-guide.md`，再选 1 个最接近 snippet。
11. 按离线优先兜底链路推进：项目源码/同类实现/`references`/`assets` -> 本地脚本/离线知识能力/脚本内置缓存 -> 本地依赖和 Gradle 验证 -> 在线元数据/基础资料增强；如果项目里已有 helper、标准服务、通用插件基类或 snippet 能覆盖需求，不再另写第二套工具方法。
12. 事件顺序、事务、字段、API、实体标识、保存目标或失败边界不确定时，先按 `references/index.md` 选择资料或脚本查证；能用本地证据保守推进的先推进并标明边界，只有关键事实仍无法确认且会直接影响正确性时才停问。
13. 修改 `.java` 后优先执行模块级 Gradle Wrapper 编译或测试；无法定位 Gradle 模块时执行 `python3 "$KINGDEE_COSMIC_SKILL_ROOT/scripts/cosmic-post-check.py" <文件或目录> --fix-hint`，无法执行时说明原因、替代验证和剩余风险。

## 任务路由门禁

| 任务类型 | 必读入口 | 关键门禁 |
|---|---|---|
| 表单/单据/列表 UI、字段联动、按钮控制 | `decision-matrix.md`、对应 `plugin-*.md`、`event-lifecycle.md`、`form-utils.md`、模板/snippet | `formId`、字段、事件点、控件 key 影响实现时必须确认；验证用 `compileJava`、定向测试或 `cosmic-post-check.py`。 |
| 操作、BOTP、回写、工作流 | `plugin-operation.md`、`operate-chain.md`、`botp-convert.md`、`plugin-workflow.md`、对应模板 | 操作编码、事务、源/目标单据、转换规则或回写阶段不明时停问；验证操作链路和来源/目标链路。 |
| 报表、DataSet、OpenAPI、后台任务 | 对应 `plugin-report-*`、`query-dataset.md`、`plugin-openapi.md`、`plugin-task.md`、对应模板 | 数据源、过滤条件、接口契约或调度上下文不明时停问；复核 DataSet 关闭、接口契约和编译结果。**数据准确性：统计数量不符时，先直连数据库验证实际数量，再定位代码差异。** |
| 基础资料、F7、组织/租户/权限 | `basedata-query.md`、`request-context.md`、`entity-metadata.md`、元数据/基础资料脚本 | `refType`、`entityId`、组织口径或权限范围不明时停问；用本地证据或脚本/缓存说明来源。 |
| 故障诊断、质量审查 | `issue-analysis.md`、`ai-code-review-patterns.md`、`cosmic-java-scan.md`、`post-check.md`、`references/issue-analysis/examples.md` | 先收集错误栈、模块、挂载点、复现步骤和最近变更；按生命周期定位（表单/操作/报表/工作流）→ 按错误类型分类（NPE/事务/权限/元数据）→ 引用 examples.md 中的类似案例（案例二十二至二十六：插件生命周期 NPE、事务回滚、挂载点冲突）；结论区分事实、推断和待验证项。代码扫描：`scripts/scan/scan_java_class.py <目录>` |

## 代码扫描与质量核查

### 快速单文件校验
```bash
# 单文件或目录快速校验
# KINGDEE_COSMIC_SKILL_ROOT = this skill's directory (resolve from symlink target or direct path)
# macOS/Linux:
export KINGDEE_COSMIC_SKILL_ROOT=<path-to>/kingdee-cosmic
# Windows CMD: set KINGDEE_COSMIC_SKILL_ROOT=<path>\kingdee-cosmic
# PowerShell:  $env:KINGDEE_COSMIC_SKILL_ROOT = "<path>\kingdee-cosmic"
python3 "$KINGDEE_COSMIC_SKILL_ROOT/scripts/cosmic-post-check.py" <文件或目录> --fix-hint
```

### 全量项目扫描（200+ 条苍穹规则）
```bash
# 1. 扫描禁用类
python scripts/scan/scan_java_class.py <代码目录>

# 2. 扫描禁用方法
python scripts/scan/scan_java_method.py <代码目录>

# 3. 扫描静态集合变量
python scripts/scan/scan_java_static.py <代码目录>

# 4. 扫描循环内禁用方法
python scripts/scan/scan_java_loop_method.py <代码目录>

# 5. 扫描循环内禁用类
python scripts/scan/scan_java_loop_class.py <代码目录>

# 6. 扫描禁用关键字
python scripts/scan/scan_java_keyword.py <代码目录>

# 7. 合并扫描结果
python scripts/scan/merge_scan_results.py

# 8. 生成扫描报告（Markdown；结果超过 20 条或显式要求时生成 HTML dashboard）
python scripts/scan/generate_scan_report.py
# 强制生成 HTML dashboard:
python scripts/scan/generate_scan_report.py --html always
# 禁止生成 HTML dashboard:
python scripts/scan/generate_scan_report.py --html never
# 使用指定扫描结果和输出目录:
python scripts/scan/generate_scan_report.py --result-file <scan_java_result.json> --out-dir <report-dir>
```

**扫描规则文件**：`references/quality/scan-rules/sonar_cve_*.md`（6个规则文件，覆盖禁用类、禁用方法、静态集合、循环内违规、禁用关键字）
HTML dashboard 是增强产物，不替代 Markdown 报告；页面必须支持搜索、等级筛选、卡片筛选、表格排序和当前视图复制。生成后用 `skills/meta/html-output-quality/scripts/check-html.mjs` 做质量门禁，聊天里只给 HTML 路径、检查状态和 High/Medium 问题。

## 执行门禁

- 生成 `@Override` 方法或调用 BOS SDK 关键方法前，必须用项目依赖、官方资料或 `scripts/cosmic-api-knowledge.py --config <配置文件> detail “类全限定名”` 验证签名；`cheat-sheet.md` 已列 API 可直接用。
- 以下情况先向用户确认或明确降级：配置能力可完成但用户要求插件、要改公共能力或批量写入、关键事实缺失、验证无法执行但仍需交付。
- 元数据全景分析、实体扫描、插件绑定分析优先交由 `kingdee-metadata-analyzer` 获取强证据；如果 analyzer 因凭据、网络或依赖暂不可用，先复用历史 analyzer 产物、项目源码、JAR、同类实现和 references 继续能完成的部分，并明确”未在线扫库”的边界。只有当前目标必须在线扫库且没有可用证据时，才询问用户补充凭据、切换环境或指定产物路径。
- 诊断任务先收集错误栈、触发场景、模块路径、插件挂载点、最近变更和复现方式；结论区分事实、推断和待验证项。
- 涉及在线编辑/WPS/WebOffice 展示策略或保护逻辑时，优先挂到文档就绪回调执行，不在 `open()` 后立刻抢跑；同时核对入口插件、配置类、预览插件和回调链是否已闭环。
- 注释遵循 `references/governance/comment-policy.md`：生成或修改 Java 代码时，类、公共方法、复杂私有方法、关键平台调用、事务/跨库/回写/DataSet/工作流边界必须有功能性注释；只写职责、业务口径、平台约束和边界条件。
- `scripts/*` 失败时先判断是配置缺失、在线能力不可用、脚本结构错误还是业务事实缺失；只有结构错误或关键事实缺失阻断当前任务。

## References
- 资料导航：`references/index.md`
- 开发流程和红线：`references/rules/workflow.md`、`references/rules/constraints.md`
- 关键事实判定与停问：`references/rules/fact-confirmation.md`
- 插件选型：`references/rules/decision-matrix.md`、`references/rules/intent-routing.md`
- 生命周期和速查：`references/adv/event-lifecycle.md`、`references/adv/form-utils.md`、`references/rules/cheat-sheet.md`、`references/rules/post-check.md`
- 注释规范：`references/governance/comment-policy.md`
- 质量扫描：`references/quality/cosmic-java-scan.md`
- 自检规则：`references/quality/ai-code-review-patterns.md`
- 故障诊断：`references/diagnostics/issue-analysis.md`
- 基础资料查询：`references/adv/basedata-query.md`
- 模板和片段：`assets/*.java`、`assets/snippets/snippets-guide.md`
- 查询和检查工具位于当前 skill 目录的 `scripts/` 下；在业务仓库执行时使用 `$KINGDEE_COSMIC_SKILL_ROOT/scripts/...`，不要写成业务仓库相对路径。
- 元数据全景分析：使用 `kingdee-metadata-analyzer`
- 数据库验证：从项目 `ok-cosmic.prod.json` 获取连接信息，Python psycopg2 直连 PostgreSQL；业务库在同实例的不同库名下，需逐库搜索目标表确认归属。

## Guardrails
- 市场资料只作参考源；正式方案必须结合当前项目规则、`${AI_KNOWLEDGE_ROOT}/kingdee/cosmic`、本地依赖和官方资料交叉校验。
- 字段、API、事件、实体标识不确定时必须查证；当前任务关键事实若无法从本地确认且会影响正确性，才停下来问用户，否则降级继续并说明风险。
- 规则用于提高命中率，不用于拒绝任务；遇到 skill 未覆盖的新苍穹场景时，先按“配置能力 → 项目源码/同类实现 → references/assets/scripts → 本地依赖/编译 → 在线资料”主动补证，再给可验证的最小方案。
- 严禁凭记忆或猜测生成 API 签名、事件方法名、实体标识、字段标识、`refType` 或返回结构。
- 新增类、工具类、公共方法、复杂私有方法、关键业务规则和不直观平台约束必须写功能性注释；不写过程性、交付性或机械复述注释。
- 涉及代码、注释、文档或提交时，署名必须遵守全局规则：不用 AI，统一用 `anfeng`。
- 项目源码、模板、snippet、标准服务或已有 helper 已能覆盖需求时，不新增第二套封装、工具类或平台调用包装。
- 不直接 SQL，不拼接 SQL/KSQL 条件字符串，不绕开平台 ORM、`QFilter`、元数据或标准服务能力。验证性数据核对可通过项目配置的数据库连接用脚本独立执行，不作为交付产物。
- 使用 `DataSet` 必须关闭；禁止在循环中访问数据库、Redis 或反复 `view.updateView()`；禁止 `printStackTrace()`。
- 数据验证由 agent 自行完成，不转嫁给用户执行。
- 不把实施过程、排查过程、修改经过或交付口径写入代码注释、skills、操作说明或示例说明。

## Output
使用简体中文：依据 → 方案 → 改动 → 验证 → 风险。依据必须标明来源类型，例如当前源码、同类实现、`references`、脚本/缓存、依赖编译结果或用户输入。
