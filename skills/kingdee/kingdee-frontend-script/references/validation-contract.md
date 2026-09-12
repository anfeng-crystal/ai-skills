# 前端脚本与样式校验契约

## 校验入口

```text
python3 scripts/validate_frontend.py <file-or-directory>
python3 scripts/validate_frontend.py <file-or-directory> --kind javascript --format json
```

路径相对 skill 或当前工作目录解析，支持 UTF-8、空格路径和当前平台的路径分隔符；在 POSIX 上也兼容相对路径中的 Windows `\` 分隔符。目录模式只扫描 `.js`、`.jsx` 和 `.css`。

退出码：

- `0`：未命中确定性规则。
- `1`：命中需修复规则。
- `2`：输入、编码或参数错误。

## 确定性规则

| 编号 | 规则 | 修复要求 |
|---|---|---|
| `JS001` | 注册事件但没有同事件名的移除动作 | `didMount` / `willUnmount` 保存并复用同一 handler 引用 |
| `JS002` | 使用 `setInterval` 但没有 `clearInterval` | 保存 timer id，并在卸载时清理 |
| `JS003` | 动态插入 DOM，但没有 `remove` / `removeChild` | 保存节点引用并配对删除 |
| `JS004` | 监听 `message` 但没有读取 `event.origin` 或等价 origin | 使用明确 origin 白名单，不接受 `*` 作为接收校验 |
| `CSS001` | 使用 `@media`、`@keyframes`、`@import` 等 at-rule | 改为平台支持的普通选择器规则 |
| `CSS002` | `$` 后直接接 `.class`、`[attr]` 或 `>` | `$` 与后代/子选择器之间保留空格 |
| `CSS003` | `themeColor` 未使用单引号 | 写成 `'themeColor'` |

校验器只证明上述静态模式未命中，不证明控件标识、生命周期签名、PC/移动端入口在目标版本可用或目标页面运行正确。helper/模板生成成功同样不是兼容证据；生成接口代码前仍按 `SKILL.md` 使用任务版本和目标声明/SDK/官方适用版本。运行验证仍需设计器/元数据证据和目标页面样本。

## 按改动与模式验证

- 生成或修改 JS/CSS 时运行本地校验器，结合目标合同处理 findings；仅解释 API 或审阅已有结果不为校验新建文件。
- 用到控件/字段标识时，复用已有设计器或 `kingdee-metadata-analyzer` 证据，缺失时再取证。
- 涉及 PC/移动端入口时，用项目脚手架核对；不同版本的 `afterLoaded` / `initKDPlugin` 不能互相套用。
- 已授权目标页面验证时，检查挂载、卸载和重复进入，确认监听器、timer、DOM 和样式没有累积。`author` 模式只报告本地结果和页面未验证状态，不自动进入真实页面。
