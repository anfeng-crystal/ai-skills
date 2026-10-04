# 异常、错误码与多语言提示

详细知识与证据边界见 [云端异常与多语言知识](https://chatgpt.com/space/page_1eae4449e42c8191b48920230e72045e)。

## 入口与真实合同

适用：业务拒绝、系统异常包装、错误码和多语言消息；日志写法见 `sdk-log.md`，事务回滚按实际操作/事务入口处理。以下 API 以本次实际 7.0 JAR 核验，并与官方 V7.0.1 Javadoc 分开记录。

官方定制化规范推荐使用 `KDException`，允许自定义子异常。`KDException extends RuntimeException`，`KDBizException extends KDException`；这是平台异常体系，不表示所有 Java 异常天然都是其子类。工具类已有的参数/状态异常合同不需机械替换。

|入口|用途|
|---|---|
|`new ErrorCode(String code, String message)`|错误代码和默认模板，支持 String.format 格式参数；不是自动完成多语言资源绑定。|
|`new KDException(ErrorCode, Object...)`|模板与参数构成异常。|
|`new KDException(Throwable, ErrorCode, Object...)`|包装并保留原始 cause。|
|`new KDBizException(ErrorCode, Object...)` / cause-first 重载|业务拒绝，构造器均在实际 7.0 中存在。|
|`exception.getErrorCode()`|返回 ErrorCode 对象；字符串代码再取 `getCode()`。|
|`exception.getArgs()`|模板参数；不是已经格式化的消息。|

错误码在产品内保持唯一，按产品云/应用/错误语义命名。`ErrorCode.getMessage()` 是默认模板，`KDException.getMessage()` 才按参数格式化。本机 7.0 使用 `%s`，多个参数可用 `%1$s`、`%2$s`；`{0}` 不会按 MessageFormat 替换。参数类型/数量不匹配时，本机实现可能回退原模板，不能把“不抛格式异常”当作提示正确。

## 消息、cause 与入口处理

对外提示应包含业务语义及可执行的下一步；底层诊断留在 cause 和受控日志中。把 `e.getMessage()` 填进业务模板仍会把底层消息带出，换成 `KDException` 不会自动清理内容。

只捕获需要处理、转换或补偿的异常；已符合入口合同的 `KDException` 可以重抛。选择表单、操作、任务或 OpenAPI 的实际处理合同，核对谁显示、谁写日志、谁序列化错误；不能从异常类型推断一定弹出友好窗口或平台一定自动记日志。若处理后不再上抛，应记录必要原因与诊断，避免无声吞错，也避免每一层重复打印同一堆栈。

## 多语言示例：读取模板后只格式化一次

`kd.bos.dataentity.resource.ResManager` 在实际 7.0 中提供：

- `String loadKDString(String defaultValue, String key, String project, Object... args)`。
- `String getKDString(String key, String project, Object... args)`。

多语言资源名、Key 和 UTF-8 资源内容须按实际工程配置。示例在每次构造错误时取得当前语言模板；不把已解析的当前语言文本缓存为静态常量。调用 ResManager 时不传动态参数，再交异常构造器格式化一次，避免把已格式化且可能含 `%` 的文本再次作为模板。

`my-module` 是待替换的示例资源标识，不是已经存在的翻译包。`doComplexTask` 为调用方实现的业务动作；不存在的订单应由业务检查明确调用 `orderNotFound`，空编号单独使用必填错误。

```java
import kd.bos.dataentity.resource.ResManager;
import kd.bos.exception.ErrorCode;
import kd.bos.exception.KDException;
import kd.bos.exception.KDBizException;

public abstract class OrderProcessor {
    private static final String RESOURCE = "my-module";

    private static ErrorCode code(String key, String defaultTemplate) {
        String template = ResManager.loadKDString(defaultTemplate, key, RESOURCE);
        return new ErrorCode("my.module." + key, template);
    }

    public static KDBizException orderNotFound(String billNo) {
        return new KDBizException(code("orderNotFound",
                "订单【%s】不存在或已删除，请核对单据编号。"), billNo);
    }

    public void processOrder(String billNo) {
        if (billNo == null || billNo.trim().isEmpty()) {
            throw new KDBizException(code("billNoRequired", "请填写订单编号。"));
        }
        try {
            doComplexTask(billNo);
        } catch (KDException e) {
            throw e;
        } catch (Exception e) {
            throw new KDException(e, code("dataProcessError",
                    "订单处理失败，请联系管理员并提供单据编号。"));
        }
    }

    protected abstract void doComplexTask(String billNo) throws Exception;
}
```

这条路径保留错误码、当前语言模板、动态业务参数和原始 cause；只创建异常不保证真实翻译资源、外部错误配置、前端展示或接口输出已经生效。日志不得以对外消息代替完整诊断；业务逻辑判断也不要比较翻译后的提示文本。

## `ErrorCode.of` 的版本边界

官方 V7.0.1 公开五参 `of(errorCode, project, key, desc, staticResource)`，其注释限定 BOS 静态资源多语言改造场景；不能当作所有二开工程的通用入口。本机实际 7.0 JAR 中的四 String 参数重载 `of(String,String,String,String)` 已标 `@Deprecated`，未提供上述五参重载。不要直接搬另一版本重载，也不因四参可编译就作为新推荐。普通构造器的 `getLangMessage()` 在本机为 null，只能证明未通过它绑定该资源描述，不否定平台外部配置或响应层的其他本地化处理。

## 依据与验证边界

- [定制化开发规范 3.11](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=218063485690097920&id=498888207505798912&productLineId=29)，更新 2025-12-23：业务提示、cause 保留与处理/重抛。
- [多语言开发规范 3.2](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=218063485690097920&id=241181198532529920&productLineId=29&lang=zh-CN)，更新 2026-09-15：资源、占位符与静态提示语处理。
- [ErrorCode](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/exception/ErrorCode.html)、[KDException](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/exception/KDException.html) · 官方 V7.0.1 Javadoc。

最终示例用实际 7.0 最小依赖/JDK 8 离线编译。消息格式、cause 与默认资源描述已执行纯本地异常实例探针；没有运行真实资源翻译、平台日志、前端、OpenAPI 或事务业务。
