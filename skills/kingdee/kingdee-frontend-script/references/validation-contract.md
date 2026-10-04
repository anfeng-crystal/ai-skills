# 前端脚本与样式校验契约

## 校验入口

```text
python3 scripts/validate_frontend.py <file-or-directory>
python3 scripts/validate_frontend.py <file-or-directory> --kind javascript --format json
```

路径相对 skill 或当前工作目录解析，支持 UTF-8、空格路径和当前平台的路径分隔符；在 POSIX 上也兼容相对路径中的 Windows `\` 分隔符。目录模式只扫描 `.js`、`.jsx` 和 `.css`。

退出码：

- `0`：未命中所列静态模式；若结果为 `partial`，仍需复核未覆盖部分。
- `1`：命中静态模式，结合下述边界核对后修复。
- `2`：输入、编码或参数错误。

## 静态规则与结果边界

| 编号 | 规则 | 修复要求 |
|---|---|---|
| `JS001` | 注册事件但没有同事件名的移除动作 | `didMount` / `willUnmount` 保存并复用同一 handler 引用 |
| `JS002` | 使用 `setInterval` 但没有 `clearInterval` | 保存 timer id，并在卸载时清理 |
| `JS003` | 动态插入 DOM，但没有 `remove` / `removeChild` | 保存节点引用并配对删除 |
| `JS004` | 监听 `message` 但没有读取 `event.origin` 或等价 origin | 使用明确 origin 白名单，不接受 `*` 作为接收校验 |
| `CSS001` | 使用 `@media`、`@keyframes`、`@import` 等 at-rule | 改为平台支持的普通选择器规则 |
| `CSS002` | `$` 后直接接 `.class`、`[attr]` 或 `>` | `$` 与后代/子选择器之间保留空格 |
| `CSS003` | `themeColor` 未使用单引号 | 写成 `'themeColor'` |

`JS001`–`JS004` 是启发式提示，不是 JavaScript/JSX 语法或控制流分析。有界代码视图屏蔽注释、普通字符串、模板静态文本及可判定的正则字面量；事件名作为数据保留，`${...}` 中的代码仍检查，并保留原始行号。普通除法和比较运算不一律拒绝。

遇 JSX、正则/除法语境歧义、动态或未解码的转义事件名、未闭合输入或模板深度超过 32 时，JSON 增加 `analysis: "partial"` 和 `warnings`（`path`、`line`、`reason`）；无 findings 时 `status` 为 `partial`，有 findings 时仍为 `fail`。文本输出 `PARTIAL`，退出码仍按是否命中规则为 0/1。此时合并已扫描代码和原文本线索，可能包含保守误报；按警告位置检查源码，不能把部分分析当作通过。原 `issues` 字段、规则编号、正常 pass/fail 和输入错误退出码不变。

命中时先确认实际执行代码，不能为消除告警添加无效清理；未命中时仍核对注册/移除是否针对同一对象、handler 和定时器，是否在 `willUnmount` 的实际路径中执行，以及消息来源是否真正经过白名单判断。仅出现 `event.origin` 不证明白名单成立。

[官方生命周期](https://vip.kingdee.com/knowledge/588370901079337984?productLineId=29&isKnowledge=2&lang=zh-CN)要求真实释放资源；当前入口、编号及退出码保持不变。[云端知识：版本与误判复现](https://chatgpt.com/space/page_aa00bb99d0488191bb4adecba2b328fe)。

校验器只证明上述静态模式未命中，不证明控件标识、生命周期签名、PC/移动端入口在目标版本可用或目标页面运行正确。helper/模板生成成功同样不是兼容证据；生成接口代码前仍按 `SKILL.md` 使用任务版本和目标声明/SDK/官方适用版本。运行验证仍需设计器/元数据证据和目标页面样本。

## 按改动与模式验证

- 生成或修改 JS/CSS 时运行本地校验器，结合目标合同处理 findings；仅解释 API 或审阅已有结果不为校验新建文件。
- 用到控件/字段标识时，复用已有设计器或 `kingdee-metadata-analyzer` 证据，缺失时再取证。
- 涉及 PC/移动端入口时，用项目脚手架核对；不同版本的 `afterLoaded` / `initKDPlugin` 不能互相套用。
- 已授权目标页面验证时，检查挂载、卸载和重复进入，确认监听器、timer、DOM 和样式没有累积。`author` 模式只报告本地结果和页面未验证状态，不自动进入真实页面。
