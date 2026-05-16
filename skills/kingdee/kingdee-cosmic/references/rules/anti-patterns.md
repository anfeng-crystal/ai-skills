# 禁忌清单 (Anti-Patterns)

> 本文件所有条目默认属于 **A 层硬约束**，除非单独标注 `[B层]`。
> 对应的 lint 规则 ID 前缀：`HAL-*`（幻觉）、`SCENE-*`（场景错配）、`STYLE-*`（可扫描坏味道）、`RESOURCE-*`（资源管理）。

## 幻觉方法名黑名单 `[A层]`

| 错误写法 | 正确替代 | 说明 |
|---|---|---|
| `setReadOnly(...)` | `getView().setEnable(false, "key")` | 苍穹不存在 setReadOnly 方法 |
| `afterCreateControl(...)` | `afterBindData` / `registerListener` | 不存在该事件方法 |
| `IDataModel.setReadOnly(...)` | `getView().setEnable(false, "key")` | 模型层不负责 UI 状态 |
| `this.getView().refresh()` | `this.getView().updateView(key)` | 不存在 refresh()，使用 updateView |
| `model.getEntryCount(...)` | `model.getEntryRowCount(entryKey)` | 方法名和参数都不同 |
| `model.deleteRow(...)` | `model.deleteEntryRow(entryKey, rowIndex)` | 方法名不同 |
| `model.addRow(...)` | `model.createNewEntryRow(entryKey, rowIndex)` | 方法名不同 |
| `destroy(...)` | `destory(...)` | 苍穹方法名就是 destory（少 r），不是 destroy |

## 幻觉类名黑名单 `[A层]`

- ❌ 不存在以 `Cosmic` 或 `Cloud` 开头的工具类，除非脚本明确查到。
- ❌ 不存在 `BillHelper`（应为 `BusinessDataServiceHelper`）。
- ❌ 不存在 `FormHelper`（应为 `FormUtils`，位于 `kd.cd.common.form`）。
- ❌ 不存在 `ListHelper`（应为 `BaseDataServiceHelper` 或 `QueryServiceHelper`）。
- ❌ 不存在 `PluginHelper`（应按具体场景使用对应 ServiceHelper）。

## 场景错配黑名单 `[A层]`

| 错误做法 | 原因 | 正确做法 |
|---|---|---|
| 在操作插件中调用 `this.getView()` | 操作插件无 UI 上下文 | 使用 `log` 或 `addErrorMessage` |
| 在操作插件中 `this.getModel().setValue(...)` | 操作插件不通过 model 操作 | 直接操作 `DynamicObject` 数据包 |
| 在 UI 插件中做重查询/复杂事务 | UI 插件应保持轻量 | 移至操作插件或服务层 |
| 在 `initialize()` 中注册监听或写 UI 状态逻辑 | 生命周期不对，可能失效或错时执行 | 在 `registerListener` 注册，在 `afterBindData` 处理界面状态 |
| 在 `registerListener` 中调用 `model.getValue(...)` | 此时数据尚未绑定 | 推迟到 `afterBindData` |
| 在 `beforeBindData` / `afterBindData` 中 `setValue` 或改数据包 | 绑定阶段禁止改数据 | 改到 `createNewData`、`propertyChanged`、保存前等正确事件 |
| 在 `afterCreateNewData` 中期望触发 `propertyChanged` | 此时赋值不触发 | 在 `afterBindData` 中处理级联 |
| 仅 `implements Listener` 不注册监听 | 监听不会生效 | 在 `registerListener` 中调用 `add*Listener` |
| 对继承型插件 `@Override` 不调 `super.xxx()` | 基类初始化逻辑不执行 | 继承型必须先调 `super`；接口型无需 |
| 直接修改 `EntityMetadataCache` 返回的元数据对象 | 缓存对象是单例，污染全局 | `clone` 后再修改 |
| 用其他实体 `createInstance()` 的对象给引用属性赋值 `→ SCENE-010` | 引用对象类型可能不一致 | 使用属性复杂类型或当前实体元数据创建对象 |

## 可扫描坏味道黑名单

以下条目统一保留"可直接扫描 / 可直接进 lint"的模式，不再与上面的"场景错配"重复展开。
每条末尾标注层级（`[A层]` = 硬约束 / `[B层]` = 推荐项），层级与 [a-layer-rules.json](a-layer-rules.json) 保持一致。

| 可扫描模式 | 风险 | 正确做法 | 层级 |
|---|---|---|---|
| `StringUtils.*Blank/*Empty/*equals` | 风格不一致 | 使用 `CharSequenceUtils` | `[B层]` |
| `!= null && !collection.isEmpty()` | 风格不一致 | 使用 `CollectionUtils.isNotEmpty(...)` | `[B层]` |
| 散落调用 `OperationServiceHelper.save/submit/audit` | 缺少错误聚合 | 使用 `OpUtils` 或 `OperateChain` | `[B层]` |
| `new PushArgs(...)` / `new DrawArgs(...)` | 手拼转换参数，重复样板多 | 使用 `BotpUtils` | `[B层]` |
| `BusinessDataServiceHelper.loadFromCache(...)` 以外反复查基础资料 | 容易退化成逐条查询 | 优先 `loadFromCache(...)` 或批量查询 | `[B层]` |
| `new Thread(...)` | 绕开平台线程池，丢失统一监控、资源回收和 `RequestContext` 传递 | 使用 `kd.bos.threads.ThreadPools` | `[B层]` |
| `Executors.*` | 直接使用 JDK 线程池，无法遵守平台线程治理约束 | 使用 `ThreadPools.new*` / `ThreadPools.executeOnce*` | `[B层]` |
| `QueryServiceHelper.queryOne(...) != null` | 以"取一条"代替"判存在"，多做对象构造和字段读取 | 使用 `QueryServiceHelper.exists(...)` | `[B层]` |
| `dynamicObject.get("a.b.c")` | 深链取值不安全 | 使用 `DynamicObjectUtils` 安全取值 | `[B层]` |
| 循环中出现 `DB.*` | 典型 N+1 / 性能风险 | 先收集条件，再批量查询 | `[A层]` → `STYLE-014` |
| 循环中出现 `BusinessDataServiceHelper.*` / `QueryServiceHelper.*` | 典型 N+1 / 缓存风暴 | 先参考 `assets/snippets/query/BatchQuerySample.java`，改成"分组 key -> 批量加载 -> 本地映射" | `[A层]` → `STYLE-015` |
| 循环中出现 `ORM.create(...)` | 循环内频繁建包/持久化，容易造成性能问题 | 先批量组织数据，按批次处理 | `[A层]` → `STYLE-016` |
| 循环中出现 `DispatchServiceHelper.invoke*` | 远程调用放进循环，容易放大时延和失败面 | 合并调用、批量调用或先聚合参数 | `[A层]` → `STYLE-016` |
| 循环中出现 `view.updateView(...)` | 高频 UI 刷新，前端和服务端开销都高 | 循环结束后统一局部刷新 | `[A层]` → `STYLE-016` |
| `QueryServiceHelper.query(...)` 结果直接 `set(...)` 或直接参与 `save/update` | `query` 返回的是扁平结果，不是可回写实体包 | 先 `query` 出 id，再 `load` 实体包后更新，参考 `assets/snippets/query/BatchQuerySample.java` | `[A层]` → `STYLE-011` |
| 插件成员变量持有 `DataSet`、`InputStream`、`OutputStream`、`Connection`、`ResultSet` | 序列化问题或资源泄漏 | 只在方法内短持有，用完立即关闭 | `[A层]` → `RESOURCE-004` |
| `DataSet` 只创建不 `close()` | 资源泄漏 | 使用 try-with-resources 或在最近使用点关闭 | `[A层]` → `RESOURCE-004` |
| 非 final 的 `static` 状态变量 | 多实例冲突 | 使用 `PageCache` 或实例变量 | `[B层]` |
| 数据库方言 SQL（如 `limit` / `rownum` / `nvl` / `isnull`） | 跨库兼容性差 | 使用 KSQL 或平台查询接口 | `[A层]` → `STYLE-012` |
| `SerializationUtils.toJsonString(args)` 直接打印页面对象、事件对象、数据对象 | JSON 序列化成本高，且容易把大对象整包打进日志 | 只按需提取关键字段打印 | `[B层]` |
| `printStackTrace()` | 日志无统一上下文，不利于检索与定位 | 使用 `logger.error("问题描述", e)` | `[A层]` → `STYLE-009` |
| `throw new RuntimeException(...)` / `throw new IllegalArgumentException(...)` / `throw new IllegalStateException(...)` | 业务异常类型不统一 | 改为 `KDBizException`，包装时保留原始 `cause` | `[A层]` → `STYLE-018` |
| `"关于" + name + "的第" + times + "次答疑"` 这类中文词条拼接 | 翻译后语序不可控 | 使用完整句模板 + `String.format(ResManager.loadKDString(...), ...)` | `[B层]` |
