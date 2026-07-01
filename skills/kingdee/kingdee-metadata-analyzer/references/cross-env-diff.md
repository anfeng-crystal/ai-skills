# 跨环境差异对比 / 引用检查 / 导出

本卡片定义三类元数据交付能力的口径与执行步骤。证据来源沿用本 skill 的 quick-query / 全景分析产物,不引入新数据库连接方式;路径一律用 `$METADATA_SKILL_ROOT` 与项目显式配置,不写本机绝对路径。

## 一、跨环境 / 跨库差异对比(diff)

### 适用
比较同一实体(或同一应用下实体集)在两个环境/库之间的元数据差异,例如 dev 与 test、改造前与改造后、源编码与目标编码。

### 对比维度(9 类,逐类独立成节)
1. 表单基本信息:MetadataId、EntityKey、ParentId、InheritPath、Name
2. 实体基本信息:MetadataId、父元数据、InheritPath、Name、EntityKey、TableName、是否扩展、Isv
3. 字段定义:Id、字段类型、Key、Name、FieldName(物理列)、MustInput、DefValue、DataScope、BaseEntityId
4. 表单插件:类名、是否继承、oid
5. 列表插件:类名、是否继承、oid
6. 操作定义:Key、Name、OperationType、操作插件列表
7. 权限项:权限 id、权限编码、权限名称
8. 页面规则:前置条件、描述、条件成立/不成立时执行
9. 业务规则:前置条件、描述、来源(form/entity)、条件成立/不成立时执行

### 差异状态模型(每条目标识一项)
- `added`:仅目标侧存在(绿色)。
- `removed`:仅源侧存在(红色)。
- `changed`:两侧都有但属性不同(黄色),必须列出 `changed_attrs`(具体哪些属性变了)。
- `unchanged`:完全一致(默认不展示)。

判定方式:每个维度以稳定 key 建左右两张映射表(字段用 `EntryEntity.Key` 形式区分分录字段,操作用 `Key`,权限用权限 id),对 key 求并集后逐项比较;`changed` 必须落到属性级,不能只说"有变化"。

### 执行步骤(基于本地 analyzer,不新增连接器)
1. 解析源环境与目标环境口径,各自定位到项目显式配置(如 `ok-cosmic.dev.json`、`ok-cosmic.test.json`),不混用环境。
2. 对源、目标分别运行 quick-query(或全景分析)采集同一实体集,产出两份结构化结果。
3. 按上述 9 维逐类对齐 key,套用 `added/removed/changed/unchanged` 状态模型,`changed` 落到属性级。
4. 输出差异摘要(每维 `+a -b ~c`)+ 明细;字段层级、物理列名、环境来源缺证据时标"未确认",不外推。

摘要示例:
```
=== cas_paybill ===
  字段定义: +3 -1 ~2
  操作定义: +1 -0 ~0
  业务规则: +1 -0 ~0
  其余维度: 无差异
```

## 二、基础资料引用检查(check-ref)

### 目的
找出指向"不存在的基础资料实体"的 `BasedataField`,避免运行期引用悬空。

### 规则
1. 仅扫描 `field_type == BasedataField` 的字段。
2. 取 `BaseEntityId`:优先原始 `raw_base_entity_id`;否则从 `名称(编码)` 形式正则提取括号内编码。
3. 跳过最终编码为空的字段。
4. 去重后批量校验(每批 ≤50,参数化查询)其是否存在于 `t_meta_mainentityinfo.fdentityid`。
5. 不存在者记为无效引用,按元数据编码分组输出:字段 Key、字段名、目标 BaseEntityId。

### 输出
```
检查实体: cas_paybill, cas_recbill
❌ 无效引用 2 处:
  [cas_paybill]
    FPayeeId (收款人) → bd_payee_invalid
    FBankId  (银行)   → bd_bank_old
  [cas_recbill] ✅ 通过
```

## 三、导出(Excel / HTML)

### Excel(每个实体一个 xlsx)
按需生成至多 8 个 sheet(无内容的 sheet 跳过):
1. 基本信息(标签-值):元数据 Id、编码、父 Id、继承路径、名称、库表
2. 字段定义(11 列):Id | 字段类型(中文) | Key | 名称 | 物理列 | 是否必录 | 默认值 | 最大长度 | 数据范围 | 基础资料实体 | 库表
3. 表单插件:类名 | 是否继承 | oid
4. 列表插件:类名 | 是否继承 | oid
5. 操作定义:操作编码 | 名称 | 类型 | 是否继承 | oid | 操作插件(换行分隔)
6. 权限:权限 id | 编码 | 名称 | 是否继承
7. 页面规则:前置条件 | 描述 | 成立时执行 | 不成立时执行
8. 业务规则:前置条件 | 描述 | 来源 | 成立时执行 | 不成立时执行

文件名 `名称(编码).xlsx`(非法字符替换为下划线);表头加粗居中、数据行隔行底色、列宽自适应(汉字按 2 宽计)。

### HTML
单文件,含页签切换与按维度过滤,适合离线查看与汇报;数据口径与 Excel 一致。

## 边界
- diff / check-ref / 导出都是"采集后加工",不改变本 skill 的证据等级规则:有警告、截断、层级缺失的输入不能产出确定结论。
- 跨环境结果只代表对应环境;不得用一个环境的差异结论冒充另一个环境的事实。
- 不在输出中写数据库明文密码、主机、内网地址。
