# createNewData - 自定义包采纳与正式编号

来源：从 [表单插件.md](../表单插件.md#17-createnewdata) 拆出。

`createNewData(e: BizDataEventArgs)` 是提供完整自定义数据包的入口，不是保证已有数据包的默认值事件。目标7.0的 `AbstractFormDataModel.createNewData` 在没有传入新对象时先构造空事件并派发；插件返回非空 `e.getDataEntity()` 才采用并跳过内置 `newDataEntity/createDefaultEntity`，否则继续创建默认包。之后还有initializer及 `afterCreateNewData`。多个插件处理同一事件对象，后插件可以替换结果。

真正要供应自定义包时才用 `e.setDataEntity(completeDynamicObject)`；它必须覆盖目标动态类型和默认值等正式合同，不能为了避免null而随手创建空 `DynamicObject`，也不能递归调用模型新建。仅补申请人/部门/日期应保留平台默认包，移到 `afterCreateNewData(e: EventObject)`，此时从模型取最终采用的包。

## 付款申请初始化与编号保留

下例保留正式部门规则对应FIN/PUR/SAL/GEN前缀、业务日期部分、正式序号与申请部门/人/日期初始化。编号不再由本机时间戳尾4位构造：按部门选前缀输入字段，业务日历提供日期，已挂载的正式编码规则组合前缀 + YYYYMMDD + 正式序号；新单据始终保持未保存。

接入前须核 `PaymentNumberContract`：它是项目接口，不是平台API。`prefixField` 是既有元数据中真实存在、且正式规则实际读取的字段；不得凭示例新增号段或字段。`validate` 核当前ADDNEW未保存单据、有效任职/业务组织的部门来源、加载完成的基础资料对象、日期时区及业务日历，并核编码规则唯一范围、保存时机、手工改号策略和预览号处理。当前用户ID不等于部门ID，不能用未经证实的 `bos_user.dpt` 查询或裸ID给基础资料字段赋值。缺规则接入时明确报错，不以时间戳/随机数补号。

```typescript
import { AbstractBillPlugIn } from "@cosmic/bos-core/kd/bos/bill";
import { DynamicObject } from "@cosmic/bos-core/kd/bos/dataentity/entity";
import { EventObject } from "@cosmic/bos-script/java/util";

interface PaymentDefaults {
  scopeToken: string;
  department: DynamicObject;
  departmentNumber: string;
  applicant: DynamicObject;
  businessDate: Date;
  businessDay: string; // 正式业务日历的YYYYMMDD，与businessDate同一天。
}
interface PaymentNumberContract {
  // 既有编码规则实际消费的前缀字段，不是billno，必须已经存在。
  prefixField: string;
  // 核ADDNEW未保存范围、引用字段类型、有效部门、日期/时区和已挂载正式编码规则。
  // 同时核首次保存取号与手工编号策略，确保预览号不会绕过正式分配。
  validate(plugin: AbstractBillPlugIn): void;
  read(plugin: AbstractBillPlugIn): PaymentDefaults;
  // 已按字段真实PK类型无损转换，不将Long先转JS number。
  referenceKey(value: DynamicObject): string;
  // 按真实日期字段/引擎桥接读取毫秒，非日期或空值返回null；只读，不猜instanceof Date。
  dateMillis(value: unknown): number | null;
}
/** 保留平台默认包，在afterCreateNewData初始化编码规则输入；从不保存或调用取号服务。 */
function createPaymentDefaultsPlugin(contract: PaymentNumberContract): AbstractBillPlugIn {
  class ApPayApplyBillNoPlugin extends AbstractBillPlugIn {
    afterCreateNewData(e: EventObject): void {
      super.afterCreateNewData(e);
      if (contract == null || typeof contract.validate !== "function" || typeof contract.read !== "function" ||
          typeof contract.referenceKey !== "function" || typeof contract.dateMillis !== "function") {
        throw new Error("申请初始化合同缺少必要适配器");
      }
      const prefixField = contract.prefixField;
      if (typeof prefixField !== "string" || !prefixField || ["billno", "applydept", "applier", "applydate"].indexOf(prefixField) >= 0) {
        throw new Error("请指定既有编码规则的独立前缀输入字段");
      }
      contract.validate(this);
      const model = this.getModel();
      const data = model.getDataEntity(true);
      if (data == null) throw new Error("平台新建数据包尚不可用");
      const initial = contract.read(this);
      // 立即复制标量、引用身份与日期时间，不继续依赖可能复用的结果容器。
      const token = initial.scopeToken;
      const department = initial.department;
      const applicant = initial.applicant;
      const deptNumber = initial.departmentNumber;
      const day = initial.businessDay;
      const time = initial.businessDate.getTime();
      const deptKey = contract.referenceKey(department);
      const applicantKey = contract.referenceKey(applicant);
      if (typeof token !== "string" || !token || typeof deptKey !== "string" || !deptKey ||
          typeof applicantKey !== "string" || !applicantKey || typeof deptNumber !== "string" || typeof day !== "string" ||
          !/^\d{8}$/.test(day) || !Number.isFinite(time)) throw new Error("申请人、部门或业务日期合同不完整");
      const prefix = deptNumber.startsWith("FIN") ? "FIN-" : deptNumber.startsWith("PUR") ? "PUR-" :
        deptNumber.startsWith("SAL") ? "SAL-" : "GEN-";
      const date = new Date(time);
      /** 只读重核作用域及编码配置；不把后续正式号段消费当作本方法的一部分。 */
      const stable = (): void => {
        contract.validate(this);
        const now = contract.read(this);
        if (contract.prefixField !== prefixField || model.getDataEntity(true) !== data ||
            now.scopeToken !== token || now.departmentNumber !== deptNumber || now.businessDay !== day ||
            now.businessDate.getTime() !== time || contract.referenceKey(now.department) !== deptKey ||
            contract.referenceKey(now.applicant) !== applicantKey || contract.referenceKey(department) !== deptKey ||
            contract.referenceKey(applicant) !== applicantKey) throw new Error("初始化期间申请范围或编码配置变化");
      };
      const equalRef = (actual: unknown, key: string): boolean =>
        actual instanceof DynamicObject && contract.referenceKey(actual) === key;
      const equalDate = (actual: unknown): boolean => contract.dateMillis(actual) === time;
      const plan = [
        {key: "applydept", value: department as unknown, same: (v: unknown) => equalRef(v, deptKey)},
        {key: "applier", value: applicant as unknown, same: (v: unknown) => equalRef(v, applicantKey)},
        {key: "applydate", value: date as unknown, same: equalDate},
        {key: prefixField, value: prefix as unknown, same: (v: unknown) => v === prefix}
      ];
      stable();
      // 先完整检查，不覆盖平台、外部供包或前序插件已填入的不同值。
      for (const item of plan) {
        const value = model.getValue(item.key);
        if (value != null && value !== "" && !item.same(value)) throw new Error("已有申请默认值冲突：" + item.key);
      }
      for (const item of plan) {
        stable();
        const value = model.getValue(item.key);
        if (!item.same(value)) {
          if (value != null && value !== "") throw new Error("申请默认值已变化：" + item.key);
          model.setValue(item.key, item.value);
        }
      }
      stable();
      for (const item of plan) {
        if (!item.same(model.getValue(item.key))) throw new Error("申请默认值未被模型采纳：" + item.key);
      }
      // billno保持平台当前值；前缀、业务日期及正式序号由已挂载编码规则组合。
    }
  }
  return new ApPayApplyBillNoPlugin();
}
export { createPaymentDefaultsPlugin };
```

项目实现合同后创建并导出 `plugin = createPaymentDefaultsPlugin(projectContract)`。`scopeToken` 覆盖当前用户、业务组织、有效部门、业务日历、规则版本与唯一范围；引用主键须无损取值。前序默认值与计划不同会在写前报冲突，已有一致值保留。日期构造使用已确认的ScriptDate/Date入口，但模型读回未证明总是全局Date实例；`dateMillis` 必须按真实字段桥接只读识别，不以 `instanceof Date` 拒绝同一日期的Java包装值。业务日期由合同提供；正则仅查格式，真实日期合法性及与日期对象同日仍由日历合同核验。初始化中途失败可能部分写入，不能宣称事务回滚。

## 真实编号消费时点

目标7.0 `AbstractCodeRulePlugin.afterCreateNewData` 先缓存新建包；绑定阶段按规则的 `isAddView` 等条件调用 `readNumber` 显示预读编号，不等于所有规则都在新建时分配正式号。对应声明说明预读不占流水且不支持不允许断号的规则；不要把预览号称为已保留的唯一正式号。

首次保存等正式操作按已挂载编码插件执行：实际 `CodeRuleOp.onAddValidators` 调用 `generateNumber`，其 `beginOperationTransaction` 覆写为空，不能套父类方法就声称取号一定在保存事务内。具体渠道、手工改号、来自数据库标记等会影响是否重新生成；正式唯一性/号段与失败回收由现有编码规则负责，不能保证无跳号或取号和保存原子。本例不直接调用编号服务，不提前保存；真实平台验收需确认最终保存号、失败后行为及多插件顺序。

依据：[官方createNewData事件](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=238600539112877056&id=222733821030797568&type=Knowledge&productLineId=29)（2024-04-17 19:47，未标完整版本范围；说明供包跳过内置创建），以及实际7.0数据模型和编码插件消费者。没有执行真实取号或保存。
