# showMessagesAndConfirmCallback - 消息提示与确认回调

## 场景与 Java 来源

用户点击表单按钮后显示普通消息、错误提示或删除确认；确认只作用于提示时绑定的分录，不能改删回调时的当前行。

Java 场景来源：`kd.bos.plugin.sample.dynamicform.pcform.form.bizcase.ShowMessageSample`。保留 `registerListener`、`click`、`confirmCallBack(e: MessageBoxClosedEvent)` 三个入口及 `showMessage`、`showErrorNotification`、`showTipNotification`、`showConfirm` 的组合。

## 声明与项目接入合同

下面是带项目接入合同的工厂示例，不是可以直接挂载的业务成品。本地 `@cosmic/bos-core` 声明包 `1.0.0` / buildTime `2025-11-12 15:28:03` 从 `kd/bos/form` 导出 `ConfirmCallBackListener`、`MessageBoxOptions`、`MessageBoxResult`，从 `kd/bos/form/events` 导出 `MessageBoxClosedEvent`。这不证明与目标 Java SDK、脚本引擎为同一发布包；部署前核对目标声明、模块解析及插件导出/注册方式。不要改用未核实的 `form/confirm`、`form/message` 导入路径。

项目提供实际按钮、平面分录与页面内独占的 `cachePrefix`，用已核配置调用 `createFormMessagePlugin` 后按目标引擎导出插件实例。`validate` 核对真实元数据、权限和删除条件；按钮不得另绑自动删除操作。`entryIdentity` 必须是同页跨请求稳定、非空且唯一的身份，可以是已保存主键或项目已有的未保存行标识，不能是行号、显示名或重复的0。`entryStamp` 覆盖提示内容及删除条件；`documentStamp` 覆盖当前数据代次、身份、状态及影响删除的编辑，不能只用数据库修改时间。没有这些真实合同就先补接入配置，不猜字段或生成临时身份。

本例只覆盖已核实的平面分录。其他前置插件不得重定向待删除行；树形、分批未加载、联动删除及并发回调需另按实际模型核验。缓存绑定交互对象，不替代业务授权或数据库幂等控制。通用删除对象说明见[表单插件确认回调](../表单插件.md#confirmcallback---绑定删除对象与标准删除操作)。

```typescript
import { AbstractFormPlugin } from "@cosmic/bos-core/kd/bos/form/plugin";
import { Control } from "@cosmic/bos-core/kd/bos/form/control";
import { ConfirmCallBackListener, MessageBoxOptions, MessageBoxResult } from "@cosmic/bos-core/kd/bos/form";
import { MessageBoxClosedEvent } from "@cosmic/bos-core/kd/bos/form/events";

interface MessageContract {
  messageButton: string;
  errorButton: string;
  deleteButton: string;
  entry: string;
  cachePrefix: string;
  validate(plugin: AbstractFormPlugin): void;
  documentStamp(plugin: AbstractFormPlugin): string;
  entryIdentity(plugin: AbstractFormPlugin, row: number): string;
  entryStamp(plugin: AbstractFormPlugin, row: number): string;
  entryLabel(plugin: AbstractFormPlugin, row: number): string;
}
interface MessageRow { key: string; stamp: string; }
interface MessageTarget { page: string; stamp: string; rows: MessageRow[]; }
interface MessagePending { id: string; index: number; target: MessageTarget; }

/** 三类消息入口；项目配置决定字段和身份，页面缓存保存跨请求的确认对象。 */
function createFormMessagePlugin(c: MessageContract): AbstractFormPlugin {
  const pendingKey = c.cachePrefix + ":pending", seqKey = c.cachePrefix + ":seq";
  return new class extends AbstractFormPlugin {
    /** 保存有序身份及条件快照；当前焦点不参与身份比较。 */
    private capture(): MessageTarget {
      c.validate(this);
      const rows: MessageRow[] = [], seen = new Set<string>();
      const count = this.getModel().getEntryRowCount(c.entry);
      if (!Number.isSafeInteger(count) || count < 0) throw new Error("分录行数无效");
      for (let i = 0; i < count; i++) {
        const key = c.entryIdentity(this, i), stamp = c.entryStamp(this, i);
        if (typeof key !== "string" || !key || typeof stamp !== "string" || !stamp || seen.has(key)) {
          throw new Error("分录身份或条件快照不完整/不唯一");
        }
        seen.add(key); rows.push({ key, stamp });
      }
      const page = this.getView().getPageId(), stamp = c.documentStamp(this);
      if (!page || typeof stamp !== "string" || !stamp) throw new Error("页面数据快照未就绪");
      return { page, stamp, rows };
    }
    /** 缓存损坏即失效，未知 JSON 不能成为删除凭据。 */
    private readPending(): MessagePending | null {
      const cache = this.getView().getPageCache(), raw = cache.get(pendingKey);
      if (raw == null) return null;
      try {
        const p = JSON.parse(raw) as MessagePending;
        if (p && typeof p.id === "string" && p.id && Number.isSafeInteger(p.index) &&
            p.target && typeof p.target.page === "string" && p.target.page &&
            typeof p.target.stamp === "string" && p.target.stamp && Array.isArray(p.target.rows) &&
            p.index >= 0 && p.index < p.target.rows.length &&
            p.target.rows.every(r => r && typeof r.key === "string" && r.key &&
              typeof r.stamp === "string" && r.stamp) &&
            new Set(p.target.rows.map(r => r.key)).size === p.target.rows.length) return p;
      } catch { /* 无效缓存不继续删除。 */ }
      cache.remove(pendingKey); return null;
    }
    /** addClickListeners 为可变参数，传入项目实际按钮标识。 */
    registerListener(e: $.java.util.EventObject): void {
      super.registerListener(e);
      this.addClickListeners(c.messageButton, c.errorButton, c.deleteButton);
    }
    /** 新提示替换旧提示；选中行只在发起确认时读取一次。 */
    click(e: $.java.util.EventObject): void {
      super.click(e);
      const key = (e.getSource() as Control).getKey();
      if (key === c.messageButton) {
        this.getView().showMessage("当前单据已加载完成，可以继续录入。"); return;
      }
      if (key === c.errorButton) {
        this.getView().showErrorNotification("当前数据存在未处理异常，请先修正后再继续。"); return;
      }
      if (key !== c.deleteButton) return;
      const cache = this.getView().getPageCache(); cache.remove(pendingKey);
      const target = this.capture(), index = this.getModel().getEntryCurrentRowIndex(c.entry);
      if (!Number.isSafeInteger(index) || index < 0 || index >= target.rows.length) {
        this.getView().showTipNotification("请先选中一行分录。"); return;
      }
      const old = cache.get(seqKey), seq = old == null ? 0 : Number(old);
      if (!Number.isSafeInteger(seq) || seq < 0 || seq >= Number.MAX_SAFE_INTEGER) {
        throw new Error("确认序号无效，请重新打开页面");
      }
      const label = c.entryLabel(this, index);
      const p: MessagePending = { id: c.cachePrefix + ":" + (seq + 1), index, target };
      cache.put(seqKey, String(seq + 1)); cache.put(pendingKey, JSON.stringify(p));
      try {
        this.getView().showConfirm("确认删除分录【" + label + "】吗？",
          MessageBoxOptions.YesNo, new ConfirmCallBackListener(p.id, this));
      } catch (error) { cache.remove(pendingKey); throw error; }
    }
    /** 先匹配并消费本次提示；仅 Yes 继续，焦点切换不改变已绑定目标。 */
    confirmCallBack(e: MessageBoxClosedEvent): void {
      super.confirmCallBack(e);
      const p = this.readPending();
      if (p == null || p.id !== e.getCallBackId()) return;
      this.getView().getPageCache().remove(pendingKey);
      if (e.getResult() !== MessageBoxResult.Yes) {
        this.getView().showTipNotification("已取消删除。"); return;
      }
      if (JSON.stringify(this.capture()) !== JSON.stringify(p.target)) {
        this.getView().showTipNotification("删除对象或内容已变化，请重新选择并确认。"); return;
      }
      this.getModel().deleteEntryRow(c.entry, p.index);
      this.getView().updateView(c.entry);
      const after = this.capture(), expected = p.target.rows.filter((_, i) => i !== p.index);
      if (after.page === p.target.page && JSON.stringify(after.rows) === JSON.stringify(expected)) {
        this.getView().showMessage("分录已从当前页面删除，持久化仍以保存结果为准。");
      } else {
        this.getView().showTipNotification("删除被取消或产生联动变化，请核对分录；未确认删除成功。");
      }
    }
  }();
}
export { createFormMessagePlugin };
```

## 回调与结果边界

- `showConfirm` 异步返回；`ConfirmCallBackListener(id, this)` 对应 `confirmCallBack`。参数为 `MessageBoxClosedEvent`，不是普通页面关闭事件。先核 ID，再比较 `getResult()` 的枚举；只有 `MessageBoxResult.Yes` 删除，No/Cancel及其他结果均不删除，旧 ID 不消费新提示。
- 删除前比较页面与有序分录快照。仅焦点变化仍定位原对象；插入、删除、重排、条件或提示内容变化都要求重新确认。已消费的提示不能再次执行删除；这不等于已验证跨请求并发或平台反重放。
- `deleteEntryRow` 返回 void，前置事件可能取消。调用返回后刷新并核对实际剩余身份/条件快照，再报告当前页面删除结果；后置核对不能撤销其他插件已经重定向的误删。异常继续向上传递，不额外报告成功；持久化仍以保存结果为准。
- 本例的本地离线模型检查不证明 KingScript 引擎、页面缓存恢复、多插件顺序或真实客户端交互通过；目标环境仍需验证这些接入边界。

延伸核验：[云端 KingScript 与 ISCB 运行时边界](https://chatgpt.com/space/page_e22ab958bea4819195a0e5ffd3b154c2)。
