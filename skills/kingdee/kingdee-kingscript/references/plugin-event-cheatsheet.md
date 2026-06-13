# KingScript 插件基类×事件 / SDK 导入速查

快速定位入口用;最终 API 签名、事件参数类型仍以 `references/sdk/` 与 `references/language/` 的具体卡片为准,不凭本表猜签名。

## 插件基类 × 事件

| 插件类型 | 基类 | 导入路径 | 核心事件(触发序) |
|---|---|---|---|
| 动态表单 | `AbstractFormPlugin` | `@cosmic/bos-core/kd/bos/form/plugin` | registerListener → afterCreateNewData → afterBindData → propertyChanged → beforeDoOperation → afterDoOperation |
| 单据界面 | `AbstractBillPlugIn` | `@cosmic/bos-core/kd/bos/bill` | 同表单 + afterLoadData / loadData |
| 移动端单据 | `AbstractMobBillPlugIn` | `@cosmic/bos-core/kd/bos/bill` | 同单据(部分事件受限) |
| 标准列表 | `AbstractListPlugin` | `@cosmic/bos-core/kd/bos/list/plugin` | filterContainerInit → setFilter → beforeCreateListColumns → itemClick → beforePackageData |
| 左树右表列表 | `AbstractTreeListPlugin` | `@cosmic/bos-core/kd/bos/list/plugin` | 同标准列表 |
| 操作服务 | `AbstractOperationServicePlugIn` | `@cosmic/bos-core/kd/bos/entity/plugin` | onPreparePropertys → onAddValidators → beforeExecuteOperationTransaction → beginOperationTransaction → endOperationTransaction → afterExecuteOperationTransaction |
| 报表界面 | `AbstractReportFormPlugin` | `@cosmic/bos-core/kd/bos/report/plugin` | verifyQuery → beforeQuery → afterQuery → processRowData → packageData |
| 调度任务 | `AbstractTask` | `@cosmic/bos-core/kd/bos/schedule/executor` | execute(唯一) |

选型:界面加载/字段联动/控件状态→表单或单据;列表过滤/批量→列表;保存/提交/审核前后→操作;报表查询/DataSet→报表。基类与注册场景必须匹配,单据不能用 `AbstractFormPlugin`。

## SDK 模块与导入映射

| 模块 | 内容 | 示例 |
|---|---|---|
| `@cosmic/bos-script` | Java 标准库/基本类型/集合/math | `import { ArrayList } from '@cosmic/bos-script/java/util'`;`import { BigDecimal } from '@cosmic/bos-script/java/math'` |
| `@cosmic/bos-util` | 公共工具(http/缓存/编码) | `import { HttpClient } from '@cosmic/bos-util/http'` |
| `@cosmic/bos-core` | 苍穹核心功能 | `import { BusinessDataServiceHelper } from '@cosmic/bos-core/kd/bos/servicehelper'` |

映射规则:Java 包名 `.` 换 `/`,前缀加模块名。例:`kd.bos.servicehelper` → `@cosmic/bos-core/kd/bos/servicehelper`;`java.util` → `@cosmic/bos-script/java/util`。

常用:`DynamicObject`(`bos-core/kd/bos/dataentity/entity`)、`EntityMetadataCache`(`bos-core/kd/bos/entity`)、`RequestContext`(`bos-core/kd/bos/context`)、`LogFactory`(`bos-core/kd/bos/logging`)。

## 语法关键约束

- 不支持 static 成员/静态方法/静态字段。
- 财务计算必须用 `BigDecimal`(`new BigDecimal("100.50")`),禁用 number;Date 比较用 `compareTo()`/`getTime()`,禁 `>`/`<`/`===`。
- 序列化:JS 原生用 JSON,Java 对象用 `SerializationUtils`。
- `let`/`const` 显式类型;方法明确返回类型;异常不静默吞,应抛出友好提示。
- 限流:`Query/BusinessDataServiceHelper` 每事务 ≤100 次查询、单次 ≤50000 行;`Save/DeleteServiceHelper` 每事务 ≤150 次 DML、单次 ≤10000 条;`AppCache/PageCache` 单 key/value ≤5M;禁直接用 `kd.bos.db.DB` / `kd.bos.orm.ORM`。
