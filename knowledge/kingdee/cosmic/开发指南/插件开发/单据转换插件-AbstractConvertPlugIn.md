# 单据转换插件 - AbstractConvertPlugIn

> 来源: 基于平台API和社区资料整理
> 日期: 2026-04-12
> 标签: 单据转换, AbstractConvertPlugIn, 上下游, 推式生成, 拉式生成

---

## 摘要
单据转换插件（AbstractConvertPlugIn）用于在苍穹平台单据推式/拉式生成过程中注入自定义业务逻辑，包括字段映射、数据过滤、数据校验和特殊计算。配合反写规则可实现完整的上下游单据联动。

## 适用版本
- 金蝶云苍穹 V5.0+

## 核心概念

### 单据转换体系

| 概念 | 说明 |
|------|------|
| 转换规则 | 定义源单到目标单的字段映射关系 |
| 转换插件 | 在转换过程中注入自定义逻辑（AbstractConvertPlugIn） |
| 反写规则 | 定义目标单保存后如何更新源单字段 |
| 反写插件 | 在反写过程中注入自定义逻辑 |

### 转换方式

| 方式 | 触发场景 | 说明 |
|------|----------|------|
| 推式生成 | 源单列表点击"下推" | 从源单主动推送到目标单 |
| 拉式生成 | 目标单点击"选单" | 从目标单主动拉取源单数据 |

### 插件生命周期

```
转换流程：
1. beforeGetSourceData    → 获取源单数据前
2. afterGetSourceData     → 获取源单数据后
3. beforeFieldMapping     → 字段映射前
4. afterFieldMapping      → 字段映射后
5. afterConvert           → 转换完成后
```

## 详细内容

### 一、插件基类

```java
package kd.bos.entity.botp.plugin;

/**
 * 单据转换插件基类
 * 所有转换插件需继承此类
 */
public abstract class AbstractConvertPlugIn {
    // 获取源单数据前
    public void beforeGetSourceData(BeforeGetSourceDataEventArgs e) {}
    // 获取源单数据后
    public void afterGetSourceData(AfterGetSourceDataEventArgs e) {}
    // 字段映射前
    public void beforeFieldMapping(BeforeFieldMappingEventArgs e) {}
    // 字段映射后
    public void afterFieldMapping(AfterFieldMappingEventArgs e) {}
    // 转换完成后（最常用）
    public void afterConvert(AfterConvertEventArgs e) {}
}
```

### 二、常用场景实现

#### 2.1 转换前过滤源单数据

```java
/**
 * 在源单数据获取前添加过滤条件
 * 场景：只允许特定状态的源单进行转换
 */
@Override
public void beforeGetSourceData(BeforeGetSourceDataEventArgs e) {
    // 添加额外的过滤条件
    List<QFilter> filters = e.getQFilters();
    // 只允许已审核的单据参与转换
    filters.add(new QFilter("billstatus", QCP.equals, "C"));
}
```

#### 2.2 转换后修改目标单数据

```java
/**
 * 转换完成后，修改目标单据数据
 * 场景：根据源单信息计算目标单的特殊字段
 */
@Override
public void afterConvert(AfterConvertEventArgs e) {
    // 获取目标单数据
    String targetEntityNumber = this.getTgtMainType().getName();
    ExtendedDataEntity[] targetBills = e.getTargetExtDataEntitySet()
        .FindByEntityKey(targetEntityNumber);

    for (ExtendedDataEntity targetBill : targetBills) {
        DynamicObject dataEntity = targetBill.getDataEntity();

        // 设置目标单据的自定义字段
        dataEntity.set("custom_field", "转换生成");
        dataEntity.set("convert_date", new Date());

        // 处理分录
        DynamicObjectCollection entries = dataEntity.getDynamicObjectCollection("entryentity");
        BigDecimal totalAmount = BigDecimal.ZERO;
        for (DynamicObject entry : entries) {
            BigDecimal qty = entry.getBigDecimal("qty");
            BigDecimal price = entry.getBigDecimal("price");
            BigDecimal amount = qty.multiply(price);
            entry.set("amount", amount);
            totalAmount = totalAmount.add(amount);
        }

        // 设置单据头汇总金额
        dataEntity.set("totalamount", totalAmount);
    }
}
```

#### 2.3 字段映射后补充携带

```java
/**
 * 字段映射完成后，从源单携带额外字段
 */
@Override
public void afterFieldMapping(AfterFieldMappingEventArgs e) {
    // 获取源单和目标单的映射关系
    // 可在此处理标准映射规则无法满足的特殊携带需求
}
```

### 三、转换规则与反写规则管理

#### 3.1 转换规则配置路径

【开发平台】→ 单据设计 → 转换规则

#### 3.2 反写规则

反写用于目标单据保存/审核后自动更新源单据字段（如已下推数量、关闭状态等）。

#### 3.3 开发责任归属

| 内容 | 归属应用 |
|------|----------|
| 转换规则 | 源单所在应用 |
| 转换插件 | 源单所在应用 |
| 反写规则 | 目标单所在应用 |
| 反写插件 | 目标单所在应用 |

> 推荐：转换规则、转换插件、反写规则、反写插件的开发，统一由源应用开发负责。

### 四、插件注册

1. 进入【开发平台】→ 对应单据 → 转换规则列表
2. 选择对应的转换规则
3. 在插件配置中填写转换插件的完整类名

## 注意事项

1. **性能**：转换插件中避免循环查询数据库，应批量获取后在内存中处理
2. **事务**：转换过程在同一事务中，插件异常会导致整个转换回滚
3. **字段访问**：在 `afterConvert` 中修改目标单据字段前，确认字段标识正确
4. **跨应用**：跨应用的转换规则和插件工程应放在源单应用中
5. **状态判断**：始终检查源单状态，只允许合法状态的单据参与转换

## 相关链接
- [苍穹定制化开发规范-插件工程归属](https://vip.kingdee.com/knowledge/498888207505798912)
- [单据转换规则配置](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248)
