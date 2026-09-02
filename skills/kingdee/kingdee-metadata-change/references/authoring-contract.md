# 执行器内部变更描述

本文件只供 agent 调用执行器时读取。根据用户目标和真实包生成 JSON，不让用户填写、选择类型或确认格式版本；不保存数据库凭据。

加载器自动补入当前内部版本；旧文件若显式声明不兼容版本则拒绝。业务字段如下：

```json
{
  "environment": "prod",
  "baseline_sha256": "<64位哈希>",
  "baseline_provenance": {
    "classification": "platform-exported",
    "evidence": "目标环境、导出时间、导出操作或版本库证据"
  },
  "changes": [
    {
      "action": "modify",
      "target": {
        "kind": "form",
        "number": "业务对象编码",
        "document": "ZIP 内成员路径（仅多成员歧义时）",
        "page_key": "页面 Key（仅多页面歧义时）",
        "node_type": "BarItemAp",
        "locator": {"key": "bar_submit"}
      },
      "set": {"Visible": "init,edit"},
      "unset": []
    }
  ]
}
```

`target.kind` 由实际单元自动决定，可为 `entity/form/entity_l/form_l/entity_term/form_term`。`locator` 只能选一个：`key/id/oid/operation_key/class_name`。`class_name` 只用于插件节点，且仍要求 analyzer 取证；继承差量节点可用 `oid`，但引擎必须在实际祖先链中解析出 Key、属性和父容器；不能人工猜测。

## 血缘分类

可作为离线修改基线的分类只有：

- `platform-exported`：目标平台直接导出；
- `user-confirmed-original`：用户明确确认是未被 agent/脚本修改的原始包，并有具体证据；
- `repository-canonical`：版本库中有平台回导或发布血缘的规范源。

`ai-derived/unknown/derived-candidate` 一律阻塞。`evidence` 不能为空，不能写“看起来正常”“文件在 Downloads”之类循环断言。

## action 语义

| action | 输入 | 允许的结果 |
|---|---|---|
| `modify` | `set/unset` | 只改现有节点标量属性；身份和 ParentId 不变 |
| `move` | `new_parent_id` | 只改 ParentId；新父容器有精确实际 profile 且不成环 |
| `delete` | 无属性变化 | 只移除业务层完整节点；无外部引用 |
| `restore` | 无属性变化 | 只移除 `action=edit/reset/delete` 业务覆盖，使其继续继承 |
| `add` | 平台候选中的唯一目标定位 | 不离线生成；交 `verify-platform-candidate` 验证平台创建结果 |

`modify` 不能携带 `Id/PkId/Key/MasterId/oid/ParentId`。需要改 Key 或重新生成身份时，走平台设计器创建/迁移流程，不能把它伪装成普通属性修改。

插件相关节点（`Plugin`、`Plugins`、`JsPlugins`，或其直接子节点）必须附带：

```json
"plugin_evidence": {
  "source": "kingdee-metadata-analyzer",
  "reference": "目标业务对象、页面/操作和插件身份的只读取证标识"
}
```

执行器只接受该来源且 `reference` 非空；agent 先完成业务对象取证，再生成内部描述。

## 新增平台候选输入

在基础字段之外再记录：

```json
{
  "candidate_sha256": "<平台候选哈希>",
  "candidate_provenance": {
    "classification": "platform-exported",
    "evidence": "同版本 DEV/TEST 设计器创建、保存和直接导出证据"
  }
}
```

每个 `changes[]` 都是 `add`，目标 locator 指向候选中新节点。验证器要求基线不存在该节点、候选存在且唯一、节点为完整定义、精确模型/父容器/字段绑定/操作绑定已观察；移除所有批准新增节点后，其他结构和非元数据成员必须与基线相同。

## 输出和复核

变更描述与候选同属派生产物。保存其 SHA-256、基线/候选 SHA-256、知识库 manifest SHA-256、每个节点的标准祖先链和匹配 profile。任何目标匹配数不是 1、任何属性或绑定无法解析、任何额外结构差异都必须停止。
