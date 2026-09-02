# 生产实际知识采集合同

## 范围与安全

采集器动态验证元数据库表结构，至少覆盖实体设计、表单设计、主实体、四个多语言/术语侧表、应用上下文和设计引用登记。主范围固定为 `fistemplate='1'`，并读取其可解析祖先闭包。

数据库会话必须：

- 从显式环境配置读取连接信息；
- `metadataAnalyzer.enabled=true`；
- `transaction_read_only=on`；
- 参数化查询和限定 statement timeout；
- 采集结束 rollback 并关闭；
- 不输出密码或连接串。

## 快照完整性

`verify` 必须确认：

- manifest 版本、所有文件 SHA-256 和计数一致；
- 模板编码无重复，所有 fdata 均可解析；
- 完全未解析祖先、未知模板表和缺失应用上下文为零；
- 模型索引覆盖所有模板 ModelType；
- 控件目录计数、完整/差量节点和 profile 自洽；
- 机器知识 payload 哈希全部一致。

缺少中文名是质量警告，不授权自动补名。只有引用登记而无定义的祖先单列 `reference_only`，涉及它的写入阻塞。

## 固化

只有通过 `verify` 的快照才能 `materialize-knowledge`。固化 manifest 保存源快照 manifest SHA-256、采集时间、环境和每个 payload/标准记录哈希。执行器每次加载都重新校验；任一文件被手工改动即拒绝。

快照是不可改写的采集证据，因此 `verify` 可校验快照内当时版本且哈希自洽的派生知识；它不授权旧知识直接参与修改。实际执行前必须用当前脚本从该快照重新运行 `materialize-knowledge`，执行器只接受当前 `knowledge_version`。

环境或平台版本变化后重新采集，不在文档中维护永久控件清单。实际完整目录始终以 `knowledge/<environment>-current` 为准。
