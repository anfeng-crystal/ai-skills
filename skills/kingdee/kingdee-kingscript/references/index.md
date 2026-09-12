# KingScript 资料索引

## 首选入口
- 生成或修改脚本：`references/templates/index.md`
- 插件示例：`references/examples/plugins/index.md`
- SDK 查询：`references/sdk/index.md`、`references/sdk/strategy.md`
- 类名索引：`references/sdk/indexes/class-index.md`
- 方法索引：`references/sdk/indexes/method-index.md`、`references/sdk/indexes/methods-by-name.md`
- 生命周期：`references/sdk/indexes/methods-lifecycle.md`、`references/sdk/indexes/plugin-index.md`
- 场景检索：`references/sdk/indexes/scenario-index.md`、`references/sdk/indexes/keyword-index.md`
- 语法限制：`references/language/kingscript/index.md`

## 查找规则
- 先看当前项目或工作区是否已有同类脚本模块、公共函数、共享工具、SDK wrapper 或模板，再进入本 skill 的 references。
- 已知具体文件或目标声明时直接读取；位置不明时用对应 `index.md` 按类名、方法名、事件名或场景词收敛，不固定经过每一层索引。
- 索引无法命中时，用 `rg` 在 `references/` 内检索。
- 生成或修改代码前按 `sdk/strategy.md` 用目标项目依赖或同版声明/SDK 确认本次 API，不等本地资料不足或出现冲突才核对；已确认目标不随 references 版本改变。
