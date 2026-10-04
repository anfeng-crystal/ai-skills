# 异步上下文与局部恢复

详细知识与证据边界见 [云端请求上下文知识](https://chatgpt.com/space/page_b6cba0054c80819194c6ebd60e892564)。

## 选择入口

只读取用户、租户、语言时看 [基础上下文](../base/sdk/sdk-request-context.md)。已有平台插件、调度或消息入口先沿用其上下文合同；裸 `ThreadLocal` 不会自动传播，不能据此否定平台线程池、调度及消息框架已提供的建立和恢复逻辑。

优先使用 [平台线程池](../base/sdk/sdk-threadpool.md)。实际 7.0 普通 `execute` / `submit` 已复制选定请求字段，无需一律切到带 `IncludeRequestContext` 的方法。请求上下文复制不等于继承 Web Session、数据库事务或取得额外权限。

## 非托管执行入口的局部作用域

仅当已核实入口需要手动绑定、来源上下文有效且身份范围已获授权时，才使用局部替换。以下示例按本地 `bos-framework-7.0` 编译核对：由调用方在**目标工作线程中**调用，`source` 来自已建立的上下文；不以手填用户 ID 构造登录身份。

```java
import java.util.Objects;
import kd.bos.context.RequestContext;

public final class ContextScopeExample {
    public static void runWithContext(RequestContext source, Runnable business) {
        Objects.requireNonNull(source, "source");
        Objects.requireNonNull(business, "business");
        RequestContext previous = RequestContext.get();
        try {
            // 官方 copy 文档要求在新线程中调用，勿在提交线程预先复制。
            RequestContext.set(RequestContext.copy(source));
            business.run();
        } finally {
            // 恢复进入此作用域之前的绑定，previous 允许为 null。
            RequestContext.set(previous);
        }
    }
}
```

调用方应保证来源在任务使用期间不被并发修改；每个任务建立自己的副本，不把可变副本跨任务共享。`copy` 只复制选定字段，部分引用仍共享，不能据此保证所有嵌套对象线程安全。手动创建/复制也受目标环境的安全模式及入口约束；编译通过不替代该环境的运行验证。

`finally` 恢复的是 `RequestContext` 绑定。实际 7.0 的 `set(null)` 可还原原来无绑定的状态，但不是 `ThreadLocal.remove()`，也不清理所有 MDC、线程跟踪或事务状态。不要宣称此示例完成整个 Web 请求生命周期；若框架有自己的清理合同，应由对应框架完成。`RequestContext` 不实现 `AutoCloseable`，本版也没有可直接调用的通用 `setup()` / `restore()` / `close()` 组合。

## 已有项目的 Guard 扩展

旧示例中的 `kd.cd.common.concurrent.RequestContextUtils`、`switchUser`、`switchContext(Map)` 与 `Guard` 未在本次本地平台 7.0 依赖中确认，不能作为每个苍穹工程均自带的 API。若项目确实引入此封装，先读其源码/依赖，核对切换、异常时恢复、嵌套作用域以及参数键和类型，再沿用项目已验证的 Guard 路径。不要猜 `userId`、`locale` 等字符串键，也不要把同名调度内部工具替换进来。

涉及用户切换、租户/账套设置或自定义参数时，还需核实身份与组织一致性；改一个 ID 不会自动补齐完整用户环境，`QFilter` 也不因采用 Guard 就自动成为权限校验。反射私有字段的封装受版本变化影响，不能保证“100%恢复”。

## 依据与验证边界

[RequestContext · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/context/RequestContext.html) 的 `copy` 时机与本地 `bos-framework-7.0` 的 `get/set/copy` 签名、实现互核；示例仅离线编译。尚未验证目标环境的安全配置、异步调度、租户权限、异常恢复和日志链行为。
