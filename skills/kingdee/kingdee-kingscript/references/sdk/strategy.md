# SDK 检索策略

## 顺序
1. 知识卡：`classes/`、`packages/`、`plugins/`、`microservices/`
2. 索引：`indexes/class-index.md`、`package-index.md`、`module-index.md`、`scenario-index.md`、`keyword-index.md`、`error-index.md`、`plugin-index.md`、`method-index.md`
3. 清单：`manifests/summary.json`、`modules.json`、`packages.json`、`types.json`、`const-exports.json`、`namespaces.json`
4. 本地声明：当前项目的 `.d.ts` 或 SDK 声明文件
5. 官方资料：Javadoc 或开发者文档

## 规则
- 已知类名先走类索引。
- 已知方法名先走方法索引。
- 已知业务场景先走场景索引。
- 已知报错先走错误索引。
- 只读取与目标类、包、方法直接相关的文件。
- 仍不能确认时，明确缺口和推断，不编造 SDK 内容。
