# Metadata Contract

## 目标

`kingdee-metadata-analyzer` 对外提供稳定 JSON 摘要，供 `kingdee-cosmic`、`kingdee-testing`、`kingdee-security-review` 消费。契约只表达已采集证据，不补写猜测。

## 顶层结构

```json
{
  "entityNumber": "ztjg_example",
  "environment": "dev",
  "forms": [],
  "fields": [],
  "warnings": []
}
```

## Forms

```json
{
  "formId": "MobileBillFormAp",
  "pageType": "mobile-bill",
  "plugins": [
    {
      "className": "com.example.Plugin",
      "pageElement": "form|list|operation|entry",
      "formPage": "edit|view|list",
      "source": "metadata|source|jar"
    }
  ]
}
```

Rules:

- `formId` 优先取 analyzer 的 `formPage` 原值；只有操作插件可使用 `operation:<opKey>`。
- `pageType` 允许值包括 `pc-form`、`mobile-bill`、`mobile-list`、`operation`、`entry`、`unknown`。
- `source` 表达证据来源，不表达可信度打分；可信度和缺口写入 `warnings`。

## Fields

```json
{
  "fieldKey": "field_key",
  "name": "字段名",
  "fieldType": "TextField",
  "entryKey": null,
  "physicalColumn": null,
  "evidence": ["entitydesign"]
}
```

Rules:

- `entryKey`、`physicalColumn` 未确认时必须是 `null`。
- `evidence` 必须是数组，常见值：`entitydesign`、`formdesign`、`source`、`jar`、`cache`。
- 不能把字段标识推断成物理列名。
- `sourceEntity/sourceDepth/inherited_from/action/oid` 存在时原样保留；来自不同设计层的同 Key 候选不自动合并。

## 完整性与来源

- `warnings` 汇集输入原有值，列表元素或非列表值都不转换成猜测的警告格式；原始状态同时保存在 `sourceEvidence.inventory/quickCache`。
- `sourceEvidence` 保留输入的 `warnings/fieldEvidence/complete/completeness/truncated`，不把 false 或未知改成 true。旧字段缓存缺少 `fieldEvidence` 时增加 `field_evidence_status_unknown`，不能由字段非空认定完整。
- `fieldEvidence` 的设计候选、祖先遍历与未解析差量边界见 [字段证据](field-evidence.md)。`--fields` 产生的警告包含差量未解析、设计层未合并、未请求祖先、祖先缺失/无法解析、循环、深度上限和 XML 无效；缓存与摘要均须保留。

## 生成方式

优先使用脚本：

```bash
python3 scripts/metadata_contract.py --inventory <inventory.json> --environment dev --output contract.json
python3 scripts/metadata_contract.py --quick-cache scripts/.metadata_cache/<entity>.json --environment dev
```

`inventory.json` 适合生成插件和页面挂载摘要；quick query cache 适合补字段摘要。两者可同时传入。

## 消费边界

- `kingdee-cosmic` 可用它确认插件入口、字段层级和待确认项后再改代码。
- `kingdee-testing` 可用它生成字段、表单、插件入口相关测试，但不能替代真实运行验证。
- `kingdee-security-review` 可用它确认页面、操作、OpenAPI 或插件入口是否真实挂载，再决定审计或 POC 范围。
