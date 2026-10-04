# 可选评测约定

仅在需要可复核评分、批量对比或用户要求留档时读取；不是小幅优化的审批或强制产物。

`test-prompts.json` 记录 `id`、`prompt`、`expected`、`eval_focus`、`baseline_risk`。
`results.tsv` 使用验证器字段：`timestamp`、`commit`、`skill`、`prompt_id`、`baseline_score`、`old_score`、`new_score`、`avg_skill_delta`、`eval_mode`、`model_set`、`status`、`notes`。保留实际 TSV 列数和换行。

`prompt_id` 关联同组案例的唯一 ID，表头不得重名；未测量或不可比较的分数、增量和模型信息填 `-` 并在 `notes` 说明，不用估计数字伪装观测。可复制的标准表头与旧记录处置见 [TSV 格式](tsv-format.md)。

`eval_mode` 为实际运行的 `full_test` 或明确推演的 `dry_run`。无实际 token 时标静态估算；发现成本、正文加载和实际执行成本分别比较，references/assets 大小不代表每次加载量。

可沿用总分100、结构60/效果40，维度为触发精度、运行价值、边界、可执行性、token经济性、证据验证、失败恢复、行为增量和决策一致性。评分只辅助比较，不能抵消能力、安全或任务结果回退，也不要求为了分数重写可靠规则。

可得时记录 input/output/cached/reasoning tokens、首轮成功、重试、人工接管和调用顺序。对比条件须一致；无法隔离基线时说明污染来源，不作收益结论。

资源校验器的 `--source-root` 指包含 `<category>/<skill>/SKILL.md` 的分类根目录，在本仓库为 `<active-root>/skills`。省略时使用 `AI_SKILLS_HOME`，未设置则使用脚本所在源树的 `skills/` 目录；该默认值不随当前工作目录改变。

只保留脱敏资产；未经要求不加入Git。需要全覆盖评测资产时才运行 `scripts/validate-skill-assets.mjs --require-eval-assets`；该选项检查选定 source root 下每个 Skill，不要把未参与评测的入口缺文件误报为业务回归。

`results_read_failed` 或 `text_read_failed` 表示相应内容未完成检查，报告仍保留其他独立文件的结果并以失败状态退出；修复读取问题后再重新验证，不能把部分结果视为全部通过。

`directory_read_failed` 表示相应目录未完成扫描，报告保留其他可访问分支的结果并以失败状态退出；目录不可读不能证明其中没有 Skill。

`test_prompts_read_failed` 表示 prompt 文件未能读取，不能当作 JSON 语法错误；`invalid_test_prompts_json` 才表示内容无法解析。错误报告只保留稳定读取代号或通用语法说明，不带底层异常消息或原始 prompt 片段。
