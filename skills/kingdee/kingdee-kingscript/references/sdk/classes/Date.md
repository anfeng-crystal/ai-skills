# Date

## 入口与证据

- 脚本入口是全局 `Date`，不是 `java/util` 的命名导出。已核 `@cosmic/bos-script` 的 `index.d.ts`、`java/util.d.ts` 没有 `Date` 导出；编辑器识别全局名不证明 SDK 导出或运行时兼容。
- 引擎 `hotfix_7.0.16_20250730`，Build `202511111000503` 的 `asset/engine/initialize_script.js` 将全局 `Date` 绑定为 `kd.sdk.kingscript.types.builtins.ScriptDate`，后者包装并可解包为 `java.util.Date`。
- 其他目标须核实际引擎与声明；不能将脚本包装、浏览器原生 `Date`、未经包装的 Java `Date` 等同。

## 使用合同

- 用于单据日期、有效期、期间、日期字段范围等场景。先确认输入是脚本日期、Java 日期还是字符串，再处理比较、序列化和字段回写；显示格式不决定运行时类型。
- 保留目标支持的 `new Date(...)`，不因底层为 Java 就虚构导入或套用 Java `Date` 的全部方法语义。
- 日期先用 `compareTo(...)`，或取 `getTime()` 后比较；不直接以对象上的 `<`、`>`、相等运算代替时间值比较。
- `getDay()` 须核目标实现：官方 FAQ 写星期值 1–7，但上述 7.0.16 构件的类级探针返回月内日期（10月4日→4、10月1日→1），不能据 FAQ 或浏览器 JS 的 0–6 直接生成星期映射。页面脚本仍遵循浏览器合同。
- 名称或类型检查通过不等于实际桥接、字段保存或业务日期口径已验证；这些须在任务目标版本与授权范围内验收。

## 短引用

- [官方日期比较问题](https://vip.kingdee.com/knowledge/720682618022532608)，aohailin，2026-07-30。
- [官方 getDay 返回值说明](https://vip.kingdee.com/knowledge/744124133280957184)，aohailin，2026-07-31。两篇均未标最低适用补丁。
- [KingScript 与 ISCB 运行时知识](https://chatgpt.com/space/page_e22ab958bea4819195a0e5ffd3b154c2)保存版本冲突和复核依据；不可访问时仍按本卡与目标证据工作。
