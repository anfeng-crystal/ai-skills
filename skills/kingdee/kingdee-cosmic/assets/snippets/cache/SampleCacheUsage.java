package kd.cd.common.snippets;

import kd.bos.cache.CacheFactory;
import kd.bos.cache.DistributeSessionlessCache;
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.dataentity.entity.DynamicObjectCollection;
import kd.bos.dataentity.metadata.IDataEntityProperty;
import kd.bos.dataentity.serialization.SerializationUtils;
import kd.bos.entity.cache.AppCache;
import kd.bos.entity.cache.IAppCache;
import kd.bos.logging.Log;
import kd.bos.logging.LogFactory;
import kd.bos.orm.query.QCP;
import kd.bos.orm.query.QFilter;
import kd.bos.servicehelper.BusinessDataServiceHelper;
import kd.bos.servicehelper.QueryServiceHelper;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * 缓存使用示例 —— AppCache / DistributeSessionlessCache / loadFromCache。
 * <p>
 * 适用插件：操作插件、OpenAPI 控制器、表单插件、后台任务
 * 优先封装：（暂无 commons 封装）
 * 原生兜底：AppCache、DistributeSessionlessCache、CacheFactory、BusinessDataServiceHelper
 * 相关 lint 规则：（暂无）
 * <p>
 * 使用场景：
 * 1. AppCache：应用级别缓存，适合存储配置、票据、状态等轻量数据；
 * 2. DistributeSessionlessCache：分布式无会话缓存，支持 TTL 自动过期，适合跨节点共享；
 * 3. loadFromCache：基础资料查询走缓存通道，减少数据库访问。
 * <p>
 * <b>注意：缓存 key 应包含足够的业务区分度（如表单标识 + 业务编码），
 * 避免不同业务场景互相覆盖。</b>
 */
public class SampleCacheUsage {
    private static final Log log = LogFactory.getLog(SampleCacheUsage.class);
    private static final int APP_CACHE_TTL_SECONDS = 600;
    private static final String MISSING_VALUE = "__MISSING__";

    // ===================================================================
    //  一、AppCache —— 应用级别缓存
    // ===================================================================

    /**
     * AppCache 是基于命名空间的应用级缓存。
     * 参数为命名空间名称，同一命名空间内共享 key 空间。
     */
    private static final IAppCache APP_CACHE = AppCache.get("kdcd_sso_ticket");

    /**
     * 场景：单点登录票据缓存。
     * 票据只能使用一次，首次解析后缓存结果，后续直接取缓存。
     */
    public String getOrCacheTicket(String ticket) {
        String cacheKey = cacheKeyForTicket(ticket);
        // 先查缓存
        String cachedValue = APP_CACHE.get(cacheKey, String.class);
        if (cachedValue != null) {
            log.info("票据解析缓存命中");
            return cachedValue;
        }

        // 缓存未命中，执行实际解析
        String resolvedValue = resolveTicket(ticket);

        // 原始票据不进入 key 或日志；共享缓存显式设置 TTL。
        APP_CACHE.put(cacheKey, resolvedValue, APP_CACHE_TTL_SECONDS);
        log.info("票据解析结果已写入应用缓存");

        return resolvedValue;
    }

    /**
     * 场景：存储临时状态（如异步操作的中间状态）。
     */
    public void cacheOperationStatus(String bizKey, String status) {
        APP_CACHE.put("operation_status:" + bizKey, status, APP_CACHE_TTL_SECONDS);
    }

    public String getOperationStatus(String bizKey) {
        return APP_CACHE.get("operation_status:" + bizKey, String.class);
    }

    // ===================================================================
    //  二、DistributeSessionlessCache —— 分布式无会话缓存（支持 TTL）
    // ===================================================================

    /**
     * 分布式缓存，跨节点共享，支持自动过期。
     * 参数为缓存区域名，同一区域内共享 key 空间。
     */
    private final DistributeSessionlessCache distCache =
            CacheFactory.getCommonCacheFactory().getDistributeSessionlessCache("kdcd_biz_cache");

    /**
     * 缓存已审核且启用的小型基础资料映射表；目标实体须具有 status、enable 字段。
     * 查询投影原样交给 QueryServiceHelper，以返回属性名作为 JSON 字段名；不自行拆分表达式。
     * id 用作外层 Map 的键，投影中的其他字段/别名不得占用 id。
     * 超过条数或字节边界时拒绝缓存，不截断业务结果；大集合应改用过滤或分页查询。
     *
     * @param formId       表单标识（如 "bcm_model"、"bos_org"）
     * @param selectFields 查询投影（如 "number,name" 或已核验的表达式及别名），无需重复选择 id
     * @param cacheKey     业务隔离标识，须包含当前应用所需的租户/数据中心及业务范围
     * @param ttlSeconds   正数有效期（秒）；源数据更新后须按同一投影 key 失效
     * @return key=id, value=查询返回字段的 JSON 对象串（不含外层 id）
     */
    public Map<String, String> getCachedModelData(
            String formId, String selectFields, String cacheKey, int ttlSeconds) {
        String namespacedKey = ModelData.cacheKey(formId, selectFields, cacheKey, ttlSeconds);

        Map<String, String> cached = distCache.getAll(namespacedKey);
        if (cached != null && !cached.isEmpty()) {
            return cached;
        }

        QFilter filter = new QFilter("status", QCP.equals, "C")
                .and(new QFilter("enable", QCP.equals, "1"));
        // 多取一行用于检查溢出，禁止把被截断的结果当成完整映射缓存。
        DynamicObjectCollection rows = QueryServiceHelper.query(
                formId, "id," + selectFields, new QFilter[]{filter}, "id", ModelData.MAX_ROWS + 1);
        Map<String, String> dataMap = ModelData.toMap(rows);
        if (!dataMap.isEmpty()) {
            distCache.put(namespacedKey, dataMap, ttlSeconds);
        }
        // 此示例不存空 Hash；不存在结果的负缓存与热点回源锁需按调用场景补齐。
        return dataMap;
    }

    /** 小型映射缓存的投影标识、字段序列化与容量边界。 */
    static final class ModelData {
        static final int MAX_ROWS = 1000;
        static final int MAX_BYTES = 1024 * 1024;

        private ModelData() {
        }

        static String cacheKey(String formId, String selectFields, String scope, int ttlSeconds) {
            requireText(formId, "formId");
            requireText(selectFields, "selectFields");
            requireText(scope, "cacheKey");
            if (ttlSeconds <= 0) {
                throw new IllegalArgumentException("ttlSeconds must be positive");
            }
            // 长度前缀避免分隔符歧义；完整投影参与摘要，字段和别名不同不能复用旧值。
            String identity = formId.length() + ":" + formId
                    + selectFields.length() + ":" + selectFields + scope.length() + ":" + scope;
            try {
                byte[] digest = MessageDigest.getInstance("SHA-256")
                        .digest(identity.getBytes(StandardCharsets.UTF_8));
                return "model_data:v2:" + Base64.getUrlEncoder().withoutPadding().encodeToString(digest);
            } catch (NoSuchAlgorithmException e) {
                throw new AssertionError("SHA-256 is unavailable", e);
            }
        }

        static Map<String, String> toMap(Iterable<DynamicObject> rows) {
            Map<String, String> values = new LinkedHashMap<>();
            long bytes = 0;
            int rowCount = 0;
            for (DynamicObject row : rows) {
                if (++rowCount > MAX_ROWS) {
                    throw new IllegalArgumentException("Model data exceeds row limit; use a filtered or paged query");
                }
                String id = row.getString("id");
                requireText(id, "row.id");
                if (values.containsKey(id)) {
                    throw new IllegalArgumentException("Model data contains duplicate id: " + id);
                }
                Map<String, Object> fields = new LinkedHashMap<>();
                for (IDataEntityProperty property : row.getDynamicObjectType().getProperties()) {
                    if (!"id".equalsIgnoreCase(property.getName())) {
                        fields.put(property.getName(), row.get(property));
                    }
                }
                String json = SerializationUtils.toJsonString(fields);
                // 统计本次写入键和值的 UTF-8 字节量；不代表 Redis 总内存占用。
                bytes += id.getBytes(StandardCharsets.UTF_8).length
                        + json.getBytes(StandardCharsets.UTF_8).length;
                if (bytes >= MAX_BYTES) {
                    throw new IllegalArgumentException("Model data exceeds byte limit; use a filtered or paged query");
                }
                values.put(id, json);
            }
            return values;
        }

        private static void requireText(String value, String name) {
            if (value == null || value.trim().isEmpty()) {
                throw new IllegalArgumentException(name + " must not be blank");
            }
        }
    }

    /**
     * 场景：缓存单个值（如用户 ID 反查）。
     *
     * @param userNumber 用户编码
     * @return 用户 ID
     */
    public Long getCachedUserId(String userNumber) {
        String cacheKey = "user_id_by_number:" + userNumber;

        // 先查缓存
        String userId = (String) distCache.get(cacheKey);
        if (MISSING_VALUE.equals(userId)) {
            return null;
        }
        if (userId != null) {
            return Long.valueOf(userId);
        }

        // 查询数据库
        DynamicObject userObj = QueryServiceHelper.queryOne(
                "bos_user", "id", new QFilter[]{new QFilter("number", QCP.equals, userNumber)});

        if (userObj == null) {
            // 短 TTL 负缓存，避免不存在编码持续穿透；不能回退成当前用户。
            distCache.put(cacheKey, MISSING_VALUE, 60);
            return null;
        } else {
            userId = userObj.getString("id");
        }

        // 写入缓存，180 秒过期
        distCache.put(cacheKey, userId, 180);

        return Long.valueOf(userId);
    }

    // ===================================================================
    //  三、loadFromCache —— 基础资料缓存查询
    // ===================================================================

    /**
     * 场景：查询基础资料时走缓存通道，减少数据库压力。
     * 适用于基础资料、辅助资料等不经常变更的实体。
     *
     * @param pk       主键
     * @param entityId 实体标识（如 "bos_org"、"bd_currency"）
     * @return 缓存中的 DynamicObject（如果缓存中没有会自动从 DB 加载并缓存）
     */
    public DynamicObject loadBaseDataFromCache(Object pk, String entityId) {
        // loadSingleFromCache：平台内置缓存通道（单条查询）
        // 首次调用从 DB 加载，后续直接从缓存返回
        return BusinessDataServiceHelper.loadSingleFromCache(pk, entityId);
    }

    /**
     * 场景：批量加载基础资料走缓存。
     * 返回 Map&lt;主键, DynamicObject&gt;。
     */
    public Map<Object, DynamicObject> loadBaseDataBatchFromCache(Object[] pks, String entityId) {
        return BusinessDataServiceHelper.loadFromCache(pks, entityId);
    }

    // ===================================================================
    //  缓存选型速查
    // ===================================================================
    //
    //  AppCache:
    //  - 应用级分布式缓存；7.0 AppCacheImpl 使用 DistributeSessionlessCache
    //  - 共享状态建议显式 TTL；无 TTL 只用于已有稳定失效机制的场景
    //  - 适合：配置项、票据、临时状态
    //  - 用法：AppCache.get("命名空间") → put/get
    //
    //  DistributeSessionlessCache:
    //  - 分布式缓存，跨节点共享（底层 Redis）
    //  - 支持 TTL 自动过期
    //  - 适合：频繁查询的映射表、用户信息、维度成员
    //  - 用法：CacheFactory...getDistributeSessionlessCache("区域") → put/get/getAll
    //
    //  loadFromCache:
    //  - 平台内置基础资料缓存通道
    //  - 自动管理缓存生命周期
    //  - 适合：基础资料、辅助资料等标准实体
    //  - 用法：BusinessDataServiceHelper.loadFromCache(pk, entityId)

    private String resolveTicket(String ticket) {
        // 模拟票据解析
        return "resolved_" + ticket;
    }

    private String cacheKeyForTicket(String ticket) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(ticket.getBytes(StandardCharsets.UTF_8));
            return "ticket:" + Base64.getUrlEncoder().withoutPadding().encodeToString(digest);
        } catch (NoSuchAlgorithmException e) {
            // SHA-256 是 Java 必须提供的算法；缺失表示运行时本身不符合平台前提，而非业务校验失败。
            throw new AssertionError("SHA-256 is unavailable", e);
        }
    }
}
