# Cache / MQ 运行契约

## 证据状态

- 以下签名已由当前 skill 内置 SDK 索引确认：`AppCache`、`IAppCache`、`IPageCache`、`CacheFactory.getCommonCacheFactory()`、`MQFactory`、`MessagePublisher`、`MessageConsumer`、`MessageAcker`、`DLock`。
- 当前 SDK 索引未收录 `DistributeSessionlessCache` 的完整方法表。本地 7.0 `bos-cache`/`bos-entity-core` JAR 已确认：`DistributeSessionlessCache` 继承 `SessionlessCache<String>`，支持 `getAll(String)` 和 `put(String, Map<String,String>, int)`，TTL 单位为秒；`AppCacheImpl` 也使用分布式无会话缓存，并在 key 加上账套与 `appKey`。此证据粒度为 7.0，不推定补丁号或其他版本；使用时继续匹配目标依赖。

## Cache 选型与操作

详细知识与证据边界见 [云端缓存知识](https://chatgpt.com/space/page_4887970ebdd48191b69aae5afc1d7f54)。

| 场景 | 首选 | 已确认入口 |
|---|---|---|
| 单页面临时状态 | 页面缓存 | `this.getView().getPageCache()` -> `IPageCache` |
| 应用范围轻量共享（也是分布式缓存） | 应用缓存 | `AppCache.get(String appKey)` -> `IAppCache` |
| 跨节点、显式 region/TTL | 分布式无会话缓存 | 先核验目标项目 JAR 后再使用 |
| 基础资料标准缓存 | 平台加载缓存 | 先核验 `BusinessDataServiceHelper` 当前依赖签名 |

已确认的应用缓存签名：

- `IAppCache.get(String key, Class<T> clazz)`
- `IAppCache.put(String key, Object value)`
- `IAppCache.put(String key, Object value, int timeout)`，`timeout` 单位为秒
- `IAppCache.remove(String key)`

已确认的页面缓存能力包括 `put`、`get`、`remove`、`putBigObject`、`getBigObject`、`suspendCommit`、`resumeCommit` 和 `saveChanges`。循环批量更新页面缓存时，先暂停即时提交，结束后恢复并提交。

Cache 门禁：

1. key 必须包含应用/租户或业务域、实体/场景和业务主键，不能只用短编码或用户输入原文。
2. 共享缓存必须显式确定 TTL；永久有效只在已有稳定失效机制且需求明确时使用。
3. 缓存值必须有大小和条数上限；大集合改为分页、摘要或持久化存储。[官方 Redis 使用注意项](https://vip.kingdee.com/knowledge/698562532583371008)建议单次读取/写入小于 1M，集合二级条目最好少于 1000、不超过 10000；这是容量建议，不是所有 API 的硬限制。`getAll`/`hgetAll`、集合全量读取和前缀扫描只用于已知有界数据。
4. 缓存未命中时先查数据；高并发热点使用同业务 key 的锁并在加锁后再次检查缓存，避免击穿。
5. 不存在结果需要短 TTL 的负缓存或等价限流策略，避免穿透；负缓存不能掩盖权限或路由错误。
6. 更新源数据后按一致性契约删除或刷新缓存；不能依靠进程重启。集合 TTL 作用于一级 key，持续写入并延长 TTL 不会让各二级条目独立到期；必须另外清理旧条目或轮换有界集合。
7. 锁必须在 `finally` 或 try-with-resources 释放；锁 key 与缓存 key 使用同一业务隔离维度。

缓存查询投影与示例：

- `selectFields` 是查询投影，不是 `DynamicObject.getString(...)` 的单个属性名；多字段或表达式结果应按查询返回属性/明确别名逐项取值后序列化。不要用逗号拆分解析带参数的表达式。
- key 必须区分实体、完整投影（含别名）、业务范围及结果结构版本；避免同一业务 key 的不同字段集合互相命中。
- `assets/snippets/cache/SampleCacheUsage.java` 保留多字段映射，使用返回属性元数据生成 JSON，并显式检查条数、UTF-8 字节量、TTL 与重复主键。示例只适合具有 `status`/`enable` 字段的小型映射；热点互斥和空结果负缓存仍需按调用场景补齐。
- AppCache 的本地 7.0 实现通过 `SerializationUtils` 写入 JSON，不能据此要求所有对象实现 Java `Serializable`。无 TTL 重载委托底层缓存，不据名称推定固定 1 小时；共享状态优先显式传 TTL。

需要观察运行中的缓存操作时，可按[实体运行监控工具](https://vip.kingdee.com/knowledge/494819274104384256)定位 `appcache.*`（应用缓存）和 `pagecache.*`（页面缓存）。该工具支持 V5.0.12+，V6+ 入口是“系统服务云 → 日志管理 → 实体运行监控”；仅监听当前账号。暂停只停止刷新，停止才结束监听。监控分类不能替代目标 SDK 的缓存作用域证据。

## MQ 已确认 API

详细知识与证据边界见 [云端 MQ 知识](https://chatgpt.com/space/page_67b293e5c7808191b181e944f5964480)。

- `MQFactory.get().createSimplePublisher(String region, String queue)`
- `MessagePublisher.publish(Object message)`
- `MessagePublisher.publishDelay(Object message, int seconds)`；当前 SDK 注释范围为 5 到 7200 秒
- `MessagePublisher.publishInDbTranscation(Object message)`、`publishInDbTranscation(String routeKey, Object message)`；方法名以 SDK 中的 `Transcation` 拼写为准
- `MessagePublisher.close()`；发送结束必须在 `finally` 释放 IO 资源。本机 7.0 接口不继承 `AutoCloseable`，不能直接把 publisher 放入 try-with-resources
- `MessageConsumer.onMessage(Object message, String messageId, boolean resend, MessageAcker acker)`
- `MessageConsumer.getRouteKey()`；跨库事务消息按消费方实际数据库路由返回
- `MessageAcker.ack(String messageId)`、`deny(String messageId)`、`discard(String messageId)`
- `DLock.create(String key)`、`tryLock()`、`tryLock(long timeoutMillis)`、`unlock()`

以上发布/消费签名另由本机 7.0 `bos-mq` JAR 核对，补丁号未确认；该 JAR 的 `MQFactory` 没有 `send`，按 `createSimplePublisher → publish → close` 使用。普通、延迟和事务发布能力均保留；行为说明结合官方 SDK V8.0.1，不能将其当作 7.0 平台运行验收。

## MQ 状态与失败规则

| 结果 | 应答 | 必要证据 |
|---|---|---|
| 业务动作已成功，或幂等台账确认已完成 | `ack` | 业务幂等键和最终状态 |
| 超时、依赖不可用、锁竞争等可恢复错误 | `deny` | 失败类型、重试计数或外部重试策略 |
| 消息格式永久无效、业务规则明确不可恢复 | `discard` | 永久失败分类和可追踪记录 |
| 未分类异常 | 默认 `deny` 或让消费失败 | 不得直接 `discard` 掩盖未知错误 |

MQ 门禁：

1. `messageId` 不是全局唯一，`resend` 也不能作为幂等判定；幂等键来自队列/业务类型/业务主键或发送方事件 ID。
2. 先持久化或确认业务最终状态，再 `ack`；不得先确认后写业务状态。
3. 重试必须有上限、退避和最终失败去向；平台未提供这些能力时，把缺口列为部署前门禁。
4. 消息只携带最小业务标识，不放凭据、大对象或敏感明文；官方 SDK 文档建议消息小于 `512Kb`（原文记法），这是容量建议，不据此推定所有重载的硬阈值。
5. 普通发布、延迟发布、数据库事务发布不能按名称猜选；先确认原子性需求、发送方业务事务及数据库路由，跨库时按消费方实际数据库重写 `public String getRouteKey()`。数据库事务发布不自动覆盖外部接口副作用。
6. region、queue、appid、消费者类和并发度从目标环境配置取证；不复制示例常量。
7. `OperationResult.isSuccess()==false` 不足以证明永久失败；仅按已核实的结构化业务错误分类 `discard`，分类未知则 `deny` 或让消费失败。官方示例里的某个异常类型不构成通用丢弃规则。
8. 业务处理与最终应答分开：`ack` 抛错不能反写业务失败或在同一 acker 上再 `deny`。本机 7.0 Rabbit 实现先标记 acker 已访问，再调用 broker；后续应答可能直接返回，不能把补一次 `deny` 当作恢复保证。
9. DLock 只防并发，不能证明业务恰好一次。远端成功而本地保存失败的窗口，需要远端识别同一稳定幂等键或查询最终结果；幂等键包含业务隔离维度，不能仅拼消息对象的 `toString()`。
10. 示例 `assets/snippets/mq/SampleMQConsumer.java` 保留操作和消息池两场景，固定实体/载荷类型/正整数Long主键，先校验再调用业务；查不到单据、读取/保存失败或未实现钩子不确认成功。示例元数据、持久完成检查、外部调用和重试上限必须落到目标业务；配套 XML 只注册实际存在的类。
