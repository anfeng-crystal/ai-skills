# 动态对象处理入口

详细知识与证据边界见 [云端动态对象知识](https://chatgpt.com/space/page_6dc95317103c8191a16c59507f9dfa31)。

`DynamicObject` 是内存数据包。先确认当前项目是否提供 `kd.cd.common.util.DynamicObjectUtils` 及其版本，再选择对应合同；项目封装不等于所有苍穹安装都具备的原生 API。

- [项目包装、批量提取、克隆、序列化与状态](adv/dynamic-object.md)：包含已核方法、完整示例，以及 safe/nullSafe、clearDirty、集合引用的边界。
- [原生 DynamicObject 合同](base/sdk/sdk-dynamic-object.md)：字段存在性、实际类型、数值 null/零/默认值、页面模型与数据包读写。
- [实体元数据](adv/entity-metadata.md)：模型、属性与字段结构依据。
- [查询与 DataSet](adv/query-dataset.md)：查询构建、投影和数据集处理。

已确认可用的项目封装应复用；不要因其不在原生 SDK 中而认定不存在，也不能靠 safe 方法隐藏错误字段。只有明确跨版本兼容需求、且至少一个受支持环境真实存在该字段时才可条件写；否则先区分外部值是查询参数还是持久化字段，并确认精确编码体系及真实 F7/业务字段。缺失的查询投影、虚构字段与合法空值必须分别处理。
