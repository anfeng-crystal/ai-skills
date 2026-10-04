# 字符串、日期、集合与 JSON 工具

详细知识与证据边界见 [云端通用工具知识](https://chatgpt.com/space/page_db09e88edfc08191a9924a1fb9882e2a)。

## 入口与版本

按具体数据类型选择已核实的 SDK 或 JDK API，不把同名工具类视为可互换。以下平台方法以实际 `bos-dataentity-7.0`、`bos-util-7.0` 和官方 V7.0.1 Javadoc 互核；日期与分批示例使用 JDK 8。

|能力|可用入口|边界|
|---|---|---|
|字符串|`kd.bos.dataentity.utils.StringUtils`：`isBlank(CharSequence)`、`isNotBlank(CharSequence)`、`equals(CharSequence, CharSequence)`、`join(Iterable<?>, String)`|前三者返回 `boolean`，join 返回 `String`。字符串判空不是集合判空；其 `isBlank(Object)` 对 Iterable/Map 不以集合大小判断。|
|集合判空|`kd.bos.util.CollectionUtils.isEmpty(Collection<?>)` / `isNotEmpty(Collection<?>)`|均返回 `boolean`，null/空集合由 isEmpty 判 true。实际 7.0 此类没有 `partition`。|
|分批|JDK `subList` 配合 `new ArrayList<>(...)`|为每批复制容器，避免直接传递源列表视图；不是事务、重试或去重机制。|
|日期/时点|`LocalDate`、`DateTimeFormatter`、`ZoneId`|先区分自然日与带时区时点；格式串不决定业务时区。|
|JSON|`kd.bos.dataentity.serialization.SerializationUtils`：`String toJsonString(Object)`、`<T> T fromJsonString(String, Class<?>)`|按数据类型和序列化合同使用；不能保证任意对象、null 字段和泛型集合无损往返。|

本地 7.0 未找到旧卡的 `kd.bos.dataentity.utils.CollectionUtils` / `DateUtils`。不要换成其他业务包中的同名类来猜签名；日期格式化、解析和加天仍可用下面的 JDK 路径完成。

## 可编译示例

调用方实现 `doBatchUpdate` 的业务动作；遍历期间不得修改源 `ids`。分批只复制列表容器，不深拷贝元素。日期方法要求非 null 的日期、文本与明确的业务时区；解析失败应交调用方按输入合同处理。

```java
import kd.bos.dataentity.utils.StringUtils;
import kd.bos.util.CollectionUtils;
import kd.bos.dataentity.serialization.SerializationUtils;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;
import java.util.Date;
import java.time.LocalDate;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;

public abstract class UtilsDemo {
    public void processData(String input, List<Long> ids) {
        if (StringUtils.isBlank(input) || CollectionUtils.isEmpty(ids)) {
            return;
        }
        for (int from = 0; from < ids.size();) {
            int to = from + Math.min(100, ids.size() - from);
            List<Long> batch = new ArrayList<Long>(ids.subList(from, to));
            doBatchUpdate(batch);
            from = to;
        }
    }
    protected abstract void doBatchUpdate(List<Long> batch);

    public String joinIds(List<Long> ids) {
        return StringUtils.join(ids, ",");
    }
    public boolean sameText(String left, String right) {
        return StringUtils.equals(left, right);
    }
    public String formatInstant(Date value, ZoneId businessZone) {
        return DateTimeFormatter.ofPattern("uuuu-MM-dd HH:mm:ss", Locale.ROOT)
            .withZone(businessZone).format(value.toInstant());
    }
    public LocalDate parseAndAddDays(String dateText, long days) {
        return LocalDate.parse(dateText, DateTimeFormatter.ISO_LOCAL_DATE).plusDays(days);
    }
    public String writeJson(Object value) {
        return SerializationUtils.toJsonString(value);
    }
    public <T> T readJson(String json, Class<T> type) {
        return SerializationUtils.<T>fromJsonString(json, type);
    }
}
```

`parseAndAddDays` 接受 ISO 日期并返回自然日；不是解析任意日期格式的通用函数。需要由带时间文本生成 `Date` 时，再明确格式、时区和夏令时歧义策略，不能默认服务器时区。官方打印时区知识也指出系统时间字段与登录用户时区曾有差异，单靠统一格式化方法不能解决。

## JSON 的实际边界

实际 7.0 的普通 `toJsonString` / `fromJsonString` 路径使用 Jackson；另有 `toJSONStringForTS` 路径使用 FastJson，不能概括整类“基于 FastJson”。默认单参序列化路径配置了忽略 null 值，解析异常也可能抛出运行时异常；接口要求保留 null、精确金额或日期格式时，按目标重载和 DTO 合同核验真实样本。

上述 `readJson` 是为调用方提供 `Class<T>` 类型参数的包装，不改变平台原方法的 `Class<?>` 签名。嵌套泛型集合、DynamicObject 元数据还原不应仅凭一个 `Class` 推定完整恢复。KingScript 的 JS 原生对象用其 JSON 能力；Java 对象与 JS 对象混用时转 [KingScript Skill](../../../../kingdee-kingscript/SKILL.md) 核对，不把 Java 工具当所有对象通用的序列化器。

## 依据

- [StringUtils · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/dataentity/utils/StringUtils.html)、[CollectionUtils · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/util/CollectionUtils.html)、[SerializationUtils · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/dataentity/serialization/SerializationUtils.html)。
- [如何实现根据登录人的时区去打印时间](https://vip.kingdee.com/knowledge/654031297895087104)，更新 2026-07-30；该打印问题正文标明 7.0.03 修复，不外推为所有日期 API 的版本说明。
- [序列化问题](https://vip.kingdee.com/knowledge/720680637639809280)，更新 2026-07-30；无版本、KingScript 语境，仅支持 Java/JS 对象来源边界。

示例仅离线编译；尚未执行平台 JSON 运行兼容、日期业务验收或批更新。
