# configureMobTableColumnsAndPackageData - 配置 MobTable 列并打包数据

## 场景与前提

为移动表格 `mobtableap` 保留原列，在前面增加绿色必填文本列和整数列，调整原日期列编辑器，再按真实移动表格行协议补充四个目标值。保留的显示要求包括日期 `YYYY年MM月DD日` 和整数 `#,##0`；后者还需要目标平台的列/区域格式配置验证，不能从本代码推定已经生效。

本例面向已有真实单据实体/分录绑定、原列和数据源的移动表格。页数据每行须有 `billno/seq/bizdate/totalamount`，`seq` 是实际整数序号。既有日期列的 `key` 为 `datemobtablecolumnap`，金额列的 `fieldKey` 为 `amountDisplay`；按项目真实元数据替换。普通移动表单没有单据实体时，需要另行实现实际取数与全列打包，不能直接依赖本例的默认绑定器。

## 真实合同

- `MobTableHandleResult` 的行列表元素必须是 `MobTableRowData`。`List.add(any)` 编译通过不代表放入 `HashMap` 合法；原生 `getRows()` 会转换行类型，错误元素会抛异常。
- 新建结果的 `fmtInfo` 未初始化，直接 `getFmtInfo().put` 会空指针。裸 `MobTableRowData` 的按字段赋值仅修改已有占位，也不能代替列模板。
- 原生 Java 示例 `kd.bos.plugin.test.mobile.mobtable.MobTablePluginSample` 使用默认 handler 完成模板和原列绑定后补列。本例采用组合调用，保留接口默认 `getData=null` 和空 `handleSummary`，避免继承原生 handler 后额外引入重读数据库和汇总行为。
- 不提前调用 `getRows()` 做检查：该方法向结果内部行集合追加内容，重复调用可能重复打包。把转换留给平台消费者。

## 完整 KingScript 示例

```typescript
import { LocaleString } from "@cosmic/bos-core/kd/bos/dataentity/entity";
import { AbstractFormPlugin } from "@cosmic/bos-core/kd/bos/form/plugin";
import { MobTable, IMobTablePackageDataHandler, MobTablePackageDataHandler, MobTableRowData } from "@cosmic/bos-core/kd/bos/form/mcontrol/mobtable";
import { BeforeCreateMobTableColumnsEvent, MobTableHandleResult, MobTablePackageDataHandlerArgs, MobTablePackageDataHandlerEvent } from "@cosmic/bos-core/kd/bos/form/mcontrol/mobtable/events";
import { MobTableColumn } from "@cosmic/bos-core/kd/bos/form/mcontrol/mobtable/tablecolumn";
import { DateTimeField, IntegerField, TextField } from "@cosmic/bos-core/kd/bos/metadata/entity/commonfield";
import { ArrayList, Map } from "@cosmic/bos-core/java/util";

/**
 * 前提：已有可由默认handler绑定的单据实体/分录模型、数据源与原列。
 * pageData每行真实含billno、seq、bizdate、totalamount；seq是整数，不从主键或页号猜。
 * 既有日期列key=datemobtablecolumnap，金额列fieldKey=amountDisplay；标识按实际元数据替换。
 */
class SalesMobTablePackageHandler implements IMobTablePackageDataHandler {
  // 保持Java接口默认getData=null及空handleSummary，不继承原生类的重读DB/汇总行为。
  getFmtInfo(args: MobTablePackageDataHandlerArgs): Map {
    return new MobTablePackageDataHandler().getFmtInfo(args);
  }

  handleData(args: MobTablePackageDataHandlerArgs): MobTableHandleResult {
    const pageData = args.getPageData();
    if (pageData == null) {
      throw new Error("未取得移动表格页数据，请先配置实际数据源");
    }
    const columns = args.getMobTableColumns();
    let dateFieldKey = "";
    let dateCount = 0;
    let amountCount = 0;
    for (let i = 0; i < columns.size(); i++) {
      const column = columns.get(i) as MobTableColumn;
      if (column.getKey() === "datemobtablecolumnap") {
        dateFieldKey = column.getFieldKey();
        dateCount++;
      }
      if (column.getFieldKey() === "amountDisplay") amountCount++;
    }
    if (dateCount !== 1 || dateFieldKey == null || dateFieldKey === "" || amountCount !== 1) {
      throw new Error("请核实唯一日期列和amountDisplay金额列的真实绑定");
    }

    // 保留默认handler按真实FieldEdit绑定的原列值、特殊单元格结构和格式化信息。
    const result = new MobTablePackageDataHandler().handleData(args);
    const packedRows = result.getMobTableRowDataList();
    if (packedRows.size() !== pageData.size()) {
      throw new Error("移动表格默认打包行数与页数据不一致，请核实实体和分录配置");
    }
    for (let i = 0; i < pageData.size(); i++) {
      const sourceRow = pageData.get(i);
      const displayRow = packedRows.get(i) as MobTableRowData;
      // MobTableRowData已由默认handler用列模板构造；只覆盖四个明确的目标字段。
      displayRow.setValue("ktext", sourceRow.getString("billno"));
      displayRow.setValue("kinteger", sourceRow.getInt("seq"));
      displayRow.setValue(dateFieldKey, sourceRow.get("bizdate"));
      displayRow.setValue("amountDisplay", sourceRow.get("totalamount"));
    }
    // 默认handler通过setFmtInfo(getFmtInfo(args))填充格式对象；此处不调用getRows。
    // "#,##0"千分位显示须按目标列/前端格式合同配置，不把它放到未证实的fmtInfo根键。
    return result;
  }
}

class ConfigureMobTableColumnsAndPackageDataPlugin extends AbstractFormPlugin {
  initialize(): void {
    super.initialize();
    const mobTable = this.getView().getControl("mobtableap") as MobTable;
    mobTable.addBeforeCreateMobTableColumnsListener(this);
    mobTable.addMobTablePackageDataHandlerListener(this);
  }

  beforeCreateMobTableColumns(event: BeforeCreateMobTableColumnsEvent): void {
    const originalColumns = event.getMobTableColumns();
    for (let i = 0; i < originalColumns.size(); i++) {
      const column = originalColumns.get(i) as MobTableColumn;
      if (column.getKey() === "ktext" || column.getKey() === "kinteger" ||
          column.getFieldKey() === "ktext" || column.getFieldKey() === "kinteger") {
        throw new Error("ktext或kinteger与既有移动表格列重复，请先明确列配置归属");
      }
    }
    for (let i = 0; i < originalColumns.size(); i++) {
      const column = originalColumns.get(i) as MobTableColumn;
      if (column.getKey() !== "datemobtablecolumnap") continue;
      const dateField = new DateTimeField();
      const editor = dateField.createEditor();
      editor.put("df", "YYYY年MM月DD日");
      column.setCustomEditor(editor);
    }
    const rebuiltColumns = new ArrayList();
    const textField = new TextField();
    textField.setMustInput(true);
    const textColumn = new MobTableColumn();
    textColumn.setFieldKey("ktext");
    textColumn.setMobTableField("ktext");
    textColumn.setKey("ktext");
    textColumn.setCaption(new LocaleString("文本列"));
    textColumn.setForeColor("#99d92b");
    textColumn.setCustomEditor(textField.createEditor());
    rebuiltColumns.add(textColumn);

    const integerField = new IntegerField();
    integerField.setScale(2); // 保留原Java样例设置，不由此宣称整数编辑器显示两位小数。
    const integerColumn = new MobTableColumn();
    integerColumn.setFieldKey("kinteger");
    integerColumn.setMobTableField("kinteger");
    integerColumn.setKey("kinteger");
    integerColumn.setCaption(new LocaleString("整数列"));
    integerColumn.setCustomEditor(integerField.createEditor());
    rebuiltColumns.add(integerColumn);
    rebuiltColumns.addAll(originalColumns);
    originalColumns.clear();
    originalColumns.addAll(rebuiltColumns);
  }

  createMobTablePackageDataHandler(event: MobTablePackageDataHandlerEvent): void {
    event.setMobTablePackageDataHandler(new SalesMobTablePackageHandler());
  }
}

let plugin = new ConfigureMobTableColumnsAndPackageDataPlugin();
export { plugin };
```

## 能力保留与配置边界

两个监听在 `initialize` 注册；列创建时保留原日期编辑器配置、文本列三个标识、标题、绿色和必填设置，以及整数列和原列顺序。对已存在的同名附加列在修改前报错，避免重复叠列。`IntegerField.setScale(2)` 保留原 Java 样例调用；本地实际 `IntegerField.getScale()` 及生成编辑器 `sc` 均为0，不能宣称它让整数显示两位小数。

数据端委托默认 handler 保留原列、特殊单元格结构和原格式，只覆盖 `billno→ktext`、`seq→kinteger`、`bizdate→真实日期fieldKey`、`totalamount→amountDisplay`。日期 `key` 与 `fieldKey` 不混用。缺少唯一日期或金额绑定、页数据为空引用或打包行数不符时明确报错；合法空页仍为零行。

默认格式对象包含 `colfmt/currencyfmt/unitfmt/timezonefmt`，不是任意字段名到格式字符串的根 Map。没有证据表明 `fmtInfo.put("kinteger", "#,##0")` 会被前端识别。保留整数类型与千分位要求，由实际平台数字格式合同配置并验收，不用日期编辑器键猜测数字格式，也不把数字改成字符串掩盖缺少合同。

## 证据与验证范围

官方[移动表格说明](https://vip.kingdee.com/knowledge/229919492393407488)第4节展示 `MobTableRowBuilder.buildTemplateRowData`、`MobTableRowData.setValue`、类型化行列表及 `setFmtInfo(getFmtInfo(args))`；日期编辑器示例使用 `YYYY年MM月DD日`。页面在2026-10-03读取，标注更新2026-03-27；其中8.0新增能力不能据此套到7.0构件。

本例依据本机7.0实际声明、消费者字节码与原生样例修正。完整候选编译零诊断，28项编译产物局部逻辑检查和13项实际SDK Java探针通过；整数编辑器另有独立探针。Java探针验证行协议、默认接口和原错误复现，局部替身验证监听、原列保留和四值映射；它们没有执行实际数据绑定、KingScript接口桥接、数据库或移动前端。模块聚合路径、项目字段、数据显示和千分位效果仍需目标平台验证，不能将本地通过写成端到端验收。
