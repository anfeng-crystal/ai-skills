# setWaterMarkInfo - 页面水印内容定制

## 合同

`setWaterMarkInfo(e: $.kd.bos.form.events.LoadWaterMarkInfoEventArgs): void` 接收水印事件；文本和样式需设置到真实 `WaterMark`，再通过 `e.setWaterMark(waterMark)` 回传。没有 `setWaterMarkText`、`setWaterMarkSubText` 或 `setWaterMarkFooter`。

当前已核脚本包只公开水印类型与 setter，构造器导出和插件注册仍需目标证据。初始事件对象的水印可能为空，`super` 不自动初始化；不能用取空后返回的代码冒充创建实现。事件早于正常页面数据使用阶段，也不能假定 `this.getModel()` 已能提供当前单据。

## 合同评审场景

水印保留三项信息：主文本“评审中”，当前登录人和组织显示名，以及业务单号 `billno`，用于截图流转时识别来源。水印文本只有一个 `text` 属性，合并这些信息不等于具备独立副标题和页脚区域。

复用[水印对象 helper](../表单插件.md#50-setwatermarkinfo)中的 `applyReviewWaterMark`。调用方提供已核实的真实水印对象、登录人、组织显示名和单号，明确空值处理与允许展示的内容；不要把基础资料 `org` 当字符串，也不要调用未经声明的 `getContext().getCurrentUserName()`。

对象取得、宿主接线及目标水印配置未完成时，只交付 helper 与实施要求；不宣称完整插件可运行。页面截图、附件预览、下载和打印的覆盖范围分别验证，不因事件存在就保证所有输出均带水印。
