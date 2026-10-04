<a id="closedcallback---子页面关闭回调事件"></a>

# closedCallBack - 供应商选择的返回合同与回填

## 事件与选择页面

`closedCallBack(e: ClosedCallBackEvent): void` 属于 `ICloseCallBack`；`getActionId()` 用于路由，`getReturnData()` 的本地 TypeScript 声明为 `any`（Java 为 `Object`），具体类型由子页决定。标准基础资料列表返回 `ListSelectedRowCollection`，行主键使用 `ListSelectedRow.getPrimaryKeyValue()`，不能在返回集合上调用 `getPkValue()`。自定义子页可返回其他协议，不能强行套用此类型。确认框使用 `MessageBoxClosedEvent`，不是这个事件。

打开标准列表使用 `ListShowParameter`，分别设置列表页面formId、供应商业务formId和lookup模式；本地构造默认不是lookup且允许多选，须显式配置。普通 `FormShowParameter.setFormId("bd_supplier")` 不保证打开选择列表。保留默认权限验证，不调用 `setHasRight(true)`：该参数在目标声明中表示“已验权”，会免除再次验权。

## 保留的采购回填能力

保留工具栏按钮接线、弹窗、回调路由、供应商主键及名称、联系人、电话、地址、开户银行和账号回填。单选写单头；需要多选时，下面同一核心可逐供应商创建分录并使用 `createNewEntryRow` 返回的实际行索引，不把列表rowKey或选中序号当目标行号。

项目必须核实列表页面和业务formId、实体、字段、默认联系人/地址/银行选择规则，以及组织、分配、状态、版本、可用性和权限范围。`listScope` 用于列表限制，`detailScope` 用于回调时重新校验，两者不能互相替代；SQL查询helper不自动等于页面授权。详情若是分录展开，必须先按真实默认行规则收敛；`queryOne` 只拿拉平后的首行，不证明唯一默认项。此例使用top2检查唯一性，0行或多行都停止，避免任取第一条。

`listenerControl` 是实际承载子项点击的ISuportClick控件（如工具栏），`button` 是事件itemKey，两者分别配置；不能把任意工具栏项标识当getControl的控件标识。`validate` 负责在打开及回填前检查真实字段映射和当前页面业务是否允许修改。`samePrimaryKey` 按真实主键类型比较，不经JS Number转换大Long。`referenceMatches` 需检查模型中基础资料引用确实加载到选中主键，不能把setValue没抛异常当加载成功。没有实际元数据时不提供猜测默认配置；项目核实后导出工厂返回的实例。

```typescript
import { AbstractBillPlugIn } from "@cosmic/bos-core/kd/bos/bill";
import { ListShowParameter } from "@cosmic/bos-core/kd/bos/list";
import { ListSelectedRow, ListSelectedRowCollection } from "@cosmic/bos-core/kd/bos/entity/datamodel";
import { CloseCallBack, ShowType } from "@cosmic/bos-core/kd/bos/form";
import { ClosedCallBackEvent } from "@cosmic/bos-core/kd/bos/form/events";
import { ItemClickEvent } from "@cosmic/bos-core/kd/bos/form/control/events";
import { QueryServiceHelper } from "@cosmic/bos-core/kd/bos/servicehelper";
import { QFilter } from "@cosmic/bos-core/kd/bos/orm/query";

interface TextMapping { source: string; target: string; }
/** clearFlag为真实Java方法的局部投影；目标TS声明未导出该成员，桥接须另验。 */
interface ClearSelection { isClearFlag(): boolean; }
interface SupplierFillContract {
  listenerControl: string;
  button: string;
  actionId: string;
  listFormId: string;
  supplierFormId: string;
  entity: string;
  primaryKey: string;
  name: string;
  supplierTarget: string;
  entryKey: string | null;
  contact: TextMapping;
  phone: TextMapping;
  address: TextMapping;
  bankName: TextMapping;
  bankAccount: TextMapping;
  validate(plugin: AbstractBillPlugIn): void;
  listScope(plugin: AbstractBillPlugIn): QFilter | null;
  detailScope(plugin: AbstractBillPlugIn, id: unknown): QFilter[] | null;
  samePrimaryKey(a: unknown, b: unknown): boolean;
  referenceMatches(value: unknown, selectedId: unknown): boolean;
  report(message: string): void;
}

/** 标准列表选择：先校验全部详情，再回填；不保存、不免除权限检查。 */
function createSupplierFillPlugin(c: SupplierFillContract): AbstractBillPlugIn {
  const mappings = [c.contact, c.phone, c.address, c.bankName, c.bankAccount];
  const select = [c.primaryKey, c.name, ...mappings.map(m => m.source)].join(",");
  return new class extends AbstractBillPlugIn {
    registerListener(e: $.java.util.EventObject): void {
      super.registerListener(e);
      this.addItemClickListeners(c.listenerControl);
    }
    itemClick(e: ItemClickEvent): void {
      super.itemClick(e);
      if (e.getItemKey() !== c.button) return;
      c.validate(this);
      const scope = c.listScope(this);
      if (scope == null) { c.report("供应商选择范围未就绪"); return; }
      const p = new ListShowParameter();
      p.setFormId(c.listFormId);
      p.setBillFormId(c.supplierFormId);
      p.setLookUp(true);
      p.setMultiSelect(c.entryKey != null);
      p.getListFilterParameter().setFilter(scope);
      p.getOpenStyle().setShowType(ShowType.Modal);
      p.setCloseCallBack(new CloseCallBack(this, c.actionId));
      this.getView().showForm(p);
    }
    closedCallBack(e: ClosedCallBackEvent): void {
      super.closedCallBack(e);
      if (e.getActionId() !== c.actionId) return;
      const raw: unknown = e.getReturnData();
      if (raw == null) return;
      if (!(raw instanceof ListSelectedRowCollection)) {
        c.report("供应商选择返回类型不匹配"); return;
      }
      if (raw.size() === 0) return;
      const clear = raw as unknown as ClearSelection;
      if (typeof clear.isClearFlag !== "function") throw new Error("选择清空标志的Java桥接未确认");
      // 取消、空结果及显式清空均不修改旧值；若业务要清空，另设清空按钮协议。
      if (clear.isClearFlag()) return;
      if (c.entryKey == null && raw.size() !== 1) {
        c.report("单头供应商只允许选择一条"); return;
      }
      c.validate(this);
      const plans: { id: unknown; name: string; values: (string | null)[] }[] = [];
      for (let i = 0; i < raw.size(); i++) {
        const selected = raw.get(i) as ListSelectedRow;
        if (!(selected instanceof ListSelectedRow)) throw new Error("选择行类型不匹配");
        const id: unknown = selected.getPrimaryKeyValue();
        if (id == null) { c.report("供应商主键缺失"); return; }
        if (plans.some(plan => c.samePrimaryKey(plan.id, id))) continue;
        const scope = c.detailScope(this, id);
        if (scope == null) { c.report("供应商详情范围未就绪"); return; }
        const data = QueryServiceHelper.query(c.entity, select,
          [new QFilter(c.primaryKey, "=", id), ...scope], "", 2);
        if (data == null || data.size() !== 1) {
          c.report("供应商或默认联系/银行信息未确定唯一结果"); return;
        }
        const found = data.get(0);
        if (!c.samePrimaryKey(found.get(c.primaryKey), id)) throw new Error("供应商主键不一致");
        const values = mappings.map(m => {
          const value: unknown = found.get(m.source);
          if (value != null && typeof value !== "string") throw new Error("供应商联系字段不是约定文本类型");
          return value == null ? null : value;
        });
        const name = found.get(c.name);
        plans.push({ id, name: name == null ? "" : String(name), values });
      }
      // 查询/映射全部成功后才开始写模型；字段null显式清空，避免沿用旧供应商的联系信息。
      const model = this.getModel();
      let completed = 0;
      for (const plan of plans) {
        const row = c.entryKey == null ? null : model.createNewEntryRow(c.entryKey);
        if (c.entryKey != null && (typeof row !== "number" || !Number.isInteger(row) || row < 0)) {
          throw new Error("创建供应商分录失败");
        }
        if (row == null) model.setValue(c.supplierTarget, plan.id);
        else model.setValue(c.supplierTarget, plan.id, row);
        const reference = row == null ? model.getValue(c.supplierTarget) : model.getValue(c.supplierTarget, row);
        if (!c.referenceMatches(reference, plan.id)) throw new Error("供应商引用未加载，需核查部分回填");
        for (let i = 0; i < mappings.length; i++) {
          if (row == null) model.setValue(mappings[i].target, plan.values[i]);
          else model.setValue(mappings[i].target, plan.values[i], row);
        }
        completed++;
      }
      c.report("已回填" + completed + "个供应商的联系信息" +
        (completed === 1 ? "【" + plans[0].name + "】" : "") + "，请核实后保存");
    }
  }();
}

export { createSupplierFillPlugin };
```

## 取消、错误与实际验收

单选、空结果、取消、多选超限、未知类型分别处理；清空标志不代表用户选择了某个供应商。`isClearFlag` 的Java存在不等于脚本声明或桥接已开放，局部投影与 `instanceof` 必须在目标运行时验证。`super.closedCallBack` 在目标表单父类为空，不承担返回值解析。

回填前查询失败不改原供应商；已开始回填后，规则、基础资料加载或字段写入仍可能失败，不能报告全批成功，也不能自动重试多选追加以免重复行。模型操作不是跨字段事务；应核查已创建行/已写字段后按实际业务恢复。真实页面还须验取消、清空、单/多选、无默认项、多默认项、组织/权限限制、供应商变更后的空字段、客户端刷新和最终保存；此核心只更新模型，没有主动保存。每次用户操作只打开一个选择窗口，重复回调或并行弹窗若可能发生，应由页面缓存的请求标识协议去重。

依据：[官方KingScript表单插件选择示例](https://vip.kingdee.com/knowledge/720676450449495552)及目标标准列表返回消费者、实际 `ListShowParameter/ListSelectedRowCollection` 声明；官方片段中的 `setHasRight(true)` 不应用于尚未验权的入口。

延伸核验：[云端 KingScript 与 ISCB 运行时边界](https://chatgpt.com/space/page_e22ab958bea4819195a0e5ffd3b154c2)。
