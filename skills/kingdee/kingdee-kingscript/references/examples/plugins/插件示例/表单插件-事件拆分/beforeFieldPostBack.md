# beforeFieldPostBack - 字段值提交模型前事件

## 基本信息

| 属性 | 说明 |
|------|------|
| 所属接口 | AbstractFormPlugin |
| 触发时机 | 服务端已收到客户端字段回传，准备交给字段控件写入模型之前 |
| 方法签名 | `beforeFieldPostBack(e: BeforeFieldPostBackEvent): void` |

## 说明

此事件用于检查本次输入是否允许进入模型，不是浏览器发送请求前的网络拦截器。[官方 KingScript 事件总览](https://vip.kingdee.com/knowledge/474603833067386624)将其定义为字段提交模型前的合法性检查。已核实的 7.0 构件中，`FormController.postFieldState` 收到字段数据后派发事件，仅未取消时调用 `FieldEdit.postBack`，后者再写入模型。

`e.setCancel(true)` 拒绝本次模型更新。不能把它用于“暂不联动但保证最终保存”的备注字段优化：本次请求已经到达服务端，被拒绝的值也没有因此获得稍后必定重传的保证。需要降低字段即时更新时，应配置字段的即时更新属性；本例使用真实 `FieldEdit.setFireEvtUp(false)`，实际网络与保存行为仍要在目标页面验证。

## 参数说明

| API | 类型 | 含义 |
|-----|------|------|
| e | BeforeFieldPostBackEvent | 从 `@cosmic/bos-core/kd/bos/form/events` 导入 |
| e.getKey() | string | 控件标识；不自动等于实体字段标识 |
| e.getValue() | any | 本次输入，声明原样为通用类型；按真实字段类型解释 |
| e.getRowIndex() / e.getParentRowIndex() | number / number | 行与父行索引，适用含义由目标控件决定 |
| e.isCancel() / e.setCancel(boolean) | boolean / void | 读取或设置本次模型更新取消状态；保留其他插件已有取消 |

`getFieldKey()` 属于 `FieldEdit`，不是本事件的方法。事件虽然有 `setValue`，本次核实的控制器仍把原局部值交给 `postBack`；不能仅凭该 setter 存在承诺输入替换有效。需要改值时另核目标版本实际调用链。

## 业务场景与前提

保留采购订单中八个普通文本字段的录入能力，关闭它们的即时更新：行备注、内部备注、物流备注、描述、单据头备注、收货地址、联系人、联系电话。数量、单价、物料、供应商和币别保持原来的联动配置。只有这些文本字段确实不参与即时校验、计算或其他业务依赖时才采用该配置；联系人等名称本身不能证明没有依赖。

下列标识是本例的页面控件 key，要求实际绑定到相应的 `FieldEdit` 普通文本字段。布局缺少某控件时跳过；存在但类型不符应先修正配置，不用强制转换掩盖。`beforeFieldPostBack` 不重写，因此正常文本录入不被本例取消，父类和其他插件的校验仍按原链执行。

## 完整示例代码

```typescript
import { AbstractBillPlugIn } from "@cosmic/bos-core/kd/bos/bill";
import { FieldEdit } from "@cosmic/bos-core/kd/bos/form/field";
import { EventObject } from "@cosmic/bos-script/java/util";

/**
 * 采购订单文本字段的即时更新配置。
 * 控件标识和纯文本字段依赖须先按目标元数据核实；保留字段正常回传模型的路径。
 */
class PmPurorderPostBackControlPlugin extends AbstractBillPlugIn {
  /** 数据绑定后配置8个无需即时联动的文本字段，不取消正常录入回传。 */
  afterBindData(e: EventObject): void {
    super.afterBindData(e);
    const deferredControls = [
      "entryremark", "internalremark", "logisticsremark", "description",
      "headremark", "deliveryaddress", "contactperson", "contactphone"
    ];
    for (let i = 0; i < deferredControls.length; i++) {
      // 示例前提：这些标识对应目标页面的 FieldEdit 文本控件。
      const edit = this.getView().getControl(deferredControls[i]) as FieldEdit;
      if (edit != null) {
        edit.setFireEvtUp(false);
      }
    }
    // qty、price、material、supplier、currency 保持原有即时更新配置。
  }
}
let plugin = new PmPurorderPostBackControlPlugin();
export { plugin };
```

## 注意事项

- 需要拒绝非法输入时，才在 `beforeFieldPostBack` 核对控件、行和真实值后设置取消；不要主动 `setCancel(false)` 清除他人的拒绝。
- 关闭即时更新不等于关闭所有网络请求、服务端校验或 `propertyChanged`；也不保证任意布局、分录分页、其他插件组合下最终保存结果。验收应覆盖输入、焦点离开、关键字段联动、翻页及保存重开。
- 本例保留 `super.afterBindData(e)`；重复绑定重新应用该控件配置，不修改关键字段的既有值或配置。
- 真实声明编译仅验证本次使用点；未运行平台控件派发、Java 字符串桥接、网络流量或保存流程。
