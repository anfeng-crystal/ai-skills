# 前后端通信与 PC/移动端扩展

以下是通信与扩展入口的候选写法。生成代码前按 `SKILL.md` 核对目标版本及项目中的前端声明、服务端 SDK/脚本声明；前端与服务端两侧分别取证。不能用新版 helper 或本地语法检查通过推定旧目标支持，也不能仅因参考卡出现某个方法就替换现有可用链路。

## 前后端通信

### fetchData(前端 → 服务端)
```javascript
this.fetchData('方法名', { 参数 }).then((result) => { /* 服务端返回 */ });
```
服务端(KS 脚本)处理:
```javascript
customEvent(e) {
  const key = e.getKey();          // 固定 '__clientRequest__'
  const name = e.getEventName();   // 对应 fetchData 方法名
  const args = e.getEventArgs();   // 对应 fetchData 参数
  if (key === '__clientRequest__' && name === 'getUserInfo') {
    this.getView().getClientProxy().addAction('setPageJSData', {
      name: 'userInfo', args: { userName: 'demo' } // 前端 result 接收
    });
  }
}
```

### 自定义控件通信
- 页面脚本 → 控件:`this.$('ctrlId').invoke('method', { data })`,控件内 `handleDirective(props, method, arg)` 接收。
- 控件 → 页面脚本:页面 `this.$('ctrlId').onCustomMsgEvent((data)=>{ /* {type,args} */ })`;控件 `this.model.triggerCustomMsgEvent('type', {...})`。

## PC vs 移动端扩展(扩展 JS)

| | PC 端 | 移动端 |
|---|---|---|
| 入口 | `window.afterLoaded(cb)` / `window.KDPluginExtend` | `window.initKDPlugin()` + `loadjs(script, cb)` |
| 执行 | 同步,didMount 时元素已就绪 | 异步加载,需 `onInit()` Promise 等控件就绪 |
| 判环境 | — | 检测 `window.initKDPlugin` 是否存在 |

```javascript
window.afterLoaded = function (cb) { cb(); };           // PC 就绪
window.KDPluginExtend = {
  didMount: function (context) { /* context 等同页面脚本 this */ },
  willUnmount: function (context) { /* 清理 */ }
};
window.initKDPlugin = function () {                      // 移动端
  loadjs('/path/to/script.js', function () { /* 加载完成 */ });
};
```

页面脚本(单据脚本编辑器内)入口为 `didMount()` / `willUnmount()`,`this` 直接指向页面脚本上下文。
