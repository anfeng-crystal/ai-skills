# 可选视觉成果卡

仅在用户需要展示卡片，或批量结果用图卡确有阅读收益时使用。普通修订交付 Markdown 即可，不为每个 Skill 自动生成 HTML/PNG。

## 模板与样式

复用 Skill 根目录下 `templates/result-card.html`；只创建任务产物副本，不覆盖模板。样式由用户选择或沿用已有风格；无偏好时可用 Warm Swiss，不随机切换。

| 风格 | CSS 类 | URL hash |
| --- | --- | --- |
| Warm Swiss | `.theme-swiss` | `#swiss` |
| Dark Terminal | `.theme-terminal` | `#terminal` |
| Newspaper | `.theme-newspaper` | `#newspaper` |

## 生成与验收

- 将 `data-field="skill-name"`、日期和改进摘要替换为实际结果。只有可比的实测评分才填 score-before/after/delta 和维度条；无分数时明确显示未评分，不能编造数据。
- 使用 `scripts/render-result-card.py` 渲染 `.template` 卡片时，可选 `model_set` 沿用评测记录的实际模型信息；未提供、空白或 `null` 显示 `-`，不由模板推定评估模型。
- 需要 PNG 时，使用当前宿主已有的浏览器或截图能力打开本地卡片，待内容和字体就绪后截图。可用 960×1280 作为起点，按内容调整；检查裁切、溢出和可读性。
- 可用 `node scripts/screenshot.mjs <HTML路径> <PNG路径>` 截取 `.card`；相对路径按当前工作目录解析。省略输入时读取模板，省略输出时写当前任务目录的 `result-card.png`。需要指定已有浏览器时设置 `DARWIN_BROWSER_CHANNEL`（如 `chrome`）或 `DARWIN_BROWSER_EXECUTABLE`（优先）；模块解析可用 `DARWIN_PLAYWRIGHT_CANDIDATES`。不自动下载浏览器；`--help` 不加载截图依赖。
- 单 Skill 卡和汇总卡按展示目的选择，不必同时生成。截图能力不可用时交付实际可用的 HTML/Markdown 并说明限制，不把未生成的 PNG 当作产物。
- 沿用模板品牌元素（Darwin.skill、日期、底部品牌文字与项目链接），用户要求其他展示风格时按其选择调整。

交付实际产物路径、评分口径和未验证项，不把视觉形式作为优化效果的证据。
