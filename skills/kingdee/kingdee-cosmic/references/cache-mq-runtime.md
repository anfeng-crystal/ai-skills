# Cache / MQ 运行契约

## 证据状态

- 以下签名已由当前 skill 内置 SDK 索引确认：`AppCache`、`IAppCache`、`IPageCache`、`CacheFactory.getCommonCacheFactory()`、`MQFactory`、`MessagePublisher`、`MessageConsumer`、`MessageAcker`、`DLock`。
- 当前 SDK 索引未收录 `DistributeSessionlessCache` 类定义及其完整方法表。项目已使用该类时，必须再以目标项目 JAR、编译结果或同版本 Javadoc 确认签名；不能把社区示例当成已确认 API。

## Cache 选型与操作

| 场景 | 首选 | 已确认入口 |
|---|---|---|
| 单页面临时状态 | 页面缓存 | `this.getView().getPageCache()` -> `IPageCache` |
| 应用范围轻量共享 | 应用缓存 | `AppCache.get(String appKey)` -> `IAppCache` |
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
3. 缓存值必须有大小和条数上限；大集合改为分页、摘要或持久化存储。
4. 缓存未命中时先查数据；高并发热点使用同业务 key 的锁并在加锁后再次检查缓存，避免击穿。
5. 不存在结果需要短 TTL 的负缓存或等价限流策略，避免穿透；负缓存不能掩盖权限或路由错误。
6. 更新源数据后按一致性契约删除或刷新缓存；不能依靠进程重启。
7. 锁必须在 `finally` 或 try-with-resources 释放；锁 key 与缓存 key 使用同一业务隔离维度。

## MQ 已确认 API

- `MQFactory.get().createSimplePublisher(String region, String queue)`
- `MessagePublisher.publish(Object message)`
- `MessagePublisher.publishDelay(Object message, int seconds)`；当前 SDK 注释范围为 5 到 7200 秒
- `MessagePublisher.publishInDbTranscation(...)`；方法名以 SDK 中的 `Transcation` 拼写为准
- `MessagePublisher.close()`；发送结束必须释放 IO 资源
- `MessageConsumer.onMessage(Object message, String messageId, boolean resend, MessageAcker acker)`
- `MessageConsumer.getRouteKey()`；跨库事务消息按消费方实际数据库路由返回
- `MessageAcker.ack(String messageId)`、`deny(String messageId)`、`discard(String messageId)`
- `DLock.create(String key)`、`tryLock()`、`tryLock(long timeoutMillis)`、`unlock()`

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
4. 消息只携带最小业务标识，不放凭据、大对象或敏感明文；当前 SDK 建议消息小于 512KB。
5. 普通发布、延迟发布、数据库事务发布不能按名称猜选；先确认原子性需求、数据库路由和消费方 `getRouteKey()`。
6. region、queue、appid、消费者类和并发度从目标环境配置取证；不复制示例常量。
