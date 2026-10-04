package kd.cd.common.snippets;

import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.dataentity.metadata.dynamicobject.DynamicProperty;
import kd.bos.entity.ExtendedDataEntity;
import kd.bos.entity.botp.plugin.AbstractConvertPlugIn;
import kd.bos.entity.botp.plugin.args.AfterConvertEventArgs;
import kd.bos.entity.botp.plugin.args.AfterCreateLinkEventArgs;
import kd.bos.entity.botp.plugin.args.AfterCreateTargetEventArgs;
import kd.bos.entity.botp.plugin.args.AfterFieldMappingEventArgs;
import kd.bos.entity.botp.plugin.args.AfterGetSourceDataEventArgs;
import kd.bos.entity.botp.runtime.ConvertConst;
import kd.bos.logging.Log;
import kd.bos.logging.LogFactory;
import kd.cd.common.util.DynamicObjectUtils;
import kd.cd.core.util.CollectionUtils;
import kd.cd.core.util.ArrayUtils;

import java.util.List;
import java.util.Map;

/**
 * 转换插件示例 —— AbstractConvertPlugIn 内部生命周期全场景。
 * <p>
 * 适用插件：转换插件（下推/选单场景）
 * 原生兜底：AbstractConvertPlugIn、ExtendedDataEntity、ConvertConst
 * 相关 lint 规则：STYLE-003、STYLE-004、STYLE-015
 * <p>
 * 生命周期方法执行顺序：
 * 1. afterGetSourceData  —— 转换执行前触发，拿到扁平化源数据行，适合源数据预校验/拦截；
 * 2. afterCreateTarget   —— 目标单创建完成后触发（字段映射前），适合自动填充分录行；
 * 3. afterFieldMapping   —— 字段映射完成后触发，事件携带目标集合，适合遍历补值/动态新增分录行；
 * 4. afterCreateLink     —— 目标单关联子实体记录源单信息后触发，适合补充关联携带数据；
 * 5. afterConvert        —— 整批转换完成后触发，可拿到全部目标单 + 源单行，适合跨单汇总/补字段/校验。
 * <p>
 * <b>注意：本文件覆盖转换插件"内部"生命周期；外部编程式下推/链路追踪请看 BotpTracePushSample。</b>
 */
public class SampleConvertPlugin extends AbstractConvertPlugIn {
    private static final Log log = LogFactory.getLog(SampleConvertPlugin.class);

    // ===================================================================
    //  一、afterGetSourceData —— 转换执行前触发，源数据预校验
    // ===================================================================

    /**
     * 特点：在字段映射和目标单创建之前触发，只有「扁平化源数据行」可用。
     * <p>
     * 可用数据：
     * - e.getSourceRows()    → 扁平化后的源数据行（分录字段以 entry.xxx 形式平铺）
     * - e.getFldProperties() → 字段属性 Map，用于从扁平行安全取值
     * <p>
     * 适合操作：源数据预校验/拦截（throw KDBizException 可直接阻断转换流程）
     * 不适合操作：修改目标单（此时目标单尚未创建）
     * <p>
     * 实战场景：支付安全校验、金额合规检查、源单状态前置校验
     */
    @Override
    public void afterGetSourceData(AfterGetSourceDataEventArgs e) {
        super.afterGetSourceData(e);

        // ── 扁平化源数据行（不是完整 DynamicObject，需要完整数据要用 id 重新 load）
        List<DynamicObject> sourceRows = e.getSourceRows();
        Map<String, DynamicProperty> fldProperties = e.getFldProperties();

        // ── 通过 fldProperties 从扁平行安全取值
        for (DynamicObject row : sourceRows) {
            Long srcId = (Long) fldProperties.get("id").getValue(row);
            // TODO 校验源单数据，不满足条件 throw new KDBizException("...") 拦截下推
        }
    }

    // ===================================================================
    //  二、afterCreateTarget —— 目标单创建后、字段映射前触发
    // ===================================================================

    /**
     * 特点：目标单 DynamicObject 已创建但字段映射尚未执行，映射字段此时为空。
     * <p>
     * 可用数据：
     * - e.getTargetExtDataEntitySet().getExtDataEntityMap().get(entityName) → 目标单列表
     * - ExtendedDataEntity.getDataEntity() → 目标单（字段值大多为空/默认值）
     * <p>
     * 适合操作：向目标单预填充分录行（查基础资料 → addNew）、设置系统字段（创建人等）
     * 不适合操作：读取映射字段值（此时尚未映射）
     * <p>
     * 实战场景：自动填充扣款项/费用项分录、预设创建人/修改人
     */
    @Override
    public void afterCreateTarget(AfterCreateTargetEventArgs e) {
        super.afterCreateTarget(e);

        String tgtEntityName = this.getTgtMainType().getName();
        List<ExtendedDataEntity> targetBills = e.getTargetExtDataEntitySet()
                .getExtDataEntityMap().get(tgtEntityName);
        if (CollectionUtils.isEmpty(targetBills)) {
            return;
        }

        for (ExtendedDataEntity targetExt : targetBills) {
            DynamicObject targetBill = targetExt.getDataEntity();
            // TODO 查询基础资料 → targetBill.getDynamicObjectCollection("entryKey").addNew()
        }
    }

    // ===================================================================
    //  三、afterFieldMapping —— 字段映射完成后，遍历目标集合补值
    // ===================================================================

    /**
     * 特点：字段映射完成后触发，目标集合可能含多张单据，需遍历处理，不能按单对映射事件理解。
     * <p>
     * 可用数据：
     * - e.getTargetExtDataEntitySet().FindByEntityKey(entityName) → 目标单数组
     * - e.getFldProperties()                                      → 源单字段属性 Map
     * - 目标单字段已完成映射赋值
     * <p>
     * 与 afterConvert 的区别：
     * - afterFieldMapping 位于字段赋值后 → 补值/动态新增分录行
     * - afterConvert 位于转换流程末尾 → 对生成的目标数据包作最终调整
     * <p>
     * 适合操作：简单字段补值、清空并重建分录行、源单行程展开为目标多行
     * <p>
     * 实战场景：字段复制补值、委托报销自动带出收款人、出差申请行程展开为多行
     */
    @Override
    public void afterFieldMapping(AfterFieldMappingEventArgs e) {
        super.afterFieldMapping(e);
        String tgtEntityName = this.getTgtMainType().getName();
        ExtendedDataEntity[] targetBills = e.getTargetExtDataEntitySet().FindByEntityKey(tgtEntityName);

        for (ExtendedDataEntity targetExt : targetBills) {
            DynamicObject targetBill = targetExt.getDataEntity();

            // TODO 补值：targetBill.set("fieldA", targetBill.get("fieldB"));
            // TODO 动态新增分录：targetBill.getDynamicObjectCollection("entry").addNew().set(...);
        }
    }

    // ===================================================================
    //  四、afterCreateLink —— 建立单据关联后触发
    // ===================================================================

    /**
     * 特点：内存中的目标单关联子实体已记录源单信息，目标数据包尚未保存入库。
     * <p>
     * 可用数据：
     * - e.getTargetExtDataEntitySet().getExtDataEntityMap().get(entityName) → 目标单列表
     * - 本次来源信息应从目标数据包读取；查库只能检查此前已保存的下推记录
     * <p>
     * 适合操作：依据当前来源补充携带数据；历史去重需另行核对已保存记录，不能据此认定本次关联已落库
     * <p>
     * 实战场景：暂估应付单多次下推时扣款项只需首次携带
     */
    @Override
    public void afterCreateLink(AfterCreateLinkEventArgs e) {
        super.afterCreateLink(e);

        String tgtEntityName = this.getTgtMainType().getName();
        List<ExtendedDataEntity> targetBills = e.getTargetExtDataEntitySet()
                .getExtDataEntityMap().get(tgtEntityName);
        if (CollectionUtils.isEmpty(targetBills)) {
            return;
        }

        for (ExtendedDataEntity targetExt : targetBills) {
            DynamicObject targetBill = targetExt.getDataEntity();
            // TODO 按本次内存来源信息补充携带数据；历史下推记录与本次未保存数据分开核对
        }
    }

    // ===================================================================
    //  五、afterConvert —— 整批转换完成后统一触发（最常用）
    // ===================================================================

    /**
     * 特点：整批转换全部完成后触发，可同时拿到全部目标单 + 对应源单行，功能最强。
     * <p>
     * 可用数据：
     * - e.getTargetExtDataEntitySet().FindByEntityKey(entityName)           → 目标单数组
     * - ExtendedDataEntity.getDataEntity()                                  → 目标单 DynamicObject
     * - ExtendedDataEntity.getValue(ConvertConst.ConvExtDataKey_SourceRows)  → 对应源单行列表
     * - e.getFldProperties()                                                → 源单字段属性 Map
     * - this.getSrcMainType().getName() / this.getTgtMainType().getName()    → 源/目标单标识
     * <p>
     * 适合操作：
     * - 基础补值：从源单行取值补充目标单字段
     * - 金额校验：校验后 throw KDBizException 拦截
     * - 分录拆分：按维度将一行拆为多行（clone → clear → addAll）
     * - 分录合并：按 groupKey 分组 + 金额汇总
     * - 外部查询填值：查映射配置/基础资料 → 批量 set
     * <p>
     * 实战场景：付款金额校验、差旅明细按人拆分、账单分录合并汇总、映射资金用途
     */
    @Override
    public void afterConvert(AfterConvertEventArgs e) {
        super.afterConvert(e);

        String tgtEntityName = this.getTgtMainType().getName();
        ExtendedDataEntity[] targetBills = e.getTargetExtDataEntitySet().FindByEntityKey(tgtEntityName);
        if (ArrayUtils.isEmpty(targetBills)) {
            return;
        }

        for (ExtendedDataEntity targetExt : targetBills) {
            DynamicObject targetBill = targetExt.getDataEntity();

            // ── 获取当前目标单对应的源单行
            @SuppressWarnings("unchecked")
            List<DynamicObject> sourceRows = (List<DynamicObject>) targetExt.getValue(
                    ConvertConst.ConvExtDataKey_SourceRows);
            if (CollectionUtils.isEmpty(sourceRows)) {
                continue;
            }

            // ── 从源单行安全取值
            Long srcBillId = DynamicObjectUtils.nullSafeGet(sourceRows.get(0), "id");

            // TODO 补值/校验/拆分/合并/映射填值
            targetBill.set("sourcebilltype", this.getSrcMainType().getName());
        }
    }

}
