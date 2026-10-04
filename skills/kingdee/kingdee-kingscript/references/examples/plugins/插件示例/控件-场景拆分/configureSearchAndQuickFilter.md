# configureSearchAndQuickFilter - 配置搜索联想与快速打开

## 场景与入口

PC页面的 `searchap` 配置为 `showModel=1`（自动补全）。输入关键词后同时查询结算方式和币别，显示带来源前缀的文本建议；确认当前建议后通过页面缓存映射打开对应资料。

保留 `kd.bos.plugin.sample.dynamicform.pcform.control.bizcase.SearchSample` 的双来源查询、缓存跨回调和 `BillShowParameter` 快开。插件基类为 `AbstractFormPlugin`，入口为 `registerListener`、`getSearchList`、`search`；真实注册方法为 `Search.addEnterListener`。

`bd_settlementtype`、`bd_currency` 与 `id/number/name`、表单ID和查询/查看权限须在项目确认；本例沿用这两类对象，各按编号或名称模糊匹配、按编号排序、最多10条。页面缓存键 `searchList` 必须由此搜索框独占。

## 完整 Kingscript 示例

```typescript
/**
 * PC 自动补全搜索结算方式和币别；本页缓存保存当前建议对应的字符串主键。
 * searchap 必须是模式1，项目须确认两个基础资料的查询及查看权限和字段合同。
 */
import { BillShowParameter } from "@cosmic/bos-core/kd/bos/bill";
import { DynamicObject } from "@cosmic/bos-core/kd/bos/dataentity/entity";
import { AbstractFormPlugin } from "@cosmic/bos-core/kd/bos/form/plugin";
import { Search } from "@cosmic/bos-core/kd/bos/form/control";
import { SearchEnterEvent, SearchEnterListener } from "@cosmic/bos-core/kd/bos/form/control/events";
import { QFilter } from "@cosmic/bos-core/kd/bos/orm/query";
import { QueryServiceHelper } from "@cosmic/bos-core/kd/bos/servicehelper";
import { ArrayList } from "@cosmic/bos-script/java/util";

interface SearchHit { formId: string; pkId: string; }
type SearchTargets = Record<string, SearchHit>;

class ConfigureSearchAndQuickFilterPlugin extends AbstractFormPlugin implements SearchEnterListener {
  /** 仅注册目标搜索框；不将普通建议协议用于模式3。 */
  registerListener(e: $.java.util.EventObject): void {
    super.registerListener(e);
    const search = this.getView().getControl("searchap") as Search;
    search.addEnterListener(this);
  }

  /** 每次查询先清除旧映射，保留双来源建议和各10条的查询上限。 */
  getSearchList(evt: SearchEnterEvent): $.java.util.List {
    const suggestions = new ArrayList();
    const source = evt.getSource() as Search;
    if (source.getKey() !== "searchap" || source.getShowModel() !== 1) return suggestions;
    this.getView().getPageCache().put("searchList", "{}");
    const keyword = evt.getText();
    if (keyword == null || keyword.trim() === "") return suggestions;
    const targets: SearchTargets = Object.create(null) as SearchTargets;
    this.appendSearchResult(suggestions, targets, "结算方式", "bd_settlementtype", keyword);
    this.appendSearchResult(suggestions, targets, "币别", "bd_currency", keyword);
    this.getView().getPageCache().put("searchList", JSON.stringify(targets));
    return suggestions;
  }

  /** 仅打开本次建议映射中的固定业务对象，普通任意输入不拼接表单或主键。 */
  search(evt: SearchEnterEvent): void {
    const source = evt.getSource() as Search;
    if (source.getKey() !== "searchap" || source.getShowModel() !== 1) return;
    const selectedText = evt.getText();
    if (selectedText == null || selectedText.trim() === "") return;
    const cached = this.getView().getPageCache().get("searchList");
    if (cached == null || cached === "") {
      this.getView().showTipNotification("请先输入关键词并从联想结果中选择。");
      return;
    }
    const value: unknown = JSON.parse(cached);
    if (value === null || typeof value !== "object") throw new Error("本页搜索映射格式无效");
    const targets = value as Record<string, unknown>;
    const raw = Object.prototype.hasOwnProperty.call(targets, selectedText) ? targets[selectedText] : null;
    if (raw === null || typeof raw !== "object") {
      this.getView().showTipNotification("未命中搜索建议，请重新选择建议项。");
      return;
    }
    const hit = raw as Record<string, unknown>;
    if ((hit.formId !== "bd_settlementtype" && hit.formId !== "bd_currency") ||
        typeof hit.pkId !== "string" || hit.pkId === "") throw new Error("本页搜索目标无效");
    const showParam = new BillShowParameter();
    showParam.setFormId(hit.formId);
    showParam.setPkId(hit.pkId);
    this.getView().showForm(showParam);
  }

  /** 编号/名称匹配并按编号排序；主键先转字符串，避免JSON数值损失精度。 */
  private appendSearchResult(suggestions: $.java.util.List, targets: SearchTargets,
      caption: string, formId: string, keyword: string): void {
    const filter = new QFilter("number", "like", "%" + keyword + "%")
      .or(new QFilter("name", "like", "%" + keyword + "%"));
    const rows = QueryServiceHelper.query(formId, "id,number,name", [filter], "number", 10);
    for (let i = 0; i < rows.size(); i++) {
      const row = rows.get(i) as DynamicObject;
      const id = row.get("id");
      if (id == null || String(id) === "") continue;
      const label = caption + "：" + row.getString("number") + " " + row.getString("name");
      const hit = { formId: formId, pkId: String(id) };
      if (Object.prototype.hasOwnProperty.call(targets, label)) {
        if (targets[label].formId !== hit.formId || targets[label].pkId !== hit.pkId) {
          throw new Error("搜索建议文案重复，需由项目增加业务区分信息：" + label);
        }
        continue;
      }
      suggestions.add(label);
      targets[label] = hit;
    }
  }
}

const plugin = new ConfigureSearchAndQuickFilterPlugin();
export { plugin };
```

## 文本建议、缓存和打开合同

- 模式1返回 `List<String>`；确认时 `SearchEnterEvent.getText()` 可能是选中的建议文本，也可能是用户直接输入的文本。只有命中当前缓存的文本才打开；展示文案须稳定，未命中只提示重新选择，不从任意文本拼接表单或主键。
- 每次有效查询入口先清空旧映射，空词也清除；两类查询完成后一次写入完整JSON。仅保留当前页临时映射，跨页复用需独立合同。多个控件或插件不得共享本例独占缓存键。
- 主键在写JSON前转字符串，避免Java长整型主键在JSON数值中损失精度。相同标签指向不同对象时拒绝并要求项目增加业务区分信息，不能静默覆盖；同目标重复行只保留一次。
- 仅打开缓存中两种固定对象的非空字符串主键。`showForm`发出打开请求不代表页面已经成功打开、用户获得权限或业务已保存；目标表单仍按已有权限处理。
- 模式3全局搜索使用另一份请求与分组响应协议，复杂点击经 `itemClick`，不能将本例直接挂到模式3。保留物料复杂显示的独立示例见[SearchEnterListener](../控件.md#searchenterlistener)。
- 运算符 `"like"` 由本机Java常量确认，避免调用目标脚本声明未导出的 `QCP.like`。这里保留原有匹配条件和查询上限，不把10条称作完整总数。

依据：[官方搜索控件编程](https://vip.kingdee.com/knowledge/226760708313580032)、[控件属性](https://vip.kingdee.com/knowledge/224164535035524352)与本机7.0 SDK/PC消费者。已核声明和本地载荷不等于真实KingScript引擎、项目数据或页面验收，不外推部署补丁。
