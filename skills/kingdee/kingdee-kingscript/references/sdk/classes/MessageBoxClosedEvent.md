# MessageBoxClosedEvent

## 基本信息

- 名称：`MessageBoxClosedEvent`
- Java 类名：`kd.bos.form.events.MessageBoxClosedEvent`
- TS 导出名：`MessageBoxClosedEvent`
- 所属模块：`@cosmic/bos-core`
- 所属包：`kd/bos/form`
- 命名空间：`kd.bos.form.events`
- 类型：消息框 / 确认框关闭回调事件参数
- 来源：
  - SDK 清单：`references/sdk/manifests/types.json`
  - 示例：`references/examples/plugins/插件示例/表单插件-场景拆分/showMessagesAndConfirmCallback.md`

## 用途概述

用于承接 `showConfirm`、`confirmCallBack`、`messageBoxClosed` 的确认结果，是消息框交互回调最直接的参数对象。

## 典型场景

- 在 `confirmCallBack(e: MessageBoxClosedEvent)` 里按 `callBackId` 分流
- 在 `messageBoxClosed(e: MessageBoxClosedEvent)` 里判断用户是否确认
- 根据 `getResult()` 决定继续删除、提交、关闭或仅提示

## 高价值规则

- 它属于消息框 / 确认框回调，不是子页面关闭回调
- 如果是 `showConfirm` 的结果，先看这里，不要误用 `ClosedCallBackEvent` 或 `BillClosedCallBackEvent`
- `callBackId` 要与 `ConfirmCallBackListener` 里传入的标识保持一致

## 运行时注意事项

- `showConfirm` 是异步交互，结果不会在发起方法里同步返回
- 先判断 `callBackId`，再处理 `result` 和后续数据修改
- 如果回调没有进入，先检查 `showConfirm` 是否传入了有效的回调监听器

## 相关文档

- [IFormView.md](IFormView.md)
- [ClosedCallBackEvent.md](ClosedCallBackEvent.md)
- [BillClosedCallBackEvent.md](BillClosedCallBackEvent.md)
- [showMessagesAndConfirmCallback.md](../../examples/plugins/插件示例/表单插件-场景拆分/showMessagesAndConfirmCallback.md)

## 关键词

- 中文关键词：确认框回调、消息框关闭事件、确认结果事件
- 英文关键词：`MessageBoxClosedEvent`
- 常见报错词：确认框回调不进、确认结果为空、回调 ID 不匹配
