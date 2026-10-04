# beforeClosed - 物料选择的确认、取消与关闭

来源：与 [表单插件.md](../表单插件.md#36-beforeclosed) 保持同一完整子页及父页协议。

## 事件合同

`AbstractFormPlugin.beforeClosed(e: BeforeClosedEvent): void` 在常规表单关闭前触发。`e.setCancel(true)` 可阻止本次关闭，`e.isCancel()` 读取已有取消结果。该事件本身没有“用户已确认”的含义；窗口 X、取消按钮或代码关闭都不能直接视作物料选择确认。

`returnDataToParent(value)` 暂存待返回值；父页用 `FormShowParameter.setCloseCallBack(new CloseCallBack(this, actionId))` 接收实际关闭后的 `closedCallBack`。示例分别处理确认意图与回传值，避免一次关闭被否决后，下一次取消或 X 关闭返回旧勾选。

## 场景与配置

- 子页 `custom_material_select` 是普通动态表单，使用 `AbstractFormPlugin` 和 `FormShowParameter`。父页是采购订单，使用 `AbstractBillPlugIn`。子页不修改运行时元数据：真实 `FormView.close` 的 `runtimeMetaChanged` 特殊分支会跳过常规 `beforeClosed`，不适用此协议。
- 子页普通按钮 `btn_confirm`、`btn_cancel`，父页普通按钮 `btn_material_select` 均由代码注册 `click`。不要再给这三个按钮绑定关闭、保存等操作；`Button.click` 会先执行绑定操作，再派发 `click`。工具栏按钮应按目标元数据接到 `itemClick`。
- 子页 `billentry` 包含复选框 `isselected`、基础资料 `material`/`unit`、文本 `materialname`/`materialnumber`/`specification`、小数 `price`/`qty`。父页 `billentry` 写入 `material`、`unit`、`price`、`qty`。标识和字段类型必须对应实际页面；物料/单位引用需与父页目标基础资料一致。
- 子页保留7项载荷，采用明确的 JSON 字符串协议。物料和单位从 `DynamicObject.getPkValue()` 取主键；主键及 BigDecimal 均不经过 JavaScript `number`。单位、小数的 `null` 原样保留，零和负值不在传输层擅自改写，业务合法性由目标单据规则校验。

## 子页：确认才回传

确认意图仅在普通按钮调用 `close()` 的同步期间有效。每次 `beforeClosed` 都先消费意图、清掉旧载荷，再尊重父类取消结果；本次没有选中行时回传 `[]`。`finally` 同时清掉意图与返回值，因为所核常规 `FormView.close` 已在返回前构建回调包装并派发。此规则不应移植到未核实的异步自定义关闭实现。

```typescript
import { AbstractFormPlugin } from "@cosmic/bos-core/kd/bos/form/plugin";
import { Control } from "@cosmic/bos-core/kd/bos/form/control";
import { BeforeClosedEvent } from "@cosmic/bos-core/kd/bos/form/events";
import { DynamicObject } from "@cosmic/bos-core/kd/bos/dataentity/entity";
import { EventObject } from "@cosmic/bos-script/java/util";
import { BigDecimal } from "@cosmic/bos-script/java/math";

/** 子页与父页共用的字符串协议；主键和小数不经过 JavaScript number。 */
interface MaterialSelection {
  materialId: string;
  materialName: string;
  materialNumber: string;
  specification: string;
  unitId: string | null;
  price: string | null;
  qty: string | null;
}

/**
 * 普通动态表单物料选择器，只在确认按钮发起的关闭尝试中回传数据。
 * 子页使用 FormShowParameter 打开；不修改运行时元数据，不附加自动关闭操作。
 */
class MaterialSelectDialogPlugin extends AbstractFormPlugin {
  /** 两个普通按钮都由本插件处理关闭，不能再绑定另一条关闭操作。 */
  registerListener(e: EventObject): void {
    super.registerListener(e);
    this.addClickListeners("btn_confirm", "btn_cancel");
  }

  /** 确认意图仅属于这次同步 close 调用，关闭被否决后不保留。 */
  click(e: EventObject): void {
    super.click(e);
    const key = (e.getSource() as Control).getKey();
    if (key !== "btn_confirm" && key !== "btn_cancel") {
      return;
    }
    const cache = this.getView().getPageCache();
    cache.remove("materialSelect.confirm");
    this.getView().returnDataToParent(null);
    if (key === "btn_confirm") {
      cache.put("materialSelect.confirm", "yes");
    }
    try {
      this.getView().close();
    } finally {
      cache.remove("materialSelect.confirm");
      // 常规 FormView.close 同步构建/派发回调后再清理；否决或异常也不残留载荷。
      this.getView().returnDataToParent(null);
    }
  }

  /** 每次关闭都清理旧载荷；取消按钮与窗口 X 不会把已有勾选作为确认。 */
  beforeClosed(e: BeforeClosedEvent): void {
    const cache = this.getView().getPageCache();
    const confirmed = cache.get("materialSelect.confirm") === "yes";
    cache.remove("materialSelect.confirm");
    this.getView().returnDataToParent(null);
    super.beforeClosed(e);
    if (e.isCancel() || !confirmed) {
      return;
    }
    const selected: MaterialSelection[] = [];
    try {
      const count = this.getModel().getEntryRowCount("billentry");
      for (let row = 0; row < count; row++) {
        if (this.getModel().getValue("isselected", row) !== true) {
          continue;
        }
        const materialId = this.readPk("material", row);
        if (materialId == null) {
          throw new Error("第" + (row + 1) + "行未选择物料");
        }
        selected.push({
          materialId: materialId,
          materialName: this.readText("materialname", row),
          materialNumber: this.readText("materialnumber", row),
          specification: this.readText("specification", row),
          unitId: this.readPk("unit", row),
          price: this.readDecimal("price", row),
          qty: this.readDecimal("qty", row)
        });
      }
      // 空数组也是本次确认结果，不能复用上次被取消关闭时的载荷。
      this.getView().returnDataToParent(JSON.stringify(selected));
    } catch (error) {
      e.setCancel(true);
      this.getView().showErrorNotification("物料数据未回传：" + String(error));
    }
  }

  /** 基础资料字段模型值为 DynamicObject，取真实主键；空单位保持 null。 */
  private readPk(key: string, row: number): string | null {
    const value = this.getModel().getValue(key, row) as DynamicObject;
    if (value == null) {
      return null;
    }
    const pk = value.getPkValue();
    if (pk == null) {
      return null;
    }
    if (typeof pk === "number" && !Number.isSafeInteger(pk)) {
      throw new Error("基础资料主键已超出安全整数范围");
    }
    const id = String(pk);
    return id === "" || id === "0" ? null : id;
  }

  /** 展示文本只作回传信息，不据此查找或代替物料主键。 */
  private readText(key: string, row: number): string {
    const value = this.getModel().getValue(key, row);
    return value == null ? "" : String(value);
  }

  /** 保留金额/数量的 null、零及十进制精度，业务约束由单据规则处理。 */
  private readDecimal(key: string, row: number): string | null {
    const value = this.getModel().getValue(key, row) as BigDecimal;
    return value == null ? null : value.toString();
  }
}
let plugin = new MaterialSelectDialogPlugin();
export { plugin };
```

## 父页：打开并回填4字段

```typescript
import { AbstractBillPlugIn } from "@cosmic/bos-core/kd/bos/bill";
import { Control } from "@cosmic/bos-core/kd/bos/form/control";
import { ClosedCallBackEvent } from "@cosmic/bos-core/kd/bos/form/events";
import { FormShowParameter, ShowType, StyleCss, CloseCallBack } from "@cosmic/bos-core/kd/bos/form";
import { EventObject } from "@cosmic/bos-script/java/util";
import { BigDecimal } from "@cosmic/bos-script/java/math";
import { DynamicObject } from "@cosmic/bos-core/kd/bos/dataentity/entity";

/** 字符串载荷先全量校验并恢复数值，再开始修改父页模型。 */
interface PreparedMaterial {
  materialId: string;
  materialName: string;
  materialNumber: string;
  specification: string;
  unitId: string | null;
  price: BigDecimal | null;
  qty: BigDecimal | null;
}

/** 采购订单普通按钮打开动态选择器；回填仅影响当前模型，不执行保存。 */
class PmPurorderMaterialSelectPlugin extends AbstractBillPlugIn {
  registerListener(e: EventObject): void {
    super.registerListener(e);
    this.addClickListeners("btn_material_select");
  }

  /** 普通按钮 click 接线；工具栏按钮应按真实元数据改用 itemClick。 */
  click(e: EventObject): void {
    super.click(e);
    if ((e.getSource() as Control).getKey() === "btn_material_select") {
      this.openMaterialSelectDialog();
    }
  }

  private openMaterialSelectDialog(): void {
    const fsp = new FormShowParameter();
    fsp.setFormId("custom_material_select");
    fsp.getOpenStyle().setShowType(ShowType.Modal);
    const css = new StyleCss();
    css.setWidth("960px");
    css.setHeight("580px");
    fsp.getOpenStyle().setInlineStyleCss(css);
    fsp.setCloseCallBack(new CloseCallBack(this, "material_select"));
    this.getView().showForm(fsp);
  }

  /** 取消/无载荷不写回；只在全部4字段完成后累计成功行数。 */
  closedCallBack(e: ClosedCallBackEvent): void {
    super.closedCallBack(e);
    if (e.getActionId() !== "material_select" || e.getReturnData() == null) {
      return;
    }
    let completed = 0;
    let currentRow = -1;
    try {
      const materials = this.prepareMaterials(String(e.getReturnData()));
      for (let i = 0; i < materials.length; i++) {
        currentRow = -1;
        const row = this.getModel().createNewEntryRow("billentry");
        if (row < 0) {
          throw new Error("第" + (i + 1) + "条物料新增分录未完成");
        }
        currentRow = row;
        const item = materials[i];
        this.getModel().setValue("material", item.materialId, row);
        this.getModel().setValue("unit", item.unitId, row);
        this.getModel().setValue("price", item.price, row);
        this.getModel().setValue("qty", item.qty, row);
        this.verifyReference("material", item.materialId, row);
        this.verifyReference("unit", item.unitId, row);
        completed++;
        currentRow = -1;
      }
      if (completed > 0) {
        this.getView().showSuccessNotification("已添加" + completed + "条物料，尚未保存");
      }
    } catch (error) {
      const partial = currentRow >= 0 ? "，第" + (currentRow + 1) + "行可能已部分赋值" : "";
      this.getView().showErrorNotification(
        "物料回填中断，已完整添加" + completed + "条" + partial +
        "。请检查当前分录后再继续，勿直接重复添加。原因：" + String(error)
      );
    }
  }

  /** 引用不存在时 setValue 可能直接返回，必须回读，不能以未抛错认定成功。 */
  private verifyReference(key: string, expected: string | null, row: number): void {
    const value = this.getModel().getValue(key, row) as DynamicObject;
    const pk = value == null ? null : value.getPkValue();
    const actual = pk == null || String(pk) === "0" || String(pk) === "" ? null : String(pk);
    if (actual !== expected) {
      throw new Error("第" + (row + 1) + "行基础资料 " + key + " 未按选择结果写入");
    }
  }

  /** 协议校验先于任何新增行；显示值不用于替代基础资料主键。 */
  private prepareMaterials(text: string): PreparedMaterial[] {
    const parsed: unknown = JSON.parse(text);
    if (!Array.isArray(parsed)) {
      throw new Error("物料载荷必须是数组");
    }
    const prepared: PreparedMaterial[] = [];
    for (let i = 0; i < parsed.length; i++) {
      const value: unknown = parsed[i];
      if (value == null || typeof value !== "object" || Array.isArray(value)) {
        throw new Error("物料载荷行格式错误");
      }
      const row = value as Record<string, unknown>;
      if (typeof row.materialId !== "string" || row.materialId === "" || row.materialId === "0" ||
          !(row.unitId === null || (typeof row.unitId === "string" && row.unitId !== "" && row.unitId !== "0")) ||
          typeof row.materialName !== "string" || typeof row.materialNumber !== "string" ||
          typeof row.specification !== "string") {
        throw new Error("第" + (i + 1) + "条物料的主键或文本格式错误");
      }
      prepared.push({
        materialId: row.materialId,
        materialName: row.materialName,
        materialNumber: row.materialNumber,
        specification: row.specification,
        unitId: row.unitId as string | null,
        price: this.parseDecimal(row.price),
        qty: this.parseDecimal(row.qty)
      });
    }
    return prepared;
  }

  /** 小数字符串直接构造 BigDecimal，null 不变成0；非法字符串整体拒绝。 */
  private parseDecimal(value: unknown): BigDecimal | null {
    if (value === null) {
      return null;
    }
    if (typeof value !== "string" || value.trim() === "") {
      throw new Error("金额或数量必须为十进制字符串或null");
    }
    return new BigDecimal(value);
  }
}
let plugin = new PmPurorderMaterialSelectPlugin();
export { plugin };
```

## 能力与失败边界

- 父页先校验整批载荷并构造 BigDecimal，再新增行；语法、字段类型或小数字符串有问题时不创建任何行。主键存在性仍由模型引用加载判断，不把客户端文本名称当作主键。
- `createNewEntryRow` 必须使用返回的有效行索引；负值表示未取得有效新增索引，不能继续按该值赋值，也不将其固定解释成某种用户操作。
- 真实基础资料字段在按主键加载无结果时可能直接返回，不一定抛异常。因此4个字段赋值后回读物料和单位主键，匹配才计入完成数。该检查不代替组织、基础资料、保存或操作权限校验。
- 回填只修改当前父页模型，未保存。任何新增/赋值/回读失败都停止后续行，保留已完成行和可能部分写入的当前行，提示用户核对；没有数据库事务、自动回滚或重复回调幂等保证。不要直接重新添加整批。删除分录也可能被其他插件取消，不能把调用删除冒称回滚成功。
- 子页确认被其他插件否决或关闭抛异常后，不保留确认意图/待返载荷；父类已有取消不被清除。此选择器应独占自己的返回协议，其他插件不得覆盖该载荷。若改用单据子页、脏数据确认或自定义异步关闭，需要重新核实事件顺序。
- 本例的本地类型与逻辑检查不能证明 KingScript Java 桥接、JSON回传、实际按钮/X、跨插件关闭否决、引用权限及保存成功；应在目标平台沿“父页按钮→确认/取消/X→回填→失败后核对”验收。

## 依据

- [官方 beforeClosed 事件](https://vip.kingdee.com/knowledge/222768769984991488)：常规关闭前事件及取消接口。文中 `setCheckDataChange` 描述与评论存在冲突，本例不依赖此标记关闭数据检查。
- [官方 closedCallBack 事件](https://vip.kingdee.com/knowledge/222764162105886464)：父页回调配置与普通按钮监听；子页确认回传、取消空值。
- 本例 API 按实际 7.0 标签构件中的 `AbstractFormPlugin`、`FormView`、`AbstractFormView`、`Button`、`BasedataProp`、`AbstractFormDataModel` 与脚本声明核对。构件标签不证明所有7.0补丁一致；目标环境不同时应核其实际依赖。
