---
name: kingdee-metadata-change
description: "金蝶云苍穹元数据新增、修改、移动、删除或恢复继承时使用。"
license: MIT
metadata:
  author: "anfeng"
  version: "2.4.0"
  tags: "kingdee, cosmic, metadata, authoring, field, control, layout, style, inheritance, rollback"
---

# 苍穹元数据变更
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 职责与边界

处理实体、字段、表单/列表/布局、控件、样式、操作、插件挂载、多语言、术语和继承差量。只读包比较、分析或知识刷新也可使用；本地改包不隐含导入、发布、数据库写入或在线修改授权。

真实对象、字段、入口、挂载及包外引用取证交 `kingdee-metadata-analyzer`；Java 消费者交 `kingdee-cosmic`；页面 JS/CSS 交 `kingdee-frontend-script`；独立 KDApi 控件交 `kingdee-custom-control`；DDL、迁移和数据回填交 `kingdee-sql-and-data`。

## 从需求到交付

1. **确定业务表现与消费者**：先明确页面层级、行列组织、原值、编辑/显隐/必录、按钮和保存返回行为，再选择字段/控件。跨接口、弹窗、分录或字段清理读[字段联动](references/field-integration.md)，合并最新用户口径和已发生的人工修改；不让用户选择 XML 类型、身份值或内部执行格式。
2. **确认可写基线**：`inspect` 定位单元、节点、继承差量及父容器。仅平台直接导出、用户确认原始包或有回导血缘的版本库规范源可作基线；`ai-derived`、`unknown` 或派生产物先补血缘，不能直接再改。
3. **恢复结构合同**：优先可信目标包、同版本同类节点及同环境 `knowledge/<environment>-current`，核对 manifest 与全部 payload 哈希。从包和标准祖先链唯一定位模型、父容器、字段/操作、主实体、多语言/术语。知识缺失可按包内证据制作候选，但必须标出未覆盖检查，不能用异环境知识证明兼容。
4. **选择最小动作**：标量属性 `modify`，只换容器 `move`，完整业务节点 `delete`，去继承覆盖 `restore`。新增按[本地新增](references/local-addition.md)复制同类完整结构、分配新身份并同步引用；不为取每个标识先在线创建节点。
5. **验证候选与引用**：核对节点类型、宿主/页面 `ModelType`、XML/语义父容器、属性值形态、字段绑定、`OperationKey`、主实体与侧表。保留可信原包、最小差异和回滚材料。现有节点可复算补丁；本地新增用 `verify-candidate`，平台导出候选可用 `verify-platform-candidate`；先查 `scripts/metadata_author.py --help`。未覆盖结构按实际合同检查，不把工具限制当平台禁令。
6. **按授权交接**：本地评审副本通过后，已有导入授权就继续核对逐文件结果及入口；用户自己导入则交付到此，收到导入结果后再做已授权的配套部署。失败区分上传、解析、构建和业务阶段，查详情后本地修正。直接在线新增按授权保存、验证即可，除备份/版本管理/交付需要不强制再做本地包。

只有具体结构无法从现有材料确定，或确有平台分配身份要求时，才在授权范围内做最小平台采样。验证通过即完成本轮，不为形式一致反复生成候选。

## 结构规则与按需资料

| 对象 | 规则与资料 |
| --- | --- |
| 身份与引用 | 已有身份不变；新身份核对作用域冲突和全部引用。区分 Key、独立身份、MasterId/oid/ParentId，不统一随机化，不沿用模板独立身份，不把本地生成称为平台分配 |
| modify/move/delete/restore | modify 不改身份/ParentId；move 重验父容器且无循环；delete 无悬空引用；restore 只去业务层继承覆盖 |
| 字段、控件、布局、样式 | 模型间不默认互用；读 `references/field-change-rules.md`、`control-change-rules.md`、`frontend-style-change-rules.md`（均在 references/ 下） |
| 必录、锁定、显隐、允许复制 | 按实际字段/控件能力与需求设置，不按样本交集补全；接口必传、非 null、页面必录和布尔为 true 分开。读 `references/property-applicability.md` |
| 字段与操作绑定 | 字段解析到同业务对象的实际类型；OperationKey 命中实体操作或同模型/节点的已观察标准动作；静态 Visible 不证明运行时可见 |
| 插件挂载 | 必须有 analyzer 的对象、页面/操作和插件身份证据；缺失先取证，不猜类名或挂载文本。读 `references/plugin-change-rules.md` |
| 继承、多语言/术语、主实体、血缘、知识刷新 | 分别读 `references/inheritance-reference.md`、`localization-term-reference.md`、`mainentity-reference.md`、`provenance-and-authoring.md`、`knowledge-base.md`（均在 references/ 下） |

## 输出

用简体中文给出业务改动、目标/血缘、必要结构和绑定依据、候选/回滚位置及实际验证阶段。在线编辑报告实际保存和入口结果。候选已生成、静态通过、已导入、已部署、已验收分别陈述，不能互相代替，也不能把用户已通过的验收退回“待验证”。
