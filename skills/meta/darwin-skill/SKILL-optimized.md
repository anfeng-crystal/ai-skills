---
name: darwin-skill
description: "Darwin Skill (达尔文.skill): autonomous skill optimizer inspired by Karpathy's autoresearch. Evaluates SKILL.md files using an 8-dimension rubric (structure + effectiveness), runs hill-climbing with git version control, validates improvements through test prompts, and generates visual result cards. Use when user mentions \"优化skill\", \"skill评分\", \"自动优化\", \"auto optimize\", \"skill质量检查\", \"达尔文\", \"darwin\", \"帮我改改skill\", \"skill怎么样\", \"提升skill质量\", \"skill review\", \"skill打分\"."
---

# Darwin Skill

> 借鉴 Karpathy autoresearch 的自主实验循环，对 skills 进行持续优化。
> 核心理念：**评估 → 改进 → 实测验证 → 人类确认 → 保留或回滚 → 生成成果卡片**
> GitHub: https://github.com/alchaincyf/darwin-skill

---

## 设计哲学

autoresearch 的精髓：
1. **单一可编辑资产** — 每次只改一个 SKILL.md
2. **双重评估** — 结构评分（静态分析）+ 效果验证（跑测试看输出）
3. **棘轮机制** — 只保留改进，自动回滚退步
4. **独立评分** — 评分用子agent，避免「自己改自己评」的偏差
5. **人在回路** — 每个skill优化完后暂停，用户确认再继续
6. **边际价值** — 同一prompt必须比较 with_skill 与 no_skill；如果模型不用skill也能稳定完成，相关规则应压缩或删除

与纯结构审查的区别：不只看 SKILL.md 写得规不规范，更看改完后**实际跑出来的效果是否更好**。

---

## 评估 Rubric（8维度，总分100）

### 结构维度（60分）

| # | 维度 | 权重 | 关键点 |
|---|------|------|--------|
| 1 | Frontmatter质量 | 8 | name规范、description完整、触发词明确 |
| 2 | 工作流清晰度 | 15 | 步骤可执行、有序号、输入输出明确 |
| 3 | 边界条件覆盖 | 10 | 异常处理、fallback路径、错误恢复 |
| 4 | 检查点设计 | 7 | 关键决策前有用户确认 |
| 5 | 指令具体性 | 15 | 不模糊、有参数/格式/示例 |
| 6 | 资源整合度 | 5 | references/scripts/assets引用正确 |

### 效果维度（40分）

| # | 维度 | 权重 | 关键点 |
|---|------|------|--------|
| 7 | 整体架构 | 15 | 结构清晰、不冗余不遗漏 |
| 8 | 实测表现 | 25 | 测试prompt输出质量、相比baseline的提升 |

详细评分标准见 `references/rubric-detail.md`

---

## 自主优化循环概述

### Phase 0: 初始化
确认优化范围 → 创建 git 分支 → 初始化 results.tsv

### Phase 0.5: 测试Prompt设计
为每个skill设计2-3个测试prompt，覆盖典型场景和边界情况。展示给用户确认后再进入评估。

### Phase 1: 基线评估
- 结构评分（维度1-7）
- 效果评分（维度8，用子agent跑测试prompt，对比 with_skill vs no_skill）
- 展示评分卡，等用户确认

### Phase 2: 优化循环
按基线分数从低到高排序，每个skill最多3轮：
1. 诊断最低维度
2. 提出改进方案
3. 执行改进（编辑 + git commit）
4. 重新评估（独立子agent）
5. 决策：新分数 > 旧分数 → keep，否则 revert
6. 每个skill优化完展示改动摘要，等用户确认

### Phase 2.5: 探索性重写（可选）
当 hill-climbing 连续2个skill涨不动时，提议重写。需用户同意。

### Phase 3: 汇总报告
总览 + 分数变化表 + 主要改进

详细流程见 `references/optimization-loop.md`

---

## 使用方式

### 全量优化（推荐首次使用）
```
用户："优化所有skills"
→ Phase 0-3 完整流程
```

### 单个优化
```
用户："优化 huashu-slides 这个skill"
→ 只对指定skill执行 Phase 0.5-2
```

### 仅评估不改
```
用户："评估所有skills的质量"
→ 只执行 Phase 0.5-1（测试prompt设计 + 基线评估）
```

### 查看历史
```
用户："看看skill优化历史"
→ 读取并展示 results.tsv
```

---

## 约束规则

1. **不改变skill的核心功能和用途** — 只优化"怎么写"和"怎么执行"，不改"做什么"
2. **谨慎引入资源** — 默认不新增依赖；只有能显著降低上下文或提高确定性时才新增
3. **每轮只改一个维度** — 避免多个变更导致无法归因
4. **保持文件大小合理** — 优化后SKILL.md不应超过原始大小的150%
5. **尊重花叔风格** — 中文为主、简洁为上
6. **可回滚** — 所有改动在git分支上，用git revert而非reset --hard
7. **评分独立性** — 效果维度必须用子agent或至少干跑验证
8. **不为规则而规则** — skill 只保留模型无skill时明显做不稳的领域知识、资源入口、工具流程和红线

---

## References

- `references/rubric-detail.md` — 8维度详细评分标准、实测表现说明、有用性判定
- `references/optimization-loop.md` — Phase 0-3详细步骤、探索性重写、汇总报告格式
- `references/strategies.md` — 优化策略库（P0-P3）
- `references/result-card.md` — 成果卡片生成流程、模板、品牌元素
- `references/tsv-format.md` — results.tsv 格式说明

---

## 设计灵感

> "You write the goals and constraints in program.md; let an agent generate and test code deltas indefinitely; keep only what measurably improves the objective."
> — Karpathy, autoresearch

本skill的对应关系：
- **program.md** → 本文件（评估rubric和约束规则）
- **train.py** → 每个SKILL.md
- **val_bpb** → 8维加权总分（含实测表现）
- **git ratchet** → 只保留有改进的commit
- **test set** → 每个skill的test-prompts.json

区别：增加了人在回路和双重评估机制，因为skill的「好坏」比loss数值更微妙。
