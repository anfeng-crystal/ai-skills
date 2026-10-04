# 请求上下文（RequestContext）

详细知识与证据边界见 [云端请求上下文知识](https://chatgpt.com/space/page_b6cba0054c80819194c6ebd60e892564)。

## 读取入口与版本

`kd.bos.context.RequestContext` 保存当前线程绑定的用户、租户、账套、组织等信息。以下签名按实际 `bos-framework-7.0`、`bos-util-7.0` 与官方 V7.0.1 Javadoc 核对；其他版本按项目依赖确认。

- `RequestContext.get()` 读取当前绑定，可能为 `null`；它不创建身份，也不传播到任意新线程。
- `getOrCreate()` 在缺失时创建对象，不代表已登录、已补齐租户/用户或已获业务权限。
- 同步插件及平台托管任务优先使用已有上下文。后台任务 `AbstractTask.execute(RequestContext, Map)` 也有平台传入的上下文，不能笼统断言所有后台线程均没有上下文。
- 异步传播、局部绑定与恢复见 [上下文作用域](../../adv/request-context.md)；平台线程池见 [线程池](sdk-threadpool.md)。

## 常用字段

|调用|返回类型与含义|
|---|---|
|`getCurrUserId()`|`long`，当前用户 ID|
|`getUid()`|`String`，独立的 uid 字段；不作为 `getCurrUserId()` 的同义方法|
|`getUserName()`|`String`，上下文中的用户名称|
|`getTenantId()` / `getAccountId()`|`String`，租户与账套 ID|
|`getOrgId()`|`long`，当前上下文的组织 ID；不是任意单据的业务组织|
|`getLang()`|`kd.bos.lang.Lang`；需要 Java `Locale` 时从该对象调用 `getLocale()`|

7.0 的 `RequestContext` 本身没有 `getLocale()`。语言也不等于时区，日期显示另按业务时区处理。

```java
import java.util.LinkedHashMap;
import java.util.Map;
import kd.bos.context.RequestContext;
import kd.bos.lang.Lang;

public final class ContextReadExample {
    public static Map<String, Object> currentInfo() {
        RequestContext ctx = RequestContext.get();
        if (ctx == null) {
            throw new IllegalStateException("当前线程没有请求上下文");
        }
        Map<String, Object> info = new LinkedHashMap<>();
        info.put("userId", ctx.getCurrUserId());
        info.put("userName", ctx.getUserName());
        info.put("tenantId", ctx.getTenantId());
        info.put("accountId", ctx.getAccountId());
        info.put("orgId", ctx.getOrgId());
        Lang lang = ctx.getLang();
        info.put("locale", lang == null ? null : lang.getLocale());
        return info;
    }
}
```

此示例仅返回调用方所需字段，不证明用户、组织或租户值已通过业务验权。不要把修改上下文字段当作登录或授权过程。

## 复制与恢复的边界

- 官方 `copy(source)` 文档要求在新线程中调用。它复制选定字段，部分成员仍共享引用，不是深拷贝；本地 7.0 实现会保留 `traceId`，不能宣称调用 `copy` 就生成新追踪链。
- `copyAndSet(source)` 还会设置当前上下文并执行线程跟踪绑定；不要仅为清理方便与 `copy` 混用。
- 本版没有 `RequestContext.remove()`。局部替换要保存并恢复原绑定，不能在平台线程上无条件清空；`set(null)` 仅表示原绑定为空，不是所有线程状态的清理方法。

## 依据

- [RequestContext · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/context/RequestContext.html)、[Lang · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/lang/Lang.html)。
- [execute事件](https://vip.kingdee.com/knowledge/226296116516332800)，官方知识，更新于 2026-07-31；正文未标平台版本，仅支持后台任务入口说明。
