# 事件体系与控件 API

官方依据：[前端页面脚本扩展](https://vip.kingdee.com/knowledge/588370901079337984?productLineId=29&isKnowledge=2&lang=zh-CN)（帮助中心，更新于 2026-04-25）。版本表：V7.0.1 引入页面脚本；V7.0.2 增加 `fetchData`、`onCustomMsgEvent`；V7.0.3 增加标准点击事件及树/表格自定义渲染；V7.0.4 增加树/表格若干事件和功能接口；V7.0.11 增加渲染参数 `originValue`。版本表对 V7.0.4 使用分组说明，不能据此断言每个方法的首次引入补丁，也不能因 V7.0.3 支持渲染就推定 `onInit` / `getGridState` 等全部存在。以下能力仍须匹配目标版本，不外推到服务端插件或独立 KDApi 控件。

正文“注意事项”确认页面脚本不能改锁定性、可见性、必录、标识、类型；基础资料字段须服务端先赋值再刷新前端。V8.0.3 修复的是 `setValue` 给处于锁定状态的字段赋值失败，不代表开放修改锁定属性。`createStyle` 的作用域限当前单据且卸载自动移除；这不能证明设计器自定义 CSS 对 at-rules 的支持情况。

本页列出名称不等于目标已支持。生成/修改调用时执行 `SKILL.md` 的目标版本检查；同一份已确认的目标声明可覆盖多个 API，不逐项向用户确认。内置示例不能补足未知补丁或把 7.0 目标提升为 8.0。

## 事件体系

### 生命周期
| 事件 | 时机 | 用途 |
|---|---|---|
| `didMount()` | 单据初始化完成(loaddata 后) | 注册监听、初始化、DOM 操作 |
| `willUnmount()` | 单据关闭销毁 | 清理监听/定时器/手挂 DOM/全局变量 |

`didMount` 表示单据业务数据加载后的脚本初始化，不保证所有控件 DOM 已挂载。PC 和移动端都可能遇到容器懒加载或复杂控件仍在初始化。依赖普通控件 DOM 时用 `this.$('控件标识').wait().then(dom => ...)`；依赖树/表格初始化后数据或 DOM 时用其 `onInit().then(...)`。`getElement()` 仍可能为空，固定延迟不能证明已就绪。官方正文第十二章问题 2 说明了这些边界。

渲染器、事件等配置注册与读取初始化后状态分开判断；官方示例允许在 `didMount` 注册 `setCellRender` / `setCellEditor`，不因使用表格就强制把全部配置移到 `onInit` 后。异步就绪回调若要加监听、定时器或 DOM，应保存当前页面的卸载状态，在回调中检查，并在 `willUnmount` 标记卸载、清理已创建资源，避免页面先关闭后回调再挂载。

### 字段 / 按钮 / 工具栏 / 页签
| 事件 | 时机 | 参数 |
|---|---|---|
| `onValueChange(cb)` | 字段值改变**失焦**时(非实时) | `{ key, newValue, oldValue }` |
| `onClick(cb)` | 按钮点击(锁定时不触发) | `{ key, operationCode }`,分录含 `rowIndex` |
| `onItemClick(cb)` | 工具栏/高级面板/页签按钮点击 | `{ key, operationCode }` 或 `{ operationCode, subTabKey }` |
| `onCustomMsgEvent(cb)` | 自定义控件内 `triggerCustomMsgEvent()` | 消息结构按控件约定；官方预置消息示例为 `{key, args:{type:'__init__'}}`，只表示 `init` 返回，DOM 可能尚未完成。不能把普通消息的 `{type,args}` 概述直接套到预置事件 |

### 按钮锁定与原生 DOM 事件

需要遵守按钮锁定状态的点击逻辑，目标支持时使用标准 `onClick`（V7.0.3 起），工具栏用 `onItemClick`。原生 `on('click', handler)` 不与控件内部状态联动，按钮锁定后仍可能触发；两种监听不能按同一行为替换。依据为上述官方正文的按钮/工具栏事件说明及“注意事项”第 4 项。

确需使用原生 DOM 事件时，在每次回调执行时读取对应控件的 `isEditable()`，不可编辑就返回；不要只在 `didMount` 注册时读取一次，因为页面状态可能随后变化。保留同一 handler 引用，并在 `willUnmount` 用 `off` 移除。前端状态判断只负责交互，服务端原有权限和业务校验仍须保留；同一次点击也不要重复绑定标准与原生监听来执行同一动作。

### 树控件
`onInit()`(Promise,读取初始化后数据/DOM 前等待)、`onTreeNodeClick`、`onTreeNodeDoubleClick`、`onTreeNodeCheck`(勾选状态 + 节点 id)。

### 表格控件
`onInit()`(Promise)、`onTableRowClick`、`onTableRowDoubleClick`、`onCellValueChange`(行/列/新值,联动)、`onSelect`/`onUnSelect`(行索引数组)、`onSelectAll`/`onUnSelectAll`。

## 7 类控件 API

1. **通用控件**:`set('属性', 值)` / `get('属性')` / `isEditable()` / `isVisible()`。注:`set` 可被服务端覆盖;锁定性/可见性/必录/标识/类型不支持脚本改。
2. **字段**:`setValue(v)`(基础资料无效,需服务端赋值)/ `getValue()`(基础资料返回不可变对象,需 `.toJS()`)/ `isRequired()`。
3. **表单**:`this.getFormConfig()` / `getFormMeta()` / `getFormStatus()`(0 新增/1 修改/2 查看/4 提交/5 审核)/ `this.fetchData(方法, 参数)`(Promise)。
4. **DOM 操作**:`on('事件', [子选择器], cb)`(focus/blur 用 focusin/focusout)/ `off('事件', cb)`(同引用)/ `getElement()`(可能空)/ `wait().then(dom)`(适合 didMount)/ `css({...})`。
5. **工具类**:`this.utils.loadFiles([url])` / `showMessage(内容,{type,duration})`(type 0 成功/1 错误/2 警告)/ `createStyle(css)`(作用域限单据,卸载自动清)/ `loadArtTemplate()`。
6. **树接口**:`expand/collapse(id)`、`checkNodes/uncheckNodes([id])`、`getNode/getParent/getAllParent(id)`、`getTreeData/getTreeState()`、`setTreeItemRender(Fn)`(支持 React 16.8 Hooks)。
7. **表格接口**:`setCellValue([{k,r,v}])`、`setCellStyle([{k,r,s:{bc,fc,fs}}])`、`setRowStyle([{r:[行],s}])`、`setSelectRows(n|[n])`、`getRowData(行)/getGridData()/getGridState()/getFocusedCell()`、`setCellRender(Fn|{列:Fn})`(查看态,props 含 value/originValue/record/rowIndex)、`setCellEditor({列:Fn})`(编辑态,props 含 value/updateEditValue/Editor)。
