# 线程池 (Unified Thread Pool)

详细知识与证据边界见 [云端线程池知识](https://chatgpt.com/space/page_8f8f165a83b48191b414a5dc149527e3)。

## 选路

平台内异步任务使用 `kd.bos.threads.ThreadPools` 创建/提交，复用命名线程池以纳入平台生命周期管理。只恢复上下文见 [请求上下文](../../adv/request-context.md)；需要持久任务、调度、重试和完成追踪时使用相应任务机制，不能用进程内线程池承诺可靠交付。

## API 与上下文（V7.0.1 / 实际 7.0）

|能力|已核签名|说明|
|---|---|---|
|单次执行|`ThreadPools.executeOnce(String name, Runnable task)`|实际 7.0 会携带当前上下文，不因缺少 Include 字样就判为无上下文|
|固定池|`ThreadPools.newFixedThreadPool(String name, int size)`|返回 `ThreadPool`|
|缓存池|`ThreadPools.newCachedThreadPool(String name, int coreSize, int maxSize)`|返回 `ThreadPool`，明确容量|
|执行|`void ThreadPool.execute(Runnable task)`|使用提交线程的请求上下文|
|显式上下文|`void execute(Runnable task, RequestContext context)`|只传授权范围内且适用于任务的上下文|
|结果任务|`<T> Future<T> submit(Callable<T> task)`|另有 `submit(Callable<T>, RequestContext)`|
|关闭|`void ThreadPool.close()`|不继承 AutoCloseable；本地实现 shutdown 并注销名称，不等待全部任务完成|

实际 7.0 的普通 `execute` / `submit` 在提交时调用 `RequestContextCreator.createForThreadPool`，执行时恢复；复制租户、账套、用户、组织、语言等选定属性。它不是完整 Web Session、页面模型、任意 ThreadLocal 或调用方事务的传播合同。`executeIncludeRequestContext` 两个实例重载仍存在但在该 JAR 标记 Deprecated，内部委托 `execute`；`ThreadPools.executeOnceIncludeRequestContext` 也存在，不把实例重载的弃用状态推广到所有同名方法。

## 共享池与结果处理

以下完整示例只演示提交入口，线程数 `5` 是示例容量，需按业务负载选择。返回 `Future` 便于调用者记录实际成功/失败；方法返回 Future 只说明得到任务句柄，不等于业务已完成。

```java
import java.util.Objects;
import java.util.concurrent.Callable;
import java.util.concurrent.Future;
import kd.bos.threads.ThreadPool;
import kd.bos.threads.ThreadPools;

public final class ThreadDemo {
    private static final ThreadPool POOL =
            ThreadPools.newFixedThreadPool("MyBizPool", 5);

    private ThreadDemo() { }

    public static <T> Future<T> submit(Callable<T> task) {
        return POOL.submit(Objects.requireNonNull(task, "task"));
    }

    // 适合无需返回值的短任务；任务自身需有明确失败记录/上报路径。
    public static void runOnce(Runnable task) {
        ThreadPools.executeOnce("MyBizOnce", Objects.requireNonNull(task, "task"));
    }
}
```

- 要等待结果时，在合适的协调线程对 `Future.get(timeout, unit)` 处理 `ExecutionException`、`TimeoutException` 和 `InterruptedException`；中断应恢复标记或向上抛出。超时/取消不保证工作线程已停止，也不撤销已写业务数据；避免在请求线程无限等待或在同一满载池内等待其子任务。
- `execute` / `runOnce` 没有 Future，调用方外层 catch 不能承接随后任务体抛出的异常。需显式设计任务内失败记录与业务状态；不要仅在调用处记“成功”。
- 复用有明确所属生命周期的池；不要每次方法调用都创建/关闭一个新池。共享池由其管理者在停止接收新任务后统一关闭，业务调用者不随意 close。不能用 `ThreadPool` 的 try-with-resources，也不能把 close 当 awaitTermination。
- 若自定义 JDK `ExecutorService`，先核目标 `ThreadLifeCycleManager.wrapExecutorService` 适配及关闭责任，再接入平台管理；普通业务优先直接用平台工厂。使用 ThreadLocal 后在 finally remove，不依赖线程复用时自动清理兜底。

## 容量、拒绝与恢复边界

实际 7.0 固定池使用有界队列，缓存池使用 `SynchronousQueue`。高负载下默认拒绝处理可能阻塞提交线程，也可能抛异常；池已关闭时存在直接返回、不执行提交任务的实现分支。因此不能承诺“默认不会丢任务”或“调用没报错就已可靠接收”。避免并发关闭与提交，需要可靠交付时另有持久记录和可核对的处理状态。

官方指南有“100 次 / 505 秒”描述，但本地 7.0 的容量等待循环本身不递增该拒绝次数，不能推导固定等待上限。具体容量、队列和拒绝行为以目标构建和实际配置为准；不把该文章数值当接口 SLA，不为排错自动修改 MC。

上下文能恢复不代表可直接捕获活页面、可变 `DynamicObject` 或事务内未提交数据跨线程共享。按业务确定独立输入、数据重新读取时机和事务边界；提交/执行失败后先核持久状态再决定重试，避免重复业务动作。

## 依据与验证

[官方线程池指南](https://vip.kingdee.com/knowledge/318771871749696000)（更新 2026-07-30 12:37）提供生命周期、上下文和队列说明；精确签名与上下文合同对照 [V7.0.1 ThreadPool](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/threads/ThreadPool.html)、[ThreadPools](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/threads/ThreadPools.html) 及实际 `bos-framework-7.0.jar`。本卡为 Java 8 离线编译和实现核验，未运行线程池饱和、关闭竞态、上下文隔离或任务业务验收。
