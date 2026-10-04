# 分布式锁 (Distributed Lock)

## TL;DR
- 适用：跨实例并发互斥，需要排他处理共享资源时。
- 先抓：`DLock.tryLock(long timeoutMillis)` 的等待单位是毫秒；仅获得锁后执行受保护业务，并在 `finally` 释放。
- 跳转：单据编辑互斥通常使用[网控](sdk-network-control.md)。
- 继续读全文：锁选型、等待时间、嵌套调用或故障恢复问题。

## 核心 API 与边界

`kd.bos.dlock.DLock` 的以下签名由实际 7.0 依赖与 V7.0.1 Javadoc 核实；用于其他目标版本前仍核对目标依赖。

| API | 合同 |
|---|---|
| `DLock.create(String key[, String desc])` | 创建不可重入锁对象；创建不等于已加锁。方括号表示两个独立重载 |
| `DLock.createReentrant(String key[, String desc])` | 创建可重入锁对象，官方明确重入仅限本 JVM；不能据此保证跨 RPC 调用可重入 |
| `void lock()` | 一直等待，直到获得锁；没有返回锁对象 |
| `boolean tryLock()` | 不等待，返回是否获得锁 |
| `boolean tryLock(long timeoutMillis)` | 最多等待指定毫秒数，获得锁返回 `true`，否则 `false` |
| `void unlock()` | 释放锁；放在成功加锁后的 `finally` 中 |

这里没有 JDK `Lock.tryLock(long, TimeUnit)` 重载，也没有声明抛出 `InterruptedException`。不能照搬 JDK 锁的捕获代码；未声明受检中断异常不等于 SDK 保证可中断等待。`DLock` 接口继承 `AutoCloseable`，但不能把返回 `void` 的 `lock()` 放入资源变量赋值。

`tryLock(5000L)` 限制的是**获取锁的等待时间**，不是业务执行上限，也不是持锁 5 秒后自动释放。官方知识说明锁没有默认超时时间，不能依赖自动到期代替正常释放。

## 示例：等待失败显式返回错误

`businessId` 是已确认的业务主键；所有争用同一资源的调用必须构造同一个 key。`business` 是需要互斥的业务动作，不能在未获锁时继续执行。

```java
import kd.bos.dlock.DLock;
import kd.bos.exception.KDBizException;

public class LockDemo {
    public void executeWithLock(String businessId, Runnable business) {
        DLock lock = DLock.create("my_module/order/" + businessId, "订单并发处理");
        if (!lock.tryLock(5000L)) {
            throw new KDBizException("获取锁超时，请稍后重试");
        }
        try {
            business.run();
        } finally {
            lock.unlock();
        }
    }
}
```

异常向调用方传播；不在捕获异常后静默返回成功。此例已用实际 7.0 依赖及 Java 8 离线编译，未执行分布式争用、网络中断或节点故障试验。

## 选型与排查

- 根据调用链决定是否需要同 JVM 重入。不可重入锁不要在已持有同一 key 时再次申请；改成可重入也不能解决跨节点循环等待或多个锁顺序相反的问题。
- key 可用 `模块/业务类型/主键`；不要给每次请求生成随机 key，否则请求间无法互斥。控制受保护范围与等待时间，避免长期占用服务线程。
- 忘记释放与节点宕机分开判断。故障恢复取决于目标版本、锁后端、会话/注册中心状态等；不能承诺所有部署在固定“约 5 分钟”后释放。先核当前锁持有者、等待线程和服务存活状态。
- 锁慢时可按官方诊断资料联合查看 Monitor 组件测速、线程等待和 Zookeeper IO；不能仅凭慢调用判定根因。独立 Zookeeper、内存存储、切换模式或手工清锁属于具体运维方案，按已确认环境与授权处理，不把文章中的示例配置直接套到共用服务。

## 来源与适用范围

- [分布式锁介绍](https://vip.kingdee.com/knowledge/318795574499699968)：官方知识，更新于 2026-07-30；无明确版本范围，支持基本使用与无默认超时说明。
- [DLock V7.0.1 Javadoc](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/dlock/DLock.html)：方法签名、毫秒参数与本 JVM 重入范围；示例另经本地实际 7.0 JAR 编译，不外推全部补丁或运行行为。
- [分布式锁缓慢诊断](https://vip.kingdee.com/knowledge/446617578367152640)：官方知识，更新于 2023-05-17；诊断参考和特定部署方案，不是通用性能或故障恢复 SLA。
