# 网页实现与验收

## 选用已有组件和 Web 能力

- 在原页面入口定位负责数据、校验、状态和样式的组件。按项目实际版本核对组件 API、主题 token 和现有用法，把确认稿里的字号、间距、表面、主次操作及状态色落实到这些组件。共享样式的修改要检查同一作用域的其他实例。
- 写布局、动效或客户端交互前，先对照 Google Chrome 团队的 `modern-web-guidance`。以单一能力检索，如 `responsive data table`，从匹配描述找到 ID，再用 `retrieve` 读正文。没有 CLI 时可从官方项目查阅指南。结合项目支持的浏览器或 WebView 决定是否采用新能力及其回退方式。[Google 官方使用说明](https://github.com/GoogleChrome/modern-web-guidance/blob/main/skills/modern-web-guidance/SKILL.md) · [官方指南目录](https://github.com/GoogleChrome/modern-web-guidance#the-full-list)
- 把控件接回原有事件、数据、权限和业务处理，在实际入口验证结果。操作等待时给出可见反馈，填写有误时在对应字段保留输入并提示修正。按业务已有分支验证，例如编辑后旧结果过期、快速切换记录或失败重试。

## 在渲染结果中对稿

- **内容与宽度。** 使用确认稿中的真实长度、字体和素材，观察首要对象、图像裁切、对齐及阅读顺序。桌面和窄屏按目标宽度分别操作。对照型数据保留可比列、单位与表头，详情返回后找得到原对象。触屏时检查固定栏、软键盘、末行和弹层是否挡住下一步。
- **输入与状态。** 用键盘走主流程，检查可见焦点、控件的读屏名称和关闭弹层后的焦点归属。触屏能完成约定操作，拖动等精细手势有等价入口。用图标、文字或形状辅助识别选中、告警和错误状态。[Vercel 网页界面检查项](https://github.com/vercel-labs/agent-skills/blob/main/skills/web-design-guidelines/references/command.md)
- **动效。** 按确认稿在同一对象上触发展开、移位、转场或反馈，核对起止状态、方向、节奏及连续操作。遇到较重的图像或滚动效果，在目标设备条件下留意卡顿。启用 `prefers-reduced-motion` 后，仍能判断哪个对象改变、结果是什么。
- **对比度。** 按最终合成的不透明 sRGB 前景、背景检查。WCAG 2.2 AA 普通文字要求至少 4.5∶1，大字（18 pt 常规或 14 pt 粗体起）至少 3∶1，辨认控件和状态所必需的非文字线索通常至少 3∶1。渐变或图片背景检查文字覆盖的最弱位置，禁用态、纯装饰等按条款适用范围判断。可用设计工具测量，也可在 Skill 目录运行 `node scripts/contrast.mjs "#243244" "#FFFFFF"`，传入实际相邻的色值，按未取整的比值判断。[离线计算脚本](../scripts/contrast.mjs) · [W3C 文字对比度](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) · [W3C 非文字对比度](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html)
