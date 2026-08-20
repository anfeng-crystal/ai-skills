# 外发字段契约与真实测试报文

服务流程向外部接口发送字段，或用户要求按字段释义生成测试报文时，使用本卡片。目标是让 DTS 映射、请求 JSON 和字段来源清单共享同一份可验证契约。

## 证据优先级

按以下顺序确定当前契约；高优先级证据变化时，低优先级产物立即失效：

1. 用户当前明确纠正和最新外部字段说明、接口 schema 或数据字典。
2. 目标接口的可验证类型/错误响应和当前环境元数据。
3. 当前 DTS 中已有映射。
4. 历史测试报文或旧说明，只能作对照。

不要从英文字段名猜编码体系，也不要把“组织字段”“基础资料字段”统一处理。逐字段记录：目标 key、JSON 类型、语义表示、精确编码体系、源字段/关联资料、缺值策略和证据来源。例如 `unified_identity_code` 与 `administrative_org_number` 都属于字符串编码，但不能互换；省市名称可能是文本，而其它地域字段可能要求编码。

## 同步工作流

1. 从最新字段说明生成 contract，先确认字段全集、大小写、必填项、JSON 类型和 `semantic_type`。
2. 对照当前 DTS，列出 missing、extra、类型不符和语义来源不符；用户要求修复时，同步修改 DTS，不得只修测试 JSON。
3. 生成 payload 后为每个字段记录 provenance。用户要求真实生产数据时，只允许：
   - `production_record`：目标生产业务记录的真实值；
   - `production_master_data`：从已验证关联基础资料取得的真实值；
   - `verified_constant`：只有 contract 明确声明固定常量时使用。
4. 源记录缺值或关联不清时，报告缺口并停止该字段；不能为了“无空值”编造 UUID、编码、名称、地址、日期或枚举值。
5. 字段语义、类型、来源或编码体系发生变化时，旧 payload 和旧 DTS 映射都标为 stale，重新生成并复核，不能沿用旧值。
6. 运行确定性校验；静态通过只证明字段、类型、语义标签和来源清单一致，不等于接口已调用或目标系统已接受。

## 校验文件格式

`contract.json`：

```json
{
  "version": 1,
  "allow_extra": false,
  "fields": {
    "TrackingUnit": {
      "required": true,
      "json_type": "string",
      "semantic_type": "unified_identity_code",
      "source_policy": "real"
    },
    "Province": {
      "required": true,
      "json_type": "string",
      "semantic_type": "text",
      "source_policy": "real"
    }
  }
}
```

`provenance.json`：

```json
{
  "fields": {
    "TrackingUnit": {
      "kind": "production_master_data",
      "semantic_type": "unified_identity_code",
      "source": "verified organization relation"
    },
    "Province": {
      "kind": "production_record",
      "semantic_type": "text",
      "source": "target business record"
    }
  }
}
```

执行：

```text
python3 scripts/validate_outbound_contract.py \
  --contract contract.json \
  --payload payload.json \
  --provenance provenance.json \
  --require-real-provenance
```

退出码 `0` 表示一致；`1` 表示 contract、payload 或 provenance 不一致；`2` 表示输入文件/格式错误。输出只列字段和错误码，不回显业务值。
