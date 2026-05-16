# results.tsv 格式说明

## 文件位置
当前 skill 目录下的 `results.tsv`。

## 格式

```tsv
timestamp	commit	skill	baseline_score	old_score	new_score	status	dimension	note	eval_mode	model_set	avg_skill_delta
2026-03-31T10:00	baseline	skill-a	65	-	78	baseline	-	初始评估	full_test	default,mini,coder	+0.8
2026-03-31T10:05	a1b2c3d	skill-a	65	78	84	keep	边界条件	补充fallback	full_test	default,mini,coder	+1.3
2026-03-31T10:10	b2c3d4e	skill-a	65	84	82	revert	指令具体性	过度细化	dry_run	default	-0.4
```

## 字段说明

| 字段 | 说明 | 示例 |
|------|------|------|
| timestamp | ISO 8601 时间戳 | 2026-03-31T10:00 |
| commit | git commit SHA（baseline时为"baseline"） | a1b2c3d |
| skill | skill 名称 | skill-a |
| baseline_score | no_skill baseline 的分数；历史缺失时填 `-` | 65 |
| old_score | 改进前总分（baseline时为"-"） | 78 |
| new_score | 改进后总分 | 84 |
| status | baseline / keep / revert | keep |
| dimension | 本轮改进的维度 | 边界条件 |
| note | 改进摘要或失败原因 | 补充fallback |
| eval_mode | full_test（跑了子agent）/ dry_run（模拟推演） | full_test |
| model_set | 测试使用的模型列表（逗号分隔） | default,mini,coder |
| avg_skill_delta | skill 相对 no_skill 的平均增量价值 | +1.3 |

## 用途

- 追踪每个skill的优化历史
- 分析哪些维度改进成功率高
- 对比 full_test vs dry_run 的准确性
- 评估多模型测试的必要性
