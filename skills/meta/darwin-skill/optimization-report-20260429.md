# Darwin Skill 优化报告

**优化日期**: 2026-04-29  
**优化分支**: auto-optimize/20260429-2239  
**优化 Skills**: kingdee-sdk-helper, kingdee-metadata-analyzer, kingdee-cosmic

---

## 总览

- **优化 Skills 数**: 3
- **总实验次数**: 3 轮
- **保留改进**: 3 次（100%）
- **回滚次数**: 0
- **实测验证**: 3 次完整测试（with_skill vs no_skill baseline）
- **平均提升**: +3.1 分

---

## 分数变化

| Skill | Before | After | Δ | 提升率 |
|-------|--------|-------|---|--------|
| kingdee-sdk-helper | 77.7 | 84.3 | +6.6 | +8.5% |
| kingdee-metadata-analyzer | 89.3 | 90.7 | +1.4 | +1.6% |
| kingdee-cosmic | 90.05 | 91.3 | +1.25 | +1.4% |
| **平均** | **85.7** | **88.8** | **+3.1** | **+3.6%** |

---

## 主要改进

### Round 1: kingdee-sdk-helper (77.7 → 84.3, +6.6分)

**改进内容**:
1. 补充触发词（SDK查询、API用法、方法签名、类定义、Javadoc、苍穹API）
2. 增加异常处理（uv环境缺失、脚本执行失败、sdk.json损坏）
3. 增加用户确认检查点（多条结果询问、代码示例前询问场景）

**维度提升**:
- Frontmatter质量: 7/10 → 9/10 (+2)
- 边界条件覆盖: 6/10 → 9/10 (+3)
- 检查点设计: 5/10 → 8/10 (+3)

**实测表现**:
- sdk-helper-p1: 防止场景假设错误
- sdk-helper-p2: 减少信息过载
- sdk-helper-p3: 环境异常可恢复

**Git Commit**: a260849

---

### Round 2: kingdee-metadata-analyzer (89.3 → 90.7, +1.4分)

**改进内容**:
1. 在快速工作流第8步增加用户确认检查点（展示关键发现摘要，询问是否深入分析）
2. 在 References 章节补充与 kingdee-sdk-helper 的协作说明

**维度提升**:
- 检查点设计: 7/10 → 9/10 (+2)
- 资源整合度: 9/10 → 10/10 (+1)

**实测表现**:
- metadata-analyzer-p1: 减少无效产出
- metadata-analyzer-p2: 不影响（持平）
- metadata-analyzer-p3: 提升效率

**Git Commit**: 2a4baf9

---

### Round 3: kingdee-cosmic (90.05 → 91.3, +1.25分)

**改进内容**:
1. 在 references/issue-analysis/examples.md 补充 5 个苍穹特定案例：
   - 案例二十二：afterBindData 生命周期 NPE
   - 案例二十三：beforeDoOperation 生命周期 NPE
   - 案例二十四：afterDoOperation 生命周期 NPE
   - 案例二十五：事务回滚导致数据不一致
   - 案例二十六：插件挂载点冲突
2. 在 SKILL.md 任务路由门禁表增强故障诊断引导（按生命周期定位 → 按错误类型分类 → 引用案例）

**维度提升**:
- 实测表现 - cosmic-p3: 7/10 → 9/10 (+2)

**实测表现**:
- cosmic-p1: 保持 9/10
- cosmic-p2: 保持 9/10
- cosmic-p3: 从通用 NPE 排查升级为苍穹生命周期专项诊断
- cosmic-p4: 保持 9/10

**Git Commit**: 2ce2482

---

## 优化规律总结

### 1. 边际递减规律
- Round 1 (+6.6分) > Round 2 (+1.4分) > Round 3 (+1.25分)
- 低分 skill 优化空间大，高分 skill 优化空间小

### 2. 优化策略分层
- **低分 skill（<80）**: 补充基础能力（边界条件、检查点、触发词）
- **中分 skill（80-90）**: 完善细节（用户确认、协作说明）
- **高分 skill（90+）**: 增强领域深度（案例库、诊断路径）

### 3. 关键维度
- **边界条件覆盖**（权重10）: 对低分 skill 影响最大
- **检查点设计**（权重7）: 防止自主失控，提升用户体验
- **实测表现**（权重25）: 最高权重，必须用独立子 agent 评估

### 4. 评估方法
- **结构评分**（60分）: 主 agent 可以做
- **效果评分**（40分）: 必须用独立子 agent，避免"自己改自己评"
- **with_skill vs no_skill baseline**: 关键对比，判断 skill 真实价值

---

## 验证方式

### 测试 Prompt 设计
- 每个 skill 设计 2-4 个测试 prompt
- 覆盖 happy path + 边界情况
- 明确 expected、eval_focus、baseline_risk

### 独立子 Agent 评估
- 每轮优化后 spawn 独立子 agent 重新评估
- 对比 with_skill vs no_skill 输出质量
- 记录 skill_delta（-2 到 +2）

### Git 版本控制
- 每轮改进创建独立 commit
- 新分 > 旧分 → keep
- 新分 ≤ 旧分 → revert（本次优化无回滚）

---

## 后续建议

### 1. 持续优化
- 定期（每月）运行 Darwin 评估，跟踪 skill 质量变化
- 新增 skill 后立即评估基线分数

### 2. 测试 Prompt 维护
- 根据实际使用场景更新测试 prompt
- 补充边缘 case 和失败场景

### 3. 案例库扩充
- kingdee-cosmic 的 examples.md 持续补充新案例
- 其他 skills 也可建立案例库

### 4. 跨 Skill 协作
- 继续完善 skill 间的协作说明
- 建立 skill 调用链路图

---

## 附录

### Git 提交记录
```
a260849 - optimize kingdee-sdk-helper: 补充边界条件处理、用户确认检查点和触发词
2a4baf9 - optimize kingdee-metadata-analyzer: 增加用户确认检查点和 SDK 查询协作说明
2ce2482 - optimize kingdee-cosmic: 增强故障诊断资料和引导
```

### Results.tsv 记录
```
2026-04-29T[时间]	a260849	kingdee-sdk-helper	77.7	84.3	keep	边界条件+检查点+触发词	补充异常处理、用户确认点和触发词，提升6.6分	full_test	default	+9.0
2026-04-29T[时间]	2a4baf9	kingdee-metadata-analyzer	89.3	90.7	keep	检查点+资源整合	增加用户确认点和SDK协作说明，提升1.4分	full_test	default	+9.0
2026-04-29T[时间]	2ce2482	kingdee-cosmic	90.05	91.3	keep	故障诊断增强	补充5个生命周期NPE案例和诊断引导，提升1.25分	full_test	default	+8.5
```

---

**报告生成时间**: 2026-04-29  
**优化工具**: Darwin Skill v1.0  
**评估模型**: Claude Opus 4.7
