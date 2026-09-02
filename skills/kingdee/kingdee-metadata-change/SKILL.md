---
name: kingdee-metadata-change
description: "金蝶云苍穹元数据新增、修改、移动、删除或恢复继承时使用。"
license: MIT
metadata:
  author: "anfeng"
  version: "2.2.0"
  tags: "kingdee, cosmic, metadata, authoring, field, control, layout, style, inheritance, rollback"
---

# 苍穹元数据变更

## 触发与路由

- 负责实体、字段、表单/列表/布局、控件、元数据样式、操作、插件挂载、多语言、术语和继承差量的新增、修改、移动、删除与恢复继承。
- 目标业务对象、真实字段/入口、插件挂载和包外引用取证交 `kingdee-metadata-analyzer`；页面扩展 JS/CSS 交 `kingdee-frontend-script`；独立 KDApi 控件交 `kingdee-custom-control`；DDL、数据迁移和回填交 `kingdee-sql-and-data`。
- 只读分析、包比较或模板知识刷新可以在本 skill 内完成；导入、发布、数据库写入和真实环境操作不由本 skill 隐含授权。

## 契约

- 从可信基线和同环境 `knowledge/<environment>-current` 自动恢复实体/表单链、节点类型、模型、父容器、字段与操作绑定、主实体、多语言和术语合同。知识目录的 manifest 和全部 payload 哈希必须有效。
- 默认离线：同环境知识有效时不连接数据库。知识缺失时仍可检查包和生成审查项；需要类型、身份、父容器或绑定合同的写入必须阻塞，不得借用另一环境或猜测补齐。
- 先判定包血缘。`ai-derived`、`unknown` 和派生产物不能作为可写基线；仅平台直接导出、用户确认原始包或有回导血缘的版本库规范源可继续。
- agent 自行生成并使用执行器内部描述；不让用户选择 XML 节点、身份值、控件目录或内部格式。

## 工作流

1. `inspect` 基线，定位元数据单元、页面、继承差量和现有节点；遇到业务事实缺口，先取证再继续。
2. 校验基线血缘与目标环境知识；从目标包和标准祖先链唯一定位节点。
3. 按动作生成候选：已有标量属性用 `modify`；仅更换父容器用 `move`；业务完整节点用 `delete`；继承覆盖用 `restore`；新增只验证同版本平台设计器创建并导出的候选。
4. 自动校验精确节点类型、宿主/页面 `ModelType`、XML 与语义父容器、属性和值形态、字段绑定、`OperationKey`、主实体映射及侧表合同。
5. 生成最小字节补丁、候选与回滚包；再以基线和内部描述复算候选。具体命令先读 `scripts/metadata_author.py --help`。

## 门禁与失败

- 不复制或伪造 `Id`、`PkId`、`Key`、`MasterId`、`oid` 或平台生成的多语言身份；离线 `add` 一律阻塞。
- `modify` 不改身份或 `ParentId`；`move` 必须重新命中父容器合同且无循环；`delete` 不得留下引用；`restore` 只移除业务层继承覆盖。
- 基础资料、单据、列表、动态表单、报表和移动端的控件不默认可互用。字段/控件/列表/布局/样式读取 `references/field-change-rules.md`、`references/control-change-rules.md` 与 `references/frontend-style-change-rules.md`。
- 字段绑定必须解析到同业务对象的实际字段类型；`OperationKey` 必须命中实体操作或同模型、同节点类型的已观察标准表单动作。静态 `Visible` 不能证明运行时可见。
- 插件挂载必须有 `kingdee-metadata-analyzer` 的业务对象、页面/操作和插件身份证据；规则见 `references/plugin-change-rules.md`。没有证据时停止，不把类名或挂载节点当普通文本猜写。
- 继承、多语言/术语、主实体和血缘分别读取 `references/inheritance-reference.md`、`references/localization-term-reference.md`、`references/mainentity-reference.md`、`references/provenance-and-authoring.md`；知识刷新规则见 `references/knowledge-base.md`。

## 输出

使用简体中文输出：目标与动作 → 基线血缘 → 命中的实际模型/节点/父容器/绑定合同 → 最小候选与回滚文件 → 静态验证结果 → 未执行的平台回导、入口运行或发布验证。不得把本地候选表述为已修复或已上线。
