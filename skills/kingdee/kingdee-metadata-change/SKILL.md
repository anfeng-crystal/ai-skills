---
name: kingdee-metadata-change
description: "金蝶云苍穹元数据新增、修改、移动、删除或恢复继承时使用。"
license: MIT
metadata:
  author: "anfeng"
  version: "2.3.1"
  tags: "kingdee, cosmic, metadata, authoring, field, control, layout, style, inheritance, rollback"
---

# 苍穹元数据变更
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 触发与路由

- 负责实体、字段、表单/列表/布局、控件、元数据样式、操作、插件挂载、多语言、术语和继承差量的新增、修改、移动、删除与恢复继承。
- 目标业务对象、真实字段/入口、插件挂载和包外引用取证交 `kingdee-metadata-analyzer`；页面扩展 JS/CSS 交 `kingdee-frontend-script`；独立 KDApi 控件交 `kingdee-custom-control`；DDL、数据迁移和回填交 `kingdee-sql-and-data`。
- 只读分析、包比较或模板知识刷新可以在本 skill 内完成；导入、发布、数据库写入和真实环境操作不由本 skill 隐含授权。

## 契约

- 从可信基线和同环境 `knowledge/<environment>-current` 自动恢复实体/表单链、节点类型、模型、父容器、字段与操作绑定、主实体、多语言和术语合同。知识目录的 manifest 和全部 payload 哈希必须有效。
- 默认离线：优先使用可信目标包、同版本同类节点和有效同环境知识。知识缺失时仍可基于包内证据制作本地候选，记录未覆盖的检查；不能冒称脚本已校验或借用另一环境证明兼容性。
- 先判定包血缘。`ai-derived`、`unknown` 和派生产物不能作为可写基线；仅平台直接导出、用户确认原始包或有回导血缘的版本库规范源可继续。
- agent 自行生成并使用执行器内部描述；不让用户选择 XML 节点、身份值、控件目录或内部格式。

## 本地改包工作流

1. `inspect` 基线，定位元数据单元、页面、继承差量和现有节点；遇到业务事实缺口，先取证再继续。
   涉及接口字段、弹窗与分录同步或字段清理时，按 [字段联动与交付](references/field-integration.md) 合并最新已确认口径、在线人工修改及源码消费者。
2. 校验基线血缘与目标环境知识；从目标包和标准祖先链唯一定位节点。
3. 按动作生成候选：已有标量属性用 `modify`；仅更换父容器用 `move`；业务完整节点用 `delete`；继承覆盖用 `restore`；新增默认在本地副本按同类完整节点构造，分配新标识并同步引用，规则见 [本地新增](references/local-addition.md)。
4. 自动校验精确节点类型、宿主/页面 `ModelType`、XML 与语义父容器、属性和值形态、字段绑定、`OperationKey`、主实体映射及侧表合同。
5. 保存可信原包、最小差异、候选与回滚材料。已有节点可用执行器复算补丁；本地新增候选用 `verify-candidate`，平台导出候选仍可用 `verify-platform-candidate`。具体命令先读 `scripts/metadata_author.py --help`；脚本未覆盖的结构按实际合同核查并列出验证缺口，不把工具能力限制解释为平台禁令。
6. 批量变更默认在本地评审副本完成，不为取得每个新字段的标识先在线复制或创建字段。已有导入授权时继续导入、核对逐文件结果并验证目标入口；失败先查详情/日志并在本地修正，验证通过即停止迭代。只有具体结构无法从现有材料确定，或有证据表明目标对象需要平台分配身份时，才在授权范围内做最小平台采样。用户选择直接在线新增时，保存并验证即可；除备份、版本管理或交付需要，不再要求修改本地包。

## 门禁与失败

- 已有身份保持不变；新节点按目标格式生成新身份，校验作用域内冲突及所有引用。不把 `Key`、独立身份和 `MasterId/oid/ParentId` 等关联一律当随机 ID；不沿用模板节点的独立身份，不把本地生成声称为平台分配。
- `modify` 不改身份或 `ParentId`；`move` 必须重新命中父容器合同且无循环；`delete` 不得留下引用；`restore` 只移除业务层继承覆盖。
- 基础资料、单据、列表、动态表单、报表和移动端的控件不默认可互用。字段/控件/列表/布局/样式读取 `references/field-change-rules.md`、`references/control-change-rules.md` 与 `references/frontend-style-change-rules.md`。
- 必录、锁定、显隐、字段允许复制等属性按目标字段/控件的实际能力和本次需求配置，不按样本交集补齐；不支持的属性或状态不写入。接口必填不等于复选框必须勾选；规则见 [属性适用性](references/property-applicability.md)。
- 字段绑定必须解析到同业务对象的实际字段类型；`OperationKey` 必须命中实体操作或同模型、同节点类型的已观察标准表单动作。静态 `Visible` 不能证明运行时可见。
- 插件挂载必须有 `kingdee-metadata-analyzer` 的业务对象、页面/操作和插件身份证据；规则见 `references/plugin-change-rules.md`。没有证据时停止，不把类名或挂载节点当普通文本猜写。
- 继承、多语言/术语、主实体和血缘分别读取 `references/inheritance-reference.md`、`references/localization-term-reference.md`、`references/mainentity-reference.md`、`references/provenance-and-authoring.md`；知识刷新规则见 `references/knowledge-base.md`。

## 输出

本地改包输出目标与动作、基线血缘、实际模型/节点/父容器/绑定合同、候选与回滚文件，以及静态、导入和入口验证结果。直接在线编辑输出实际保存与入口验证结果，不强制生成本地候选。使用简体中文，明确未执行的验证；不得把本地候选表述为已修复或已上线。
