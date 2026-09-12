# API 废弃与替换核验

保留此文件名供现有引用使用；这里是核验入口，不能把无来源的历史表当作苍穹通用废弃黑名单。只对目标版本和完整重载有 `@Deprecated` / Javadoc 废弃标记或官方迁移公告的条目，按项目规则提出替换。批量调用偏好、方法未列出、返回类型不同与正式废弃是不同事实。

## 已从官方原文核对的反例

以下范围为 **Cosmic V8.0.1**，核验日期 2026-09-07；不向旧版本或所有未来版本外推。

| 历史断言 | 官方证据与正确处理 |
|---|---|
| `QueryServiceHelper.query(entity, fields, filter, orderBy, limit)` 已废弃，改为末参 `top` | 官方列出 `query(String, String, QFilter[], String, int)`，末参名为 `top`，该重载未见废弃标记。参数变量叫 limit 或 top 不构成不同 Java 签名，不因改名触发迁移 |
| `SaveServiceHelper.update(obj)` 已废弃，必须改数组 | 官方同时公开单个 `DynamicObject` 与 `DynamicObject[]` 入口，包括各自带 `OperateOption` 的重载，均未见废弃标记。按当前单条/批量语义和目标 SDK 选择；批量效率建议不能写成废弃事实 |
| 操作调用的替换建议仅列 `DynamicObject[]` | 官方同时公开 `executeOperate(String, String, Object[], OperateOption)` 和 `DynamicObject[]` 版本。保留主键数组路径；补 `OperateOption` 必须先确认目标实际签名，不强行把主键改造成不完整数据包 |
| `RequestContext.getUserId()` 已废弃，因此一律替换 | 此版公开 `public long getCurrUserId()`；未列 getUserId 并不能证明其历史废弃版本。先核对旧项目调用的实际类、返回类型及 SDK，不能仅据名称替换 |

官方版本化来源：[QueryServiceHelper](https://dev.kingdee.com/sdk/Cosmic%20V8.0.1/javadoc/kd/bos/servicehelper/QueryServiceHelper.html)、[SaveServiceHelper](https://dev.kingdee.com/sdk/Cosmic%20V8.0.1/javadoc/kd/bos/servicehelper/operation/SaveServiceHelper.html)、[OperationServiceHelper](https://dev.kingdee.com/sdk/Cosmic%20V8.0.1/javadoc/kd/bos/servicehelper/operation/OperationServiceHelper.html)、[RequestContext](https://dev.kingdee.com/sdk/Cosmic%20V8.0.1/javadoc/kd/bos/context/RequestContext.html)。

## 其余历史候选：未确认，禁止自动替换

以下旧表条目未附可核验的正式废弃版本或迁移依据；保留检索线索，不保留未经证实的替换映射。

- `KingdeeBaseDataServiceHelper.loadSingle` / `loadSingleFromCache`：核实类是否来自目标产品、SDK 或项目封装，再查缓存和主键类型合同。
- `DynamicObjectUtils.copy`、`DataEntityUtils.toJson`：核实实际包、深复制或序列化语义，不能仅因存在另一个工具类就判为废弃。
- `BusinessDataServiceHelper.loadFromCache`：区分单条与批量返回结构；性能选型不是废弃依据。
- `CacheFactory.getMVCCache().getOrCreate`：先确认类、缓存层级、作用域及确切方法，不能拼出不存在的工厂调用链。
- `MessageInfo.setMessageContent`：确认消息类型及目标版本，不依据命名偏好替换为另一个 setter。
- `ConvertServiceHelper.push`：核对实际全限定名、参数和返回类型，不用无来源的“5.0 改版”结论推断迁移。
- `StringUtils.isEmpty` 与 `isBlank`：语义不同；包迁移与空白判定必须分别核对，不以替换改变业务结果。
- `DateUtils.format`：核对实际包、重载与格式/时区合同，不能通过更换工具静默改变输出。

## 执行与输出

1. 经 `kingdee-sdk-helper` 定位目标项目依赖、同版本官方 Javadoc 或带出处的索引。
2. 记录类全名、完整参数类型、静态/实例属性、返回类型、废弃标记及来源版本；Java 废弃、脚本废弃和内部 API 标记分别报告。
3. 只有目标版本确认不适用或已废弃时才提出具体修正，保留行为/事务/缓存合同，并做适当编译或回归检查。
4. 证据不足写 `unconfirmed`；继续独立工作，不制造已确认错误、不做全库替换，也不把未核验调用写成可运行示例。
