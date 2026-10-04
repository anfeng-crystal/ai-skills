# queryAndExportByFilter - 查询与导出共用过滤链路

## 场景

报表页面支持多条件查询后，用户还希望直接导出当前结果；当导出方式切换为“分 Sheet 导出”时，又希望按已选组织拆成多个 Sheet，而不是重新写一套导出过滤逻辑。

## Java 来源

- `kd.bos.plugin.sample.report.queryplugin.TestReportExportPlugin`

这个 Java 样例的核心点有 3 个：

- `query` 和 `export` 复用同一套过滤收集逻辑
- `export` 通过 `exporttype = 1` 控制整表导出
- `exportWithSheet` 通过 `exporttype = 2` 和 `orgfield` 控制按组织拆 Sheet

## 适用入口

- `query(queryParam: ReportQueryParam, selectedObj: object): DataSet`
- `export(queryParam: ReportQueryParam, selectedObj: object): DataSet`
- `exportWithSheet(queryParam: ReportQueryParam, selectedObj: object): $.java.util.List`
- 插件基类：`AbstractReportListDataPlugin`

## 完整 Kingscript 示例

```typescript
import { BasedataEntityType } from "@cosmic/bos-core/kd/bos/entity";
import { DataSet } from "@cosmic/bos-core/kd/bos/algo";
import { DynamicObject, DynamicObjectCollection } from "@cosmic/bos-core/kd/bos/dataentity/entity";
import {
  AbstractReportListDataPlugin,
  ReportQueryParam
} from "@cosmic/bos-core/kd/bos/entity/report";
import { QCP, QFilter } from "@cosmic/bos-core/kd/bos/orm/query";
import { QueryServiceHelper } from "@cosmic/bos-core/kd/bos/servicehelper";
import { ArrayList } from "@cosmic/bos-script/java/util";

/** 项目桥接须返回原生Java结果；绑定实现见报表表单插件第3节。 */
interface ReportSheetBridge {
  create(sheetName: string, data: DataSet): object;
}
declare function getReportSheetBridge(): ReportSheetBridge;

function organizationSheetName(name: string | null, used: Set<string>): string {
  let base = (name == null ? "" : String(name)).replace(/[\u0000-\u001f\\/?*\[\]:]/g, "_").trim();
  base = base.replace(/^'+|'+$/g, "") || "未命名组织";
  let candidate = base.slice(0, 31).replace(/'+$/g, "");
  let index = 2;
  while (used.has(candidate.toLowerCase())) {
    const suffix = "_" + index++;
    candidate = base.slice(0, 31 - suffix.length).replace(/'+$/g, "") + suffix;
  }
  used.add(candidate.toLowerCase());
  return candidate;
}

class QueryAndExportByFilterPlugin extends AbstractReportListDataPlugin {

  private formId = "kdtest_report001";
  private selectFields =
    "billno,kdtest_integerfield,kdtest_decimalfield,kdtest_textfield,"
    + "kdtest_datefield,kdtest_datetimefield,kdtest_amountfield,kdtest_orgfield";

  query(queryParam: ReportQueryParam, selectedObj: object): DataSet {
    let filters = this.buildFilters(queryParam, true);
    return QueryServiceHelper.queryDataSet(
      "QueryAndExportByFilterPlugin",
      this.formId,
      this.selectFields,
      filters,
      "billno asc", -1
    );
  }

  export(queryParam: ReportQueryParam, selectedObj: object): DataSet {
    let exportType = queryParam.getFilter().getValue("exporttype") as string;
    if (exportType !== "1") {
      return super.export!(queryParam, selectedObj);
    }

    let filters = this.buildFilters(queryParam, true);
    return QueryServiceHelper.queryDataSet(
      "QueryAndExportByFilterPlugin",
      this.formId,
      this.selectFields,
      filters,
      "billno asc", -1
    );
  }

  exportWithSheet(queryParam: ReportQueryParam, selectedObj: object): $.java.util.List {
    let exportType = queryParam.getFilter().getValue("exporttype") as string;
    if (exportType !== "2") {
      return super.exportWithSheet!(queryParam, selectedObj);
    }

    const bridge = getReportSheetBridge();
    if (bridge == null || typeof bridge.create !== "function") throw new Error("缺少真实Sheet结果桥接");
    const resultList = new ArrayList();
    const owned: DataSet[] = [];
    const used = new Set<string>();
    const addSheet = (name: string | null, data: DataSet): void => {
      owned.push(data);
      const result = bridge.create(organizationSheetName(name, used), data);
      if (result == null) throw new Error("Sheet桥接未返回结果");
      resultList.add(result);
    };
    try {
      const orgs = queryParam.getFilter().getValue("orgfield") as DynamicObjectCollection;
      if (orgs == null || orgs.size() === 0) {
        addSheet("全部组织", this.query(queryParam, selectedObj));
      } else {
        for (let i = 0; i < orgs.size(); i++) {
          const org = orgs.get(i) as DynamicObject;
          if (org == null || org.getPkValue() == null) throw new Error("所选组织缺少身份");
          // 原Java样例将其转换为BasedataEntityType，不能在IDataEntityType上虚构方法。
          const orgType = org.getDataEntityType() as BasedataEntityType;
          const nameProp = orgType.getNameProperty();
          if (!nameProp) throw new Error("组织名称属性未配置");
          const name = org.getString(nameProp);
          const filters = this.buildFilters(queryParam, false);
          filters.push(new QFilter("kdtest_orgfield.id", QCP.equals, org.getPkValue()));
          const data = QueryServiceHelper.queryDataSet(
            "QueryAndExportByFilterPlugin_sheet", this.formId, this.selectFields,
            filters, "billno asc", -1
          );
          addSheet(name, data);
        }
      }
    } catch (error) {
      for (const data of owned) { try { data.close(); } catch (_) {} }
      throw error;
    }
    // 成功后各数据流由导出消费者接管；此处不预先close。
    return resultList;
  }

  private buildFilters(queryParam: ReportQueryParam, appendOrgIn: boolean): QFilter[] {
    let filters: QFilter[] = [];
    let headFilters = queryParam.getFilter().getHeadFilters();
    if (headFilters != null) {
      for (let i = 0; i < headFilters.size(); i++) {
        filters.push(headFilters.get(i) as QFilter);
      }
    }

    let qFilters = queryParam.getFilter().getQFilters();
    if (qFilters != null) {
      for (let i = 0; i < qFilters.size(); i++) {
        filters.push(qFilters.get(i) as QFilter);
      }
    }

    if (!appendOrgIn) {
      return filters;
    }

    let orgs = queryParam.getFilter().getValue("orgfield") as DynamicObjectCollection;
    if (orgs == null || orgs.size() === 0) {
      return filters;
    }

    let orgIds: object[] = [];
    for (let i = 0; i < orgs.size(); i++) {
      let org = orgs.get(i) as DynamicObject;
      orgIds.push(org.getPkValue());
    }

    if (orgIds.length > 0) {
      filters.push(new QFilter("kdtest_orgfield.id", QCP.in, orgIds));
    }
    return filters;
  }
}

let plugin = new QueryAndExportByFilterPlugin();
export { plugin, QueryAndExportByFilterPlugin, organizationSheetName };
```

## 映射说明

- Java 样例里私有的 `getQfilter(queryParam, boolean)` 被拆成了 `buildFilters(queryParam, appendOrgIn)`，这样更容易看清“公共过滤”和“按组织补 in 条件”的边界。
- `exporttype` 在 Java 里分别用 `"1"` 和 `"2"` 分流 `export`、`exportWithSheet`。这里沿用同一约定，避免页面查询和导出逻辑脱节。
- `exportWithSheet` 里每次循环都从公共过滤重新构造，再追加单个组织的 `equals` 条件，对应 Java 中“先复用过滤，再叠加当前 Sheet 组织”的写法。
- 这里用 `QueryServiceHelper.queryDataSet` 表达 DataSet 查询，和现有本地报表示例保持一致；场景重点在过滤链路复用，而不是 ORM/Helper 的具体实现差异。

## 注意事项

- 目标7.0导出器先调用 `export`，仅其返回null才调用 `exportWithSheet`；`exporttype` 是本示例自己的分支条件。两个基类方法实际默认返回null，这里在不匹配时显式调用基类。不要给export无条件返回DataSet后还期待分Sheet优先。
- 如果过滤面板里组织字段是多选基础资料，整表导出适合用 `in`，分 Sheet 导出则应改成单个组织 `equals`，不要混用。
- 报表查询插件优先只做取数和导出，不要把列头排序过滤、合计行等交互逻辑也塞进来，那些能力应该放到报表表单插件。

目标7.0随包脚本声明未导出 `ReportExportDataResult`，不能凭Java类存在捏造脚本导入。`getReportSheetBridge` 为项目接入合同，必须采用 [真实Java桥接及资源/Sheet名边界](../报表表单插件.md#3-exportwithsheet---分-sheet-页导出数据)，保持返回原生对象；普通JS对象不能通过导出消费者强制转换。该桥接仍需真实KingScript验收，本节原有实体字段与过滤合同不因此获得元数据或权限验证。

本示例的orgfield须与原Java样例一致：集合元素本身就是组织DynamicObject，类型为BasedataEntityType，名称属性由元数据取得；不猜固定name字段，也不把分录包装行当组织。成功返回独立数据流，桥接或中途查询失败时释放已持有的数据流，保留原错误；Sheet名清洗及去重不改变查询组织身份。

空组织选择时的“全部组织”分支沿用本地原有示例，按当前公共过滤返回范围；这是本示例的行为选择，原Java样例在空集合时返回空List。是否允许该分支须遵循项目既有查询权限与空选择合同，不能据此推导无条件跨组织授权。
