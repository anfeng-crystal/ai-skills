---
name: darwin-skill
description: "Self-improving SKILL.md quality. 8-dim rubric scoring, git-tracked versions, test prompts, auto-rollback on regression. Not for reviewing third-party skills (use skill-vetter)."
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [skill, optimizer, darwin, auto-tune, evaluation]
---

# Darwin Skill

> **Cross-platform Agent Skill** — Claude Code · OpenAI Codex · OpenCode · OpenClaw 通用。
> 跨平台 SKILL.md，遵循开放 Agent Skill 规范。

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

### 结构维度（60分）— 静态分析

| # | 维度 | 权重 | 评分标准 |
|---|------|------|---------|
| 1 | **Frontmatter质量** | 8 | name规范、description包含做什么+何时用+触发词、≤1024字符 |
| 2 | **工作流清晰度** | 15 | 步骤明确可执行、有序号、每步有明确输入/输出 |
| 3 | **边界条件覆盖** | 10 | 处理异常情况、有fallback路径、错误恢复 |
| 4 | **检查点设计** | 7 | 关键决策前有用户确认、防止自主失控 |
| 5 | **指令具体性** | 15 | 不模糊、有具体参数/格式/示例、可直接执行 |
| 6 | **资源整合度** | 5 | references/scripts/assets引用正确、路径可达 |

### 效果维度（40分）— 需要实测

| # | 维度 | 权重 | 评分标准 |
|---|------|------|---------|
| 7 | **整体架构** | 15 | 结构层次清晰、不冗余不遗漏、符合项目规范 |
| 8 | **实测表现** | 25 | 用测试prompt跑一遍，输出质量是否符合skill宣称的能力 |

### 评分规则
- 维度1-7：每个维度打 1-10 分，乘以权重得到该维度得分
- 维度8（实测表现）：跑2-3个测试prompt，按输出质量打1-10分
- **总分 = Σ(维度分 × 权重) / 10**，满分100
- 改进后总分必须 **严格高于** 改进前才保留

### 关于「实测表现」维度

这是与纯结构评分最大的区别。评分方式：

1. 为每个skill设计2-3个**典型用户prompt**（不是边缘case，是最常见的使用场景）
2. 用子agent执行 with_skill 与 no_skill baseline；可用多个模型时至少覆盖：
   - 当前默认模型/主力模型
   - 一个更小或更快的模型
   - 一个偏代码或偏推理的模型（如果当前环境可用）
3. 对比输出质量，从以下角度打分：
   - 输出是否完成了用户意图？
   - 相比不带skill的baseline，质量提升明显吗？
   - 有没有skill引入的负面影响（过度冗余、跑偏、格式奇怪）？
   - 多模型结论是否一致？是否只有某个弱模型依赖该规则？

如果无法跑子agent（时间/资源限制），可以退化为「干跑验证」：读完skill后模拟一个典型prompt的执行思路，判断流程是否合理。但要在results.tsv中标注 `dry_run`。

### Skill 有用性的判定

- **高价值规则**：no_skill 经常遗漏、误判或走错工具；with_skill 明显改善，并且不显著增加冗余。
- **低价值规则**：多个模型 no_skill 已稳定完成，with_skill 只是重复常识、系统规则或通用工程习惯；应压缩到一句，或移出 SKILL.md。
- **负价值规则**：with_skill 更容易停问、逃避、过度约束、输出过程流水或忽略用户目标；优先删除或改成“主动补证后推进”的规则。
- **模型专属规则**：只帮助小模型、不影响强模型的内容可以保留，但要写成短规则或引用 references，避免长期占用主上下文。

---

## 自主优化循环

### Phase 0: 初始化

```
1. 确认优化范围：
   - 全部skills → 扫描当前宿主实际启用的 skills 目录（如 active skills、.agents/skills、.codex/skills）
   - 指定skills → 用户指定列表
   - 复盘型请求 → 优先只选“本轮实际用到的 skills”；先列出使用链路，再按“可编辑的本地 skill / bundled 或 cache skill”分组
   - 默认只改可编辑的本地 skill；对于插件缓存、bundled skill 或第三方只读副本，默认只评分和给优化建议，除非用户明确要求直接改这些文件
2. 创建 git 分支：auto-optimize/YYYYMMDD-HHMM
3. 初始化 results.tsv（如不存在）
4. 读取现有 results.tsv 了解历史优化记录
```

### Phase 0.5: 测试Prompt设计

在基线评估前，为每个 skill 设计 2-3 个测试 prompt。

```
for each skill:
  1. 读取 SKILL.md，理解它做什么
  2. 设计2-3个测试prompt，覆盖：
     - 最典型的使用场景（happy path）
     - 一个稍复杂或有歧义的场景
  3. 保存到 skill目录/test-prompts.json：
     [
       {
         "id": "happy_path",
         "prompt": "用户会说的话",
         "expected": "期望输出的简短描述",
         "eval_focus": "用来判断输出好坏的关键点",
         "baseline_risk": "不使用该skill时最可能缺失或跑偏的地方"
       },
       {
         "id": "ambiguous_case",
         "prompt": "...",
         "expected": "...",
         "eval_focus": "...",
         "baseline_risk": "..."
       }
     ]
```

展示所有测试prompt给用户，**确认后再进入评估**。测试prompt的质量决定了优化方向是否正确。

### Phase 1: 基线评估（Baseline）

```
for each skill in 优化范围:

  # 结构评分（主agent可以做）
  1. 读取 SKILL.md 全文
  2. 按维度1-7逐项打分（附简短理由）

  # 效果评分（用子agent做，独立于主agent）
  3. 按”关于「实测表现」维度”的方法，对每个测试 prompt 跑 with_skill 与 no_skill 对比
  4. 记录三个关键数据：
     - baseline_score：no_skill 的分数
     - with_skill_score：当前 skill 的分数
     - skill_delta：with_skill_score - baseline_score
  5. 维度 8 按 skill_delta 和任务完成质量综合打分

  # 汇总
  6. 计算加权总分
  7. 记录到 results.tsv（包含 baseline_score）
```

**如果子agent或多模型不可用**（超时、环境限制），维度8用干跑验证打分，标注 `dry_run`。干跑也必须记录 `prompt_id`、`expected`、`with_skill_expected_behavior`、`baseline_expected_behavior`、`skill_delta`、`score_reason`，不要因为跑不了测试就跳过这个维度——哪怕是模拟推演也比完全不看效果好。

基线评估完成后，展示评分卡：

```
┌──────────────────────────┬───────┬──────────────┬──────────────┐
│ Skill                    │ Score │ 结构短板      │ 效果短板      │
├──────────────────────────┼───────┼──────────────┼──────────────┤
│ skill-a                  │ 78    │ 边界条件      │ 测试prompt2  │
│ skill-b                  │ 72    │ 指令具体性    │ baseline持平  │
├──────────────────────────┼───────┼──────────────┼──────────────┤
│ 平均                     │ 75    │              │              │
└──────────────────────────┴───────┴──────────────┴──────────────┘
```

**暂停等用户确认，再进入优化循环。**

### Phase 2: 优化循环

用户确认后，按基线分数从低到高排序，先优化最弱的。

**清理上一轮测试输出**：
```bash
# 删除所有 skill 目录下的临时测试输出文件
find . -name "*-test-output-*.json" -delete
find . -name "*-with-skill-*.txt" -delete
find . -name "*-no-skill-*.txt" -delete
# 保留 test-prompts.json 和 results.tsv
```

```
for each skill:
  round = 0
  while round < MAX_ROUNDS (默认3):
    round += 1

    # Step 1: 诊断
    找出得分最低的维度（结构或效果都算）

    # Step 2: 提出改进方案
    针对最低维度，生成1个具体改进方案：
      - 改什么（具体段落/行）
      - 为什么改（对应rubric哪条）
      - 预期提升多少分

    # Step 3: 执行改进
    编辑 SKILL.md
    git add + commit（message: "optimize {skill}: {改进摘要}"）

    # Step 4: 重新评估
    按 Phase 1 的方法重新打分，记录：
      - baseline_score（no_skill，保持不变）
      - previous_score（优化前 with_skill）
      - new_score（优化后 with_skill）
      - previous_delta（previous_score - baseline_score）
      - new_delta（new_score - baseline_score）

    # Step 5: 决策
    if new_score > previous_score AND new_delta > previous_delta:
      status = "keep"，更新旧总分
      说明：不仅总分提升，相对 baseline 的增量也提升
    else:
      status = "revert"
      git revert HEAD（创建新commit回滚，不用reset --hard）
      记录失败尝试到 results.tsv
      break  # 该skill到瓶颈，跳到下一个

    # Step 6: 日志
    results.tsv 追加行

  # === 每个skill优化完后的人类检查点 ===
  展示该skill的改动摘要：
    - git diff（改前 vs 改后）
    - 分数变化（哪些维度提升/下降）
    - 测试prompt输出对比（如果跑过的话）
  等用户确认 OK 再继续下一个skill。
  如果用户说"不好"，回滚到该skill的优化前版本。

  # === 清理测试文件 ===
  删除该 skill 的测试输出文件：
  - 删除 {skill-name}-test-output-*.json
  - 删除 {skill-name}-with-skill-*.txt
  - 删除 {skill-name}-no-skill-*.txt
  - 保留 test-prompts.json 和 results.tsv 记录
```

### Phase 2.5: 探索性重写（可选）

当 hill-climbing 连续2个skill都在 round 1 就 break（涨不动）时，提议一次「探索性重写」：

```
1. 选一个瓶颈skill
2. git stash 保存当前最优版本
3. 从头重写SKILL.md（不是微调，是重新组织结构和表达方式）
4. 重新评估
5. if 重写版 > stash版: 采用重写版
   else: git stash pop 恢复
```

这解决了 hill-climbing 的局部最优问题——有时候需要「先拆后建」才能突破瓶颈。
**必须征得用户同意后才执行。**

### Phase 3: 汇总报告与成果卡片

优化完成后，生成两种格式的报告：

#### 1. 文本报告（终端输出）

```
## 优化报告

### 总览
- 优化skills数：N
- 总实验次数：M
- 保留改进：X（Y%）
- 回滚次数：Z
- 实测验证：A次完整测试 / B次干跑

### 分数变化
┌──────────────────────────┬────────┬────────┬────────┐
│ Skill                    │ Before │ After  │ Δ      │
├──────────────────────────┼────────┼────────┼────────┤
│ skill-a                  │ 78     │ 87     │ +9     │
│ skill-b                  │ 72     │ 83     │ +11    │
├──────────────────────────┼────────┼────────┼────────┤
│ 平均                     │ 75     │ 85     │ +10    │
└──────────────────────────┴────────┴────────┴────────┘

### 主要改进
1. [skill-A] 补充了边界条件处理，测试输出质量提升明显
2. [skill-B] 重组了workflow结构，baseline对比优势增大
```

#### 2. 成果卡片（Markdown + HTML/PNG 增强）

为每个优化的 skill 生成 Markdown 成果卡片，包含：
- skill 名称、优化日期、分数变化
- 各维度对比（before/after/delta）
- 主要改进列表
- 测试结果摘要

保存位置：/tmp/{skill-name}-result.md

当成果需要转交审核、展示评分变化或包含多维对比时，同时生成 HTML/PNG 增强产物：
- HTML 模板优先复用 `templates/result-card-gated.html.template`；旧模板继续可作视觉参考，但交付前必须通过共享门禁。不要把大段 HTML 粘进聊天上下文。
- 成果卡片必须保留可操作视图：维度变化、主要改进、测试结果切换，以及复制摘要状态反馈。
- 输出目录遵循 `output/html/darwin-skill/<timestamp>/index.html`，截图为同目录 `desktop.png` / `mobile.png`。
- 将渲染用 JSON 保存为同目录 `card-data.json`，并写入 `recordCount: 1` 供质量门禁校验。
- 生成后运行共享门禁：
  ```bash
  node skills/meta/html-output-quality/scripts/check-html.mjs \
    --html output/html/darwin-skill/<timestamp>/index.html \
    --source output/html/darwin-skill/<timestamp>/card-data.json \
    --out output/html/darwin-skill/<timestamp>
  ```
- 有 High 问题时先修模板或数据，不把 HTML 标记为通过；Markdown 摘要仍作为聊天主交付。

---

## results.tsv 格式

```tsv
timestamp	commit	skill	baseline_score	old_score	new_score	status	dimension	note	eval_mode	model_set	avg_skill_delta
2026-03-31T10:00	baseline	skill-a	65	-	78	baseline	-	初始评估	full_test	default,mini,coder	+0.8
2026-03-31T10:05	a1b2c3d	skill-a	65	78	84	keep	边界条件	补充fallback	full_test	default,mini,coder	+1.3
2026-03-31T10:10	b2c3d4e	skill-a	65	84	82	revert	指令具体性	过度细化	dry_run	default	-0.4
```

列说明：
- `baseline_score`：no_skill 的分数（保持不变，用于追踪 skill 相对 baseline 的增量）
- `old_score`：上一版本 with_skill 的分数
- `new_score`：当前版本 with_skill 的分数
- `avg_skill_delta`：当前版本相对 baseline 的平均增量（new_score - baseline_score）
- `eval_mode`：`full_test`（跑了子agent测试）或 `dry_run`（模拟推演）
- `model_set`：测试覆盖的模型列表
文件位置：当前 skill 目录下的 `results.tsv`

---

## 异常与边界条件

| 场景 | 处理方式 |
|---|---|
| 不在 git 仓库 | 先提示用户风险；用户确认后用 `SKILL.md.bak.YYYYMMDD-HHMM` 文件备份代替 git revert |
| `results.tsv` 缺失 | 新建 12 列表头，列顺序必须与本节 `results.tsv 格式` 一致 |
| `results.tsv` 列数不一致 | 先备份为 `results.tsv.bak.YYYYMMDD-HHMM`，再补齐缺失列；历史缺失的 `baseline_score` 填 `-` |
| 测试 prompt 已存在 | 默认复用并展示；只有用户确认后才重写或追加 |
| 优化后体积超过原文件 150% | 不提交，回到改进步骤先精简 |
| 子agent或多模型不可用 | 退化为 `dry_run`，但必须记录 baseline 预期、with_skill 预期和评分理由 |
| 回滚失败或工作树脏 | 停止自动处理，展示冲突和建议恢复步骤，由用户确认后继续 |
| 优化范围混入 bundled/cache skill | 默认只评分不改写，改写前先单独征得用户同意 |
| 目标 skill 仓已有未提交改动 | 缩小到目标文件最小编辑；不要顺手整理同目录其它改动 |

---

## 优化策略库

按优先级排序，每轮只做最高优先级的一个：

### P0: 效果问题（实测发现的）
- 测试输出偏离用户意图 → 检查skill是否有误导性指令
- 带skill比不带还差 → skill可能过度约束，考虑精简
- 输出格式不符合预期 → 补充明确的输出模板

### P1: 结构性问题
- Frontmatter缺少触发词 → 补充中英文触发词
- 缺少Phase/Step结构 → 重组为线性流程
- 缺少用户确认检查点 → 在关键决策处插入

### P2: 具体性问题
- 步骤模糊（"处理图片"）→ 改为具体操作和参数
- 缺少输入/输出规格 → 补充格式、路径、示例
- 缺少异常处理 → 补充 "如果X失败，则Y"

### P3: 可读性问题
- 段落过长 → 拆分+用表格
- 重复描述 → 合并去重
- 缺少速查 → 添加TL;DR或决策树

---

## 约束规则

1. **不改变skill的核心功能和用途** — 只优化"怎么写"和"怎么执行"，不改"做什么"
2. **谨慎引入资源** — 默认不新增依赖；只有脚本或 reference 能显著降低上下文、提高确定性或承载项目专有知识时才新增
3. **保持文件大小合理** — 优化后SKILL.md不应超过原始大小的150%
4. **可回滚** — 所有改动在git分支上，用git revert而非reset --hard
5. **评分独立性** — 效果维度必须用子agent或至少干跑验证，不能在同一上下文里「改完直接评」

---

## 使用方式

### 全量优化（推荐首次使用）
```
用户："优化所有skills"
→ Phase 0-3 完整流程
→ 建议：先基线评估，选择分数最低的5-10个重点优化
```

### 单个优化
```
用户："优化 code-review 这个skill"
→ 只对指定skill执行 Phase 0.5-2
```

### 仅评估不改
```
用户："评估所有skills的质量"
→ 只执行 Phase 0.5-1（设计测试prompt + 基线评估），不进入优化循环
```

### 查看历史
```
用户："看看skill优化历史"
→ 读取并展示 results.tsv
```

---
