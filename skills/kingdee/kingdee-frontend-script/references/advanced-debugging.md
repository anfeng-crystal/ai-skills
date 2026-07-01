# 高级模式与调试

## React Hooks(仅 Render 函数内)
仅在 `setCellEditor` / `setCellRender` / `setTreeItemRender` 的 Render 函数内可用:`useState` / `useEffect` / `useMemo` / `useCallback`(及 Lodash `_` 做防抖节流)。**禁止在 didMount/willUnmount/export 顶层函数中用 Hooks**。

## this 传入 Render 函数
Render 函数访问不到页面脚本 `this`,约定用参数 `kd_global` 传入:
```javascript
function didMount() {
  this.$('tableId').setCellEditor({
    colId: (props) => myEditor({ ...props, kd_global: this })
  });
}
export function myEditor(props) {
  const { kd_global, value, updateEditValue } = props;
  const onClick = () => kd_global.fetchData('method', {}).then(r => {});
  return <button onClick={onClick}>操作</button>;
}
```

## iframe / postMessage
用 `export var` 保存 handler 引用,`didMount`/`willUnmount` 配对 add/remove,并做 origin 白名单校验:
```javascript
export var __messageHandler__ = null;
function didMount() {
  this.__messageHandler__ = (event) => {
    if (!allowedOrigins.includes(event.origin)) return; // 安全关键
    /* 处理 */
  };
  window.addEventListener('message', this.__messageHandler__);
}
function willUnmount() {
  window.removeEventListener('message', this.__messageHandler__);
  this.__messageHandler__ = null;
}
```

## 调试
- `debugger` 断点;`console.log()`(日志右侧链接可定位脚本)。
- 单据初始化前在 Console 执行 `window.show_ps_init = true`,脚本初始化时输出固定 log。

## 脚本不生效排查
1. Console 看 `getPageJs.do` 请求是否发出、响应是否正常(JSON 含 JS)。
2. 前端有缓存,脚本无变化不重复请求 → 手动清缓存。
3. debugger / console.log 定位。
4. 设计器中控件标识与脚本是否一致。
5. 嵌套回调是否用了箭头函数(否则 `this` 丢失)。
