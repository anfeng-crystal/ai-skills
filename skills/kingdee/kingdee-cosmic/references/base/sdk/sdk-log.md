# 日志框架 (Logging Framework)

详细知识、官方来源与验证边界：[云端专题](https://chatgpt.com/space/page_f563cc1fce008191b83e9adf3c9e63a3)。

## TL;DR
- 适用：统一日志记录、级别判断和异常堆栈输出。
- 先抓：优先 `LogFactory.getLog(Class)`，避免 `System.out.println`。
- 跳转：如果继承了 Ext 插件基类，先直接用内置 `log` 对象，不必回到本页。
- 继续读全文：当你要确认参数化日志、异常记录和生产级日志建议时。

## 概述
苍穹提供 `kd.bos.logging.Log` 统一接口，支持 DEBUG、INFO、WARN、ERROR。已核本机 7.0 构件在未指定自定义日志工厂时选择 Logback；这是可配置的实现路径，不是所有版本/部署的保证。异步写入、链路字段和集中采集由目标实现及部署配置决定，不能仅凭 `Log` 接口认定已启用。

## 核心类
- **`kd.bos.logging.LogFactory`**: 获取日志对象的工厂类。
- **`kd.bos.logging.Log`**: 日志执行接口。

## 常用 API 方法
### 获取日志实例
- `LogFactory.getLog(Class<?> clazz)`: 推荐方式，根据类名获取日志对象。
- `LogFactory.getLog(String name)`: 根据标识名获取。

### 级别判断
- `isDebugEnabled()` / `isInfoEnabled()` / `isWarnEnabled()` / `isErrorEnabled()`

### 记录日志
- `debug(String message, Object... args)`
- `info(String message, Object... args)`
- `warn(String message, Object... args)` / `error(String message, Object... args)`
- `warn(String message, Throwable t)` / `error(String message, Throwable t)`，以及 `warn(Throwable)` / `error(Throwable)`：明确传递异常对象。

V7.0.1 文档把数组形式显示为 `Object[]`；本机 7.0 的上述四级数组重载带 `ACC_VARARGS`，可按 `Object...` 调用。`{}` 是已核的参数占位符，不是 `String.format` 的 `%s`。完整堆栈是否输出及采集仍依赖目标日志布局和配置。

## 示例代码
```java
import kd.bos.logging.Log;
import kd.bos.logging.LogFactory;

public abstract class LogDemo {
    // 1. 定义静态常量日志对象
    private static final Log logger = LogFactory.getLog(LogDemo.class);

    // safeBillNo 由调用方提供已脱敏、适合单行日志的业务定位信息。
    public void doWork(String safeBillNo) throws Exception {
        // 2. 级别判断也可保护有计算成本的日志参数。
        if (logger.isInfoEnabled()) {
            logger.info("开始处理单据: {}", safeBillNo);
        }

        try {
            process();
        } catch (Exception e) {
            // 3. 本层承担一次错误记录，保留异常对象并继续传播失败。
            logger.error("单据处理失败: " + safeBillNo, e);
            throw e;
        }
    }

    protected abstract void process() throws Exception;
}
```

本例不实现业务动作；子类提供 `process()`。记录日志不等于恢复业务，失败仍传给调用方。若上层已有统一错误记录，应按项目错误处理合同选择一个记录位置，避免同一异常重复记录；需要包装异常时保留原始 cause。

## 实践建议
1. **按需判断级别**：级别检查是官方推荐，尤其用于有计算成本的参数。参数化日志不会推迟 Java 参数求值；不要先做昂贵计算再期望日志级别替你省掉它。
2. **占位符写法**：推荐使用 `{}` 占位符，而不是手写字符串拼接。
3. **异常对象单独传递**：需要记录堆栈时优先使用已核的 `warn/error(String, Throwable)`；不要只记录 `e.getMessage()`，也不把任意最后一个 Object 参数一概当作异常重载。级别按错误语义选择，不机械把所有异常都记为 ERROR。
4. **只记录必要内容**：大列表和完整数据包先评估并按需选字段；官方规范禁止仅为打日志把页面/数据对象 `toJson`。保留定位所需的业务上下文，参数也先脱敏。

## 常见坑位
1. **`System.out` 滥用**：官方规范要求程序日志使用 `Log`，特殊工具除外。stdout 是否被采集由部署决定，不能宣称技术上永远无法集中收集，也不能用它替代统一日志接口。
2. **循环内输出**：避免分录/大循环逐行输出，优先汇总必要数量与失败定位；日志量和开销需按目标环境验证。
3. **敏感信息泄露**：记录日志时注意脱敏，避免将用户的密码、个人手机号等敏感信息直接打入日志。

## 依据与验证边界

- [Log V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/logging/Log.html) 与 [LogFactory V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/index.html?nav=class&module=kd.bos.logging&package=kd.bos.logging&name=LogFactory)：公开方法与占位符合同。
- [金蝶AI苍穹定制化开发规范](https://vip.kingdee.com/knowledge/498888207505798912)，2025-12-23 更新，3.11/3.12：异常处理及日志强制/推荐规则，未列精确 SDK 补丁。
- 本机 `bos-log-7.0.jar`（manifest：`hotfix_7.0.16_20250730`）确认本卡签名及所述工厂/SLF4J 委托。示例仅以实际依赖、Java 8 目标离线编译；未初始化日志系统，也未验证真实输出、异步传输、链路字段、集中采集或业务异常处理。
