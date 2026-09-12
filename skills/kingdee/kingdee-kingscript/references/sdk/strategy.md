# SDK 检索策略

## 证据与可用入口
以下是资料定位入口，不是必须逐项执行的顺序或版本权威排序。生成或修改代码前，先复用用户已确认产品/目标版本，并用当前工程匹配目标实际版本的 `.d.ts`/SDK 核对本次 API；新版、版本不明或同大版本另一补丁的卡片只作候选，不等冲突才查目标，也不必先穷尽快照。只确认到 `7.0` 时不补成具体补丁或提升到 `8.0`；补丁未知但目标依赖已能确认本次 API 时可继续。目标与依赖不一致时按 `../../SKILL.md` 报告冲突，不以另一版本检查通过替代目标验证。

1. 知识卡：`classes/`、`packages/`、`plugins/`、`microservices/`
2. 索引：`indexes/class-index.md`、`package-index.md`、`module-index.md`、`scenario-index.md`、`keyword-index.md`、`error-index.md`、`plugin-index.md`、`method-index.md`
3. 清单：`manifests/summary.json`、`modules.json`、`packages.json`、`types.json`、`const-exports.json`、`namespaces.json`
4. 本地声明：当前项目的 `.d.ts` 或 SDK 声明文件
5. 官方资料：Javadoc 或开发者文档

## 规则
- 已有具体卡片或目标声明路径时直接读取；位置不明时，类名用类索引、方法名用方法索引、业务场景用场景索引、报错用错误索引。
- 只读取与目标类、包、方法直接相关的文件。
- 仍不能确认时，明确缺口和推断，不编造 SDK 内容。
