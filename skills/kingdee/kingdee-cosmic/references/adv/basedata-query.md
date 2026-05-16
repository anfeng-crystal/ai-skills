# 基础资料查询

## 适用场景
- 需要按编码、名称或用户给定关键字确认基础资料单条数据。
- 需要从业务字段的 `refType` 推导真实基础资料实体标识。
- 需要在生成代码前确认基础资料编码、名称、主键或关键字段口径。

## 前置条件
- 项目根目录存在 `ok-cosmic.json`。
- `basedata.apiUrl` 已配置，或运行环境提供脚本支持的基础资料查询环境变量。
- `entityId` 必须来自用户明确给出的英文标识、元数据字段 `refType`、项目源码或可靠资料。

## 固定规则
- 不按中文名称、相近单据名或经验猜测 `entityId`。
- `entityId` 不确定时，先用 `scripts/cosmic-form-metadata.py` 查询字段 `refType`，或按基础资料中文名称确认真实英文标识。
- 查询结果只作为事实依据；写代码时仍按当前项目规则、字段类型和平台 API 约束处理。
- 查询失败、超时或未配置在线地址时，不编造数据结构；只说明缺少可用依据。

## 推荐命令
```bash
python3 scripts/cosmic-form-metadata.py --config ok-cosmic.json get --bill-name "物料"
python3 scripts/cosmic-form-metadata.py --config ok-cosmic.json get --form-id <form-id> --fuzzy <field-keyword>
python3 scripts/cosmic-basedata-query.py --config ok-cosmic.json get --entity-id <entity-id> --number-or-name <number-or-name>
```

## 失败条件
- `basedata.apiUrl` 为空且无可用环境变量。
- `entityId` 来源不明确。
- 查询接口返回超时、鉴权失败、租户不匹配或数据不存在。
- 查询结果无法覆盖当前字段、组织、租户或权限场景。
