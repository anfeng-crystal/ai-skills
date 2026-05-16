# 多 Agent 代码注释策略

- Coding Worker 生成或修改代码时，必须遵循目标仓库、目标 skill 或用户指定的注释策略。
- Coordination Plan 中涉及代码实现时，应把“稳定注释/Docstring 要求”写入 Shared constraints 或 Worker scope。
- Worker 交付前自查新增/修改的文件、类、公共方法、复杂私有函数、关键业务规则、资源/异常/异步/事务边界是否有功能性注释。
- Reviewer 需要检查两类问题：缺少必要注释，以及过程性、机械复述或逐行翻译注释。
- 主 agent 集成时不接受“代码可运行但完全没有可维护注释”的 Worker 结果；应要求补注释或把风险列入剩余风险。
