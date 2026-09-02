# 实际元数据知识库

知识库是本 skill 的本地判定数据，不是用户步骤。日常修改不连接数据库；执行器直接加载同环境 `knowledge/<environment>-current` 并校验全部哈希。

## 可用性决策

1. 同环境 current 有效：离线继续，不探测数据库。
2. current 缺失但有已验证同环境快照：从快照本地重新固化，不连接数据库。
3. 两者都没有：仍可 inspect、比较和收集包内证据；模型、父容器、身份或绑定证据不足的写入阻塞。
4. 只有在知识确需刷新且已获得只读访问授权时才连接元数据库。不得用其他环境知识替代。

## 刷新来源

每个环境从元数据库只读事务采集：

- `t_meta_entitydesign`、`t_meta_formdesign` 的全部 `fistemplate='1'` 记录及可解析祖先闭包；
- `t_meta_mainentityinfo` 的全部模板行；
- 实体/表单 `_l` 和 `_term` 侧表；
- 设计引用登记、应用上下文和数据库结构发现结果。

范围由数据库字段和 `fistemplate='1'` 决定，不用 `bos_` 前缀、名称或开发平台分页结果猜模板。连接强制 `transaction_read_only=on`，采集后回滚并关闭连接。

## 固化文件

`knowledge/<environment>-current/` 包含：

| 文件 | 执行时用途 |
|---|---|
| `manifest.json` | 环境、快照时间、来源哈希、全部 payload/标准记录哈希和计数 |
| `entity-types.json` | 实体节点、模型、XML 父节点、属性、值形态、子节点顺序和实例 |
| `form-types.json` | 表单/列表/布局结构节点的同类合同 |
| `control-types.json` | 实际控件类型、功能族、宿主模型、页面模型、语义父容器、属性和值形态 |
| `model-matrix.json` | 每种 `ModelType` 实际出现的实体/表单节点集合 |
| `binding-matrix.json` | 实体字段—控件绑定、实体操作—表单节点绑定，以及无实体操作定义但实际存在的标准表单动作 |
| `identity-contracts.json` | 每类节点在各模型/父节点下的实际身份属性；身份生成状态单独记录 |
| `mainentity-contract.json` | 主实体实际列、值形态和各模型非空列 |
| `localization-term-contracts.json` | 四个 `_l/_term` 侧表的实际列、locale 和行形态 |
| `standard-entity/form*.jsonl.gz` | 精确祖先 XML、侧表和哈希，用于解析继承差量 |
| `standard-reference-registry.jsonl.gz` | 只有登记、没有定义内容的祖先；命中时阻塞写入 |

类型目录不是手写白名单。平台升级、模板变化或目标环境改变后必须重采；不能把另一环境的目录当当前环境合同。

## 自动判定顺序

1. 按业务单元 `kind + number + document` 唯一定位。
2. 从实际 `InheritPath/ParentId` 按 `fid` 加载实体链或表单链；近祖先覆盖远祖先。
3. 用 `Key/Id/oid/OperationKey` 唯一定位节点并还原有效属性。
4. 实体/普通结构查“kind + ModelType + XML 父节点” profile。
5. 控件再查“控件类型 + 宿主 ModelType + 页面 ModelType + 语义父容器” profile；基础资料、单据、列表、移动端和报表互不默认兼容。
6. 控件字段绑定查同业务对象字段类型及 `binding-matrix`，不能只验证字段名存在。
7. `OperationKey` 先查表单 `EntityId` 对应实体及其继承链中的 `Operations/Operation/Key`；找不到实体操作时，只接受 `binding-matrix` 中同模型、同节点类型、同操作键的实际标准表单动作。
8. 修改值检查属性实际值形态；插入新属性按实际子节点顺序定位。
9. 新增平台候选检查精确身份合同；数据库终态只证明身份字段存在，不证明 agent 能生成身份。

## 内部查询命令

这些命令供 agent 解释阻塞或审查知识，不替代执行器自动判定：

```bash
python3 scripts/metadata_knowledge.py verify-knowledge <knowledge-dir>
python3 scripts/metadata_knowledge.py model-show <knowledge-dir> BillFormModel
python3 scripts/metadata_knowledge.py schema-show <knowledge-dir> \
  --kind entity --node-type TextField --model-type BillFormModel --parent-type Fields
python3 scripts/metadata_knowledge.py schema-show <knowledge-dir> \
  --kind control --node-type BarItemAp --model-type BillFormModel \
  --page-model-type BillFormModel --parent-type ToolbarAp
python3 scripts/metadata_knowledge.py binding-show <knowledge-dir> \
  --model-type BillFormModel --field-type TextField \
  --control-type ListColumnAp --binding-property ListFieldId
python3 scripts/metadata_knowledge.py operation-show <knowledge-dir> \
  --model-type BillFormModel --operation-type Operation \
  --control-type BarItemAp --operation-key submit
python3 scripts/metadata_knowledge.py side-show <knowledge-dir> form_l
python3 scripts/metadata_knowledge.py mainentity-show <knowledge-dir> --model-type BillFormModel
```

`status=observed` 只表示目标环境标准模板中有实际完整实例；业务需求、基线血缘、平台身份、权限和运行结果仍分别验证。`unsupported` 表示不能由 agent 生成；已在可信业务包中合法存在的自定义节点可保留，但新增属性或移动仍需精确证据。

## 只读刷新

```bash
python3 scripts/bootstrap-python-env.py -- scripts/metadata_knowledge.py snapshot \
  --config <environment-config.json> --environment <environment>
python3 scripts/metadata_knowledge.py verify <snapshot-dir>
python3 scripts/metadata_knowledge.py materialize-knowledge <snapshot-dir> \
  --output knowledge/<environment>-current --overwrite
python3 scripts/metadata_knowledge.py verify-knowledge \
  knowledge/<environment>-current
```

刷新只允许目标环境只读数据库访问。`materialize-knowledge` 是本地生成文件更新，不是数据库写入。快照有重复编码、无效 XML、未解析祖先、未知模板表、缺失应用上下文或哈希错误时不得固化。
