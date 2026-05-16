# 复盘评分卡模板

用于 `skill-retrospective` 在收尾阶段输出稳定的复盘报告。  
目标不是把这轮对话复述一遍，而是明确回答三个问题：

1. 本轮到底用了哪些 skill
2. 这轮应该新建 skill，还是优化已有 skill
3. 哪些优化已经抽象成通用准则，哪些仍然只是一次性案例

## 适用场景
- 用户说“收尾”“复盘”“结束前看一下这轮 skill”
- 需要调用 `darwin-skill` 做轻量评分优化
- 需要形成稳定的本轮 skill 沉淀结论

## 输出顺序
1. 本轮行为统计
2. 本轮 skill 清单
3. 评分与优化结果
4. 沉淀策略结论

## 复盘评分卡模板

```md
**本轮行为统计**
- new_skill: 是/否，理由
- improve_existing: 是/否，理由
- no_skill_change: 是/否，理由
- final_strategy: new_skill | improve_existing | no_skill_change

**本轮 skill 清单**
- skill: skill-name
  evidence: 用户点名 / 助手显式使用 / 本轮实际承担步骤
  path_type: editable_local | score_only | excluded
  action: optimize | score_only | exclude

**评分与优化**
- skill: skill-name
  mode: dry_run | tested
  before: 84
  after: 90
  result: keep | revert | score_only
  weakest_dimension: 工作流清晰度 / 指令具体性 / 边界条件覆盖
  change_summary:
    - 补了什么
    - 为什么值得保留

**沉淀策略**
- target_skill: 归属到哪个已有 skill，或确实需要新建 skill
- universal_rule: 这次沉淀出的通用行为准则
- rejected_rule: 哪条规则因为太像一次性案例而没有保留
```

## 判定口径

### `new_skill`
只有同时满足下面两条，才建议新建：
- 现有 skill 无法承接
- 抽象后仍有跨任务复用价值

### `improve_existing`
只要本轮问题能通过补边界、补守卫、补工作流收进已有 skill，就优先归到这里。

### `no_skill_change`
如果只是一次性业务细节，或无法抽象成长期规则，就只记录复盘，不强行沉淀。

## 通用化检查
每次复盘都要明确写出一条 `universal_rule`，并验证它满足：

1. 不依赖本次案例名词才能成立
2. 换一个相似需求仍然可用
3. 它说的是判断条件和处理动作，不是单个文件名

## 简短示例

```md
**本轮行为统计**
- new_skill: 否，现有收尾链路可承接
- improve_existing: 是，本轮暴露的是已有清理守卫不足
- no_skill_change: 否
- final_strategy: improve_existing

**本轮 skill 清单**
- skill: cleanup-guard
  evidence: 本轮用于收尾删除测试残留
  path_type: editable_local
  action: optimize

- skill: darwin-skill
  evidence: 本轮作为评分引擎参与
  path_type: score_only
  action: score_only

**评分与优化**
- skill: cleanup-guard
  mode: dry_run
  before: 82
  after: 88
  result: keep
  weakest_dimension: 指令具体性
  change_summary:
    - 增加候选判定顺序
    - 增加保留门槛

**沉淀策略**
- target_skill: cleanup-guard
- universal_rule: 删除未跟踪源码文件前，必须先完成归因确认
- rejected_rule: 删除某个具体文件名前先确认
```
