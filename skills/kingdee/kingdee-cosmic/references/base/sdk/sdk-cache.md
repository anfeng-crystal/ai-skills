# 缓存服务 (Cache Service)

详细知识与证据边界见 [云端缓存知识](https://chatgpt.com/space/page_4887970ebdd48191b69aae5afc1d7f54)。

## TL;DR
- 适用：页面缓存和应用缓存，解决跨操作临时数据与应用级共享数据。
- 先抓：表单内优先 `IPageCache`，跨页面/应用再用 `AppCache`。
- 跳转：并发互斥不是缓存，去锁或网控文档；持久化数据也不是本页。
- 继续读全文：当你要确认作用域、有效期、示例和常见误用时。

## 概述
金蝶云苍穹提供页面缓存和应用缓存。页面缓存用于当前表单的临时状态；应用缓存用于应用范围共享数据。本地 7.0 `bos-entity-core` JAR 中，`AppCacheImpl` 使用 `DistributeSessionlessCache`，缓存 key 包含账套与 `appKey`，不是只在同一 JVM 共享。具体节点配置、失效行为和目标补丁仍以项目依赖与运行配置为准。

## 核心类
- **`kd.bos.form.IPageCache`**: 页面级缓存接口，仅限表单插件使用。
- **`kd.bos.entity.cache.AppCache`**: 获取应用级缓存的工具类。
- **`kd.bos.entity.cache.IAppCache`**: 应用级缓存接口。

## 常用 API 方法
### 页面缓存 (this.getPageCache())
- `put(String key, String value)`: 存入单条数据。
- `put(Map<String, String> values)`: 批量存入。
- `get(String key)`: 读取数据。

### 应用缓存 (AppCache.get("appId"))
- `put(String key, Object value)`: 存入数据；本地 7.0 实现委托底层无显式 TTL 的重载，不能据此断言固定 1 小时过期。
- `put(String key, Object value, int seconds)`: 存入带自定义过期时间的数据。
- `get(String key, Class<T> clazz)`: 类型安全地读取数据。
- `remove(String key)`: 显式移除缓存。

## 示例代码
```java
// 1. 页面缓存示例（在表单插件中）
public class MyFormPlugin extends AbstractFormPlugin {
    public void cacheTempData() {
        this.getPageCache().put("temp_token", "ABC-123");
        String token = this.getPageCache().get("temp_token");
    }
}

// 2. 应用缓存示例（通用场景）
import kd.bos.entity.cache.AppCache;
import kd.bos.entity.cache.IAppCache;

public class CacheDemo {
    public void handleAppCache() {
        IAppCache cache = AppCache.get("my_app_id");
        // 存入缓存，有效期 10 分钟
        cache.put("user_config", configObj, 600);
        
        // 读取缓存
        MyConfig config = cache.get("user_config", MyConfig.class);
    }
}
```

## 实践建议
1. **优先批量操作**：缓存访问虽然快，但高频的网络交互仍有开销，存入多条数据时优先使用批量接口。
2. **应用编码隔离**：调用 `AppCache.get()` 时，务必传入正确的 `appId`，以实现各应用间的数据隔离。
3. **及时释放**：对于不再需要的应用缓存，应主动调用 `remove`，防止缓存堆积。

## 常见坑位
1. **缓存一致性**：由于是分布式缓存，注意在多节点并发更新同一 Key 时可能产生的数据覆盖问题。
2. **序列化要求**：本地 7.0 `AppCacheImpl` 通过 `SerializationUtils.toJsonString` 写入，读取时按目标类型反序列化。值须适配该 JSON 序列化契约；不能把实现 Java `Serializable` 当作充分条件或统一必需条件。
3. **大小限制**：严禁将超大对象（如数万行的 List）放入缓存，这会显著增加网络传输和 Redis 内存压力。
具体容量、集合 TTL 与查询投影隔离见 [Cache / MQ 运行契约](../../cache-mq-runtime.md)。
