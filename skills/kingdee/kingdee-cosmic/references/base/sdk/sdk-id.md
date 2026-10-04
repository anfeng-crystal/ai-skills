# 分布式 ID (Distributed ID)

## TL;DR
- 适用：生成平台分布式唯一 ID，或临时资源的唯一名称。
- 先抓：`ID.genLongId()` / `ID.genStringId()`；实体主键遵循真实元数据类型及平台分配流程，不一律手工覆盖。
- 跳转：业务编码规则与主键生成不同，业务编号使用 `CodeRuleServiceHelper` 对应合同。
- 继续读全文：批量生成、字符串长度、转换或初始化故障。

## 核心 API

`kd.bos.id.ID`。以下签名已由实际 7.0 JAR 与官方 V7.0.1 Javadoc 核实；依赖不同版本时再核对，不擅自升级项目。

| 方法 | 返回值与用途 |
|---|---|
| `genLongId()` | `long`，生成一个 ID |
| `genLongIds(int count)` | `long[]`，生成指定数量 ID |
| `genStringId()` | `String`，生成默认编码的字符串 ID |
| `genStringIds(int count)` | `String[]`，批量字符串 ID |
| `toStringId(long id)` / `toLongId(String id)` | 默认 Base39 编码与对应解码 |
| `longTo36Radix(long id)` / `longFrom36Radix(String idOf36Radix)` | Base36 编码与对应解码 |
| `getCreateTime(long id)` / `getCreateTime(String id)` | `java.util.Date`，获取平台 ID 的大致生成时间，不能替代业务日期 |

批量方法真实存在，原示例能编译；按业务需要使用，控制单次申请量。不把未经测量的“减少锁竞争”写成性能保证，也不依赖未确认的零数/负数入参行为。

## 长度与转换

- `long` ID 最大十进制长度 19 位；数据库选能容纳该值的整型，具体列定义遵循数据库和元数据，不把 `bigint(19)` 当跨数据库 DDL。
- 默认 `genStringId()` / `toStringId(long)` 使用 Base39（`+/=0-9A-Z`）表示 **long 数值**，方法级 Javadoc 标注最大 12 个字符。是 long 编成 String，不是 String 编成 long。
- `longTo36Radix` 使用 `0-9A-Z`，方法级 Javadoc 标注最大 13 个字符，且明确**不可用作实体主键**。用于该方法允许的唯一名称场景；不要把所有字符串 ID 字段统一设为 `varchar(12)`。
- “最大长度”不是任意入参都固定宽度；本地实现未给通用转换结果补零。官方知识将常见结果简述为 12/13 位，V7.0.1 类概览中的默认 String“最大13”又与具体方法说明冲突；这里采用具体方法说明和实际编码实现的上界。
- 两种编码必须成对解码：`toStringId` 配 `toLongId`，`longTo36Radix` 配 `longFrom36Radix`。字符集部分重合不代表可以混用；不要直接解码未知来源、外部主键或任意字符串。数值趋势不等于两种编码字符串都能按文本排序保持时间顺序。

## 示例：生成与成对转换

这是服务端 API 使用示例，不会保存实体，也没有覆盖既有主键。业务代码需要使用返回的 ID；独立调用两次生成函数得到的是两个新 ID，不是同一 ID 的两种表示。

```java
import kd.bos.id.ID;

public class IdDemo {
    public void generateId() {
        long billId = ID.genLongId();
        long[] batchIds = ID.genLongIds(10);
        String traceId = ID.genStringId();
        String[] traceIds = ID.genStringIds(10);

        String encoded = ID.toStringId(billId);
        long restored = ID.toLongId(encoded);
        String base36Name = ID.longTo36Radix(billId);
        long restored36 = ID.longFrom36Radix(base36Name);
    }
}
```

示例仅经 Java 8 / 实际 7.0 依赖离线编译；没有启动 ID 服务、连接 Zookeeper 或执行数据库保存。

## 实体主键与故障边界

1. **沿用平台分配链**：先确认实体主键的真实类型及创建/保存方式。本地 7.0 保存实现会按元数据类型给空主键分配值，不能由此推出所有业务实体必须手工 `genLongId()`。已有主键不覆盖；确实需要提前分配时才使用适合该实体的已确认 API。内部 ORM 分配实现只作本地证据，不作为新的二开入口。
2. **历史与外部 ID**：导入/映射保留其既有语义；只有来源和编码明确时才转换。不能从任意 ID 推算真实创建时间，也不能以“趋势有序”承诺跨节点的严格业务顺序。
3. **初始化异常先取证**：按实际异常核对 ID 服务依赖、时钟、节点分配和协调服务状态。旧卡“种子用完就清理 Zookeeper”未有足够的目标版本恢复合同，不作为通用修复；清节点会改变共享状态，须另有具体、已授权的恢复方案。没有确认依赖配置时，不把 Redis/Zookeeper 其中任一组件异常直接等同于 ID 服务必然无法启动。

## 来源

- [苍穹分布式 ID](https://vip.kingdee.com/knowledge/318798719069836544)：官方知识，更新于 2026-07-30，未给明确版本范围；批量数组、转换接口与编码长度。表格中 `genStringIds` 中文误写为 long 数组，以 `String[]` 签名及实际 SDK 为准。
- [ID V7.0.1 Javadoc](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/id/ID.html)：具体方法、长度上界及 Base36 不作主键的限制。
- 本地实际 `bos-id-7.0.jar` / 保存链签名与字节码只确认本次依赖的调用事实，不证明所有补丁、部署或故障恢复行为。
