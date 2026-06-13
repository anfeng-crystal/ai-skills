# 事件体系与控件 API

## 事件体系

### 生命周期
| 事件 | 时机 | 用途 |
|---|---|---|
| `didMount()` | 单据初始化完成(loaddata 后) | 注册监听、初始化、DOM 操作 |
| `willUnmount()` | 单据关闭销毁 | 清理监听/定时器/手挂 DOM/全局变量 |

### 字段 / 按钮 / 工具栏 / 页签
| 事件 | 时机 | 参数 |
|---|---|---|
| `onValueChange(cb)` | 字段值改变**失焦**时(非实时) | `{ key, newValue, oldValue }` |
| `onClick(cb)` | 按钮点击(锁定时不触发) | `{ key, operationCode }`,分录含 `rowIndex` |
| `onItemClick(cb)` | 工具栏/高级面板/页签按钮点击 | `{ key, operationCode }` 或 `{ operationCode, subTabKey }` |
| `onCustomMsgEvent(cb)` | 自定义控件内 `triggerCustomMsgEvent()` | `{ type, args }`;预置 `__init__` 加载完成 |

### 树控件
`onInit()`(Promise,操作前必须等待)、`onTreeNodeClick`、`onTreeNodeDoubleClick`、`onTreeNodeCheck`(勾选状态 + 节点 id)。

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
