# Normalized UI Test Cases

Use one case object per business scenario:

| Field | Meaning |
| --- | --- |
| `caseId` | Stable unique ID |
| `name` | Business scenario name |
| `priority` | `P0`, `P1`, `P2`, or `P3` |
| `requirements` | Requirement IDs covered by the case |
| `preconditions` | Observable setup facts, not credentials |
| `steps` | Ordered step objects |

Each step contains `stepId`, `order`, `action`, `target`, `data`, `expected`, `mutates`, and `effect`.

## Action vocabulary

Read-only actions: `navigate`, `inspect`, `assert`, `screenshot`, `wait`, `search`, `open`, `close`, `paginate`, `switch-tab`.

Write-capable actions: `input`, `select`, `upload`, `save`, `create`, `update`, `delete`, `submit`, `audit`, `unaudit`, `enable`, `disable`, `workflow`, `cleanup`, `rollback`.

Use `click` only with an explicit `effect`. Mark it `mutates=true` unless the effect is one of `navigation`, `open`, `close`, `paginate`, `switch-tab`, or `inspect`.

## CSV columns

Use one row per step. Supported columns are `case_id`, `case_name`, `priority`, `requirements`, `preconditions`, `step_id`, `step_order`, `action`, `target`, `data`, `expected`, `mutates`, and `effect`. Separate list values with `|`.

Never place authentication data, browser storage, tenant-specific URLs, or reusable session material in a testcase.

## 页面断言与执行结果

页面断言必须声明可选的 `step.page`；普通导航和非页面步骤省略。`page` 是本地 schemaVersion `1.0` 的可选扩展，旧文件不含它时仍可读取，但报告不会声称已核验页面身份。

```json
{
  "stepId": "check-status-column",
  "action": "assert",
  "target": "status",
  "expected": "状态列可见",
  "page": {"formId": "sample_list", "pageType": "list", "pageElement": "status"}
}
```

- 三个预期字段均为必填非空字符串；`pageType` 只允许 `list`、`detail`、`edit`、`dialog`。`pageElement` 使用双方一致的控件/布局逻辑标识。
- 示例标识仅作格式示意。执行前从当前页面或元数据确认身份；无法确认则先补证，不能按表名、实体名、标题或相似字段编造 `formId`。列表绑定单据的 ID 不自动等于当前视图身份。
- CSV 可加 `page_form_id`、`page_type`、`page_element` 三列；全空表示未声明，部分填写拒绝。JSON normalize 和 CSV normalize 生成相同的 `page` 对象，可再次导入生成的 JSON。
- 执行结果支持 JSON 数组、`{"results": [...]}` 或 JSONL。每条用 `caseId` / `stepId` 对齐，`status` 为 `passed`、`failed`、`blocked`、`skipped`、`not-run`。缺结果也标记 `not-run`。

页面断言的实测结果示意：

```json
{
  "caseId": "PAGE-001", "stepId": "check-status-column", "status": "passed",
  "actual": "状态列可见",
  "page": {
    "route": "/sample/list",
    "formId": "sample_list", "pageType": "list", "pageElement": "status"
  }
}
```

报告保留步骤预期 `page`、脱敏后的 `evidence.page`、原始 `rawStatus` 与 `pageCheck`。三个身份字段在脱敏前逐项比较（忽略首尾空白，不转换大小写），实际 `route` 须为非空字符串；不从 route 推导身份或要求 URL 相等。route 的 host、query、fragment 隐去，只保留脱敏路径。

| pageCheck.status | 含义及门禁 |
| --- | --- |
| `matched` | 必要实测齐全且身份字段匹配；仅最终 `passed` 计入 `summary.pagePassedCount` |
| `wrong_page` | 至少一个身份字段明确不匹配；报送 `passed` 降为 `blocked`，`blockReason=blocked_wrong_page` |
| `missing` | 必要实测缺失、为空或类型错误；报送 `passed` 降为 `blocked`，`blockReason=blocked_missing_page_evidence` |
| `not-requested` | 步骤未声明页面预期；保留执行者状态，不计入页面核验通过数 |

明确错配优先于缺证据。已有 `failed` / `blocked` / `skipped` / `not-run` 保持不变，并保留页面诊断；没有执行结果时 `rawStatus=null`。`statusCounts.passed` 包括非页面步骤，不能充当页面通过数。报告只检验执行者提供的结构化证据一致性，实际可见性、行为和截图仍由受支持的浏览器执行器核验。

页面概念来源：[标准单据列表插件-视图模型](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=218061890915053824&id=223817018275635200&type=Knowledge&productLineId=29&lang=zh-CN)。该文不定义本地 JSON 合同。

详细来源、版本与验收边界见[云端知识条目](https://chatgpt.com/space/page_f4f9da1eaad081919ae9e4f94ee96a10)；离线执行仍以本地合同为准。
