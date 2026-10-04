# results.tsv 格式说明

## 文件位置与用途

批量评测需要留档时，优先写入任务产物目录；只有明确要求维护 Skill 本地评测资产时才放在对应 Skill 目录。不是每次优化都需要 TSV，也不因生成记录就自动加入 Git。完整约定见 [评测约定](evaluation-contract.md)。

## 格式

```tsv
timestamp	commit	skill	prompt_id	baseline_score	old_score	new_score	avg_skill_delta	eval_mode	model_set	status	notes
2026-10-04T10:00:00+08:00	baseline	skill-a	case-1	-	-	-	-	dry_run	-	keep	仅推演路由，未测量评分或token
```

## 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| timestamp | ISO 8601 时间戳 | 2026-03-31T10:00 |
| commit | git commit SHA（baseline时为"baseline"） | a1b2c3d |
| skill | skill 名称 | skill-a |
| prompt_id | 对应 `test-prompts.json` 中唯一且实际存在的案例 ID | case-1 |
| baseline_score | no_skill 基线分数；未做该对照填 `-` | 65 |
| old_score | 旧版分数；未测量填 `-` | 78 |
| new_score | 候选版分数；未测量填 `-` | 84 |
| avg_skill_delta | 相对 no_skill 的平均增量及明确口径；不可比或未测量填 `-` | - |
| eval_mode | 实际执行案例且有可检查产物为 `full_test`；仅评审或推演为 `dry_run` | dry_run |
| model_set | 实际参与评测的模型标识；未记录时填 `-` | - |
| status | baseline / keep / revert | keep |
| notes | 改进维度、证据位置、限制或回滚原因；不含凭据、原始业务数据或制表符/换行 | 路由推演，未执行业务流程 |

## 校验与旧格式

表头不得重名，每行列数与表头一致；正文中的制表符或换行先概括为单行文本，不改变分隔符。示例数字和模型名不能当成实际测量。调用了子代理只说明评审来源独立，不自动证明 `full_test`。

旧表头的 `dimension`、`note` 可合并到 `notes`，但不能编造缺失的 `prompt_id`；无法关联案例时保留为历史记录并说明限制。验证器默认对旧格式警告，`--strict-results` 将其判错；不为消除警告捏造测量或案例。
