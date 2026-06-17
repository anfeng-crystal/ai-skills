# 编码偏好、默认写法与治理方向

**B 层** 和 **C 层** 规则：

- **B 层：推荐项 / 新代码默认写法**
  - 新生成代码默认尽量遵守。
  - 历史存量代码若暂未满足，不因此直接判为错误。
- **C 层：目标态治理 / 渐进优化**
  - 适合模板升级、专项治理、批量重构。
  - 默认不作为一次性交付阻断项。

真正的硬红线请看 [constraints.md](constraints.md)。

## B1. 新代码默认写法

### 插件基类与封装优先级

- **[B1.1]** **插件基类（封装层）**：新代码优先选择 `kd.cd.common.plugin` 包下的扩展基类：
  `AbstractBillPlugInExt`、`AbstractFormPluginExt`、`AbstractListPluginExt`、`AbstractOperationServicePlugInExt`、`AbstractValidatorExt`
- **[B1.2]** **原生插件基类**：BOTP 转换（`AbstractConvertPlugIn`）和反写（`AbstractWriteBackPlugIn`）没有 `*Ext` 封装版本，直接使用 `kd.bos.entity.botp.plugin` 包下的原生基类。
- **[B1.3]** 如果必须给出原生写法：
  先说明为什么仓库封装不适用，再给最小可行实现，不要把原生样板扩散成默认风格。
- **[B1.4]** 历史项目中大量原生基类写法是可预期的；评估现有代码时，不要因为“不是 Ext 基类”就直接判错。

### 工具类与实现风格

- **[B1.5]** 需要错误汇总时，优先使用 `OpUtils.addErrorMessage(...)`、`OpUtils.getCompleteFailMsg(...)`、`PushResult.failThenThrow()`
- **[B1.6]** 字符串判空优先使用 `CharSequenceUtils`；不要在**新示例代码**里混用 `StringUtils`、`ObjectUtils` 做字符串空白判断。
- **[B1.7]** 集合判空优先使用 `CollectionUtils`；不要在**新示例代码**里手写 `!= null && !isEmpty()`。
- **[B1.8]** 对异常优先使用日志框架记录；`*Ext` 基类里直接使用内置的 `public final Log log`，非插件类可直接使用 `kd.bos.logging.LogFactory`。
- **[B1.9]** 未经用户明确要求，不要偏离 `assets/FormPluginTemplate.java` 的代码风格；确需偏离时，在答案里说明原因。
- **[B1.10]** 若必须新增模板之外的 `import`，需仅新增最小集合，并说明新增原因。

### 业务封装优先级

- **[B1.11]** 对单据状态流转，优先使用 `OpUtils`；不要在**新代码**里散落调用多个 `OperationServiceHelper`。
- **[B1.12]** 只有在需要连续调用多个操作时，才优先使用 `OperateChain`；单次 `save`、`submit`、`audit` 优先使用 `OpUtils`。
- **[B1.13]** 对单据转换，优先使用 `BotpUtils`；不要在**新代码**里手拼 `PushArgs`/`DrawArgs` 等重复样板。
- **[B1.14]** 处理基础资料（BaseData）相关业务动作时，先查 `BaseDataServiceHelper` 是否已有现成方法。
- **[B1.15]** 在操作插件里，除非需要准备的字段非常多，否则不要使用 `allFields()`；优先按实际场景显式准备字段。
- **[B1.16]** 对查询，优先使用 `QueryUtils` + `AlgoUtils`；不要先写裸 SQL 或循环查库。
- **[B1.17]** `QueryServiceHelper.query(...)` 查出来的是扁平结果集，默认只用于读取、分组、聚合；不要直接 `set(...)` 后 `SaveServiceHelper.update/save(...)`。
- **[B1.18]** 查询基础资料时，优先使用 `BusinessDataServiceHelper.loadFromCache(...)`；不要对基础资料反复用普通查询接口查库。
- **[B1.19]** 对动态对象取值，优先使用 `DynamicObjectUtils`；不要直接深链式 `get("a.b.c")`。
- **[B1.20]** 对附件处理，优先使用 `AttachmentUtils` 和 uploader；不要直接散落调用 `AttachmentServiceHelper`。
- **[B1.21]** `references/base/*` 只用于补齐原生知识、事件签名和缺失能力；不要因为能写原生 API 就绕开现有封装。

### 查询、资源与提示语

- **[B1.22]** 判断“是否存在”时，**新代码优先**使用 `QueryServiceHelper.exists(...)`，不要继续放大 `queryOne(...) != null` 这种写法。
- **[B1.23]** 查询时只取实际需要的字段；除加载完整单据/基础资料外，不要默认 `allFields()` 或无选择地查整包数据。
- **[B1.24]** `DataSet` 使用后要在最靠近创建/转换的位置关闭；优先用清晰的生命周期包裹，避免跨方法悬挂。
- **[B1.25]** 需要参数化查询时，优先使用平台查询构造或 KSQL 参数，不要手拼 where 条件字符串。
- **[B1.26]** 面向用户的提示语要体现业务语义和下一步动作，不要只抛底层异常文本。
- **[B1.27]** 报表或大结果集处理时，优先复用已查询数据，并用 `algo` 做分组、去重、统计；不要把大聚合逻辑堆进 Java 循环。

## B2. 元数据与脚本配合细则

- **[B2.1]** **元数据查询约束**：调用 `cosmic-form-metadata.py` 时，脚本会无条件展示所有字段；如果概览模式未显示所需字段，请主动在 `--fuzzy` 中增加搜索词进行精准匹配。
- **[B2.2]** 如果脚本未查到字段或表单元数据，必须提醒用户确认其提供的表单名称/标识是否正确，再继续处理。
- **[B2.3]** **批量合并**：需要确认多个字段时，必须合并为一次 `--fuzzy` 调用（如 `--fuzzy qty price amount material org`），严禁逐个字段发起多次查询。
- **[B2.4]** **自动详情**：当 `--fuzzy` 传入 ≥3 个关键词时，脚本自动升级为详情模式（含枚举/refType），无需手动追加 `--show-detail`。
- **[B2.5]** **常规字段对齐**：仅确认 1-2 个字段标识时，不带 `--show-detail` 和 `--sql`。
- **[B2.6]** **深度实现**：当需要编写枚举判断、手动赋值或基础资料关联查询前，带上 `--show-detail`。
- **[B2.7]** **生成 SQL**：除非用户强依赖编写原生 JDBC/SQL 查询，否则默认不要使用 `--sql`。

## C1. 目标态治理项

以下内容仍然推荐，但默认作为长期治理方向，而不是当前一次性交付阻断项：

- **[C1.1]** **验证来源注释**：建议在关键 `@Override` 方法或 BOS SDK 关键调用附近补充“验证来源”注释，作为事实留痕。
- **[C1.2]** **异常体系统一**：建议逐步把历史项目中的 `RuntimeException`、`IllegalArgumentException` 等，收敛到更明确的业务异常或带 `cause` 的统一异常体系。
- **[C1.3]** **日志治理**：建议逐步清理历史代码中的 `printStackTrace()`，统一为 `logger.error("问题描述", e)`。
- **[C1.4]** **存在性判断治理**：建议在后续重构中逐步把 `queryOne(...) != null` 迁移为更明确的存在性判断或领域查询封装。
- **[C1.5]** **原生基类迁移**：对稳定运行的历史插件，不要求为了“改成 Ext 基类”而进行无收益重构；只有在功能演进、模板升级、公共封装复用收益明确时再迁移。

## C2. 评估历史代码时的默认口径

- **[C2.1]** 发现历史代码使用原生基类、`StringUtils`、`queryOne(...)`、`OperationServiceHelper.executeOperate(...)` 等写法时，先判断其是否触犯 [constraints.md](constraints.md) 中的硬红线。
- **[C2.2]** 若没有触犯 A 层红线，则应描述为：
  - “当前可运行的历史写法”
  - “建议新代码采用的替代写法”
  - “是否值得在本次需求中顺手收敛”
- **[C2.3]** 不要把所有历史写法一律描述成“错误”；要区分 **硬错误**、**推荐替换**、**后续治理** 三种层级。