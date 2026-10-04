# 前后端通信与 PC/移动端扩展

以下是通信与扩展入口的候选写法。生成代码前按 `SKILL.md` 核对目标版本及项目中的前端声明、服务端 SDK/脚本声明；前端与服务端两侧分别取证。不能用新版 helper 或本地语法检查通过推定旧目标支持，也不能仅因参考卡出现某个方法就替换现有可用链路。

## 前后端通信

### fetchData(前端 → 服务端)
`fetchData` 与下文 `onCustomMsgEvent` 自 V7.0.2 引入，依据见 [页面脚本版本说明](events-and-api.md)。只有 7.0 大版本信息时不能默认可用；服务端接收签名另按目标 SDK/脚本声明核对。
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
| 就绪判断 | 扩展资源入口与页面 `didMount` 不保证每个控件 DOM 就绪 | 异步加载资源后仍须判断页面/控件就绪 |
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

扩展 JS 的入口、资源加载完成和单个控件就绪是不同阶段；入口仍按目标项目脚手架核对。页面脚本在 PC 和移动端都有懒加载场景，依赖 DOM 时用 `wait()`，树/表格初始化后数据或 DOM 用 `onInit()`。不要把 PC 的 `didMount` 当成所有元素同步可用的保证，具体边界见 [生命周期](events-and-api.md#生命周期)。
