# Dynamic SPA Pattern

## 适用信号
- 首屏 HTML 很空，内容靠前端请求填充
- 切换 tab、滚动、展开面板后才出现关键内容
- 页面 URL 不变，但 DOM 或数据源持续变化

## 首选入口
- 先用宿主浏览器能力或当前页面观察 DOM 变化
- 再用 CDP 抓 target、DOM、快照和必要的单次读取命令
- 只有 DOM/快照不足时，才启用 `Runtime.evaluate --allow-unsafe`

## 最小步骤
1. 确认目标页面、首屏状态和触发条件。
2. 找关键线索：接口请求、分页参数、懒加载入口、选项卡切换。
3. 先做只读提取：`DOM.getDocument`、`Page.captureSnapshot`、`/json/list`。
4. 需要页面脚本时，先 dry-run，再实际发送高风险命令。
5. 每次页面发生明显变化后，重新确认 target 和证据，不沿用旧结论。

## 证据记录
- 触发条件：滚动、点击、切 tab、时间等待或请求完成
- 抓到的是 DOM、快照还是脚本执行结果
- 关键信息是否稳定复现

## 风险 / 停问
- 旧 target、旧 DOM、旧 selector 可能失效
- 页面自动刷新或 websocket 推送会让证据过期
- 如果必须连续复杂交互，考虑切 Playwright 或宿主电脑操作能力
