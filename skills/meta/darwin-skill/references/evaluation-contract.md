# 可选评测约定

仅在需要可复核评分、批量对比或用户要求留档时读取；不是小幅优化的审批或强制产物。

`test-prompts.json` 记录 `id`、`prompt`、`expected`、`eval_focus`、`baseline_risk`。
`results.tsv` 使用验证器字段：`timestamp`、`commit`、`skill`、`prompt_id`、`baseline_score`、`old_score`、`new_score`、`avg_skill_delta`、`eval_mode`、`model_set`、`status`、`notes`。保留实际 TSV 列数和换行。

`eval_mode` 为实际运行的 `full_test` 或明确推演的 `dry_run`。无实际 token 时标静态估算；发现成本、正文加载和实际执行成本分别比较，references/assets 大小不代表每次加载量。

可沿用总分100、结构60/效果40，维度为触发精度、运行价值、边界、可执行性、token经济性、证据验证、失败恢复、行为增量和决策一致性。评分只辅助比较，不能抵消能力、安全或任务结果回退，也不要求为了分数重写可靠规则。

可得时记录 input/output/cached/reasoning tokens、首轮成功、重试、人工接管和调用顺序。对比条件须一致；无法隔离基线时说明污染来源，不作收益结论。

只保留脱敏资产；未经要求不加入Git。需要全覆盖评测资产时才运行 `scripts/validate-skill-assets.mjs --require-eval-assets`；该选项检查选定 source root 下每个 Skill，不要把未参与评测的入口缺文件误报为业务回归。
