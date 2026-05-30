---
name: neat-freak
description: "当前会话的持久事实可能需要同步到项目 docs、README、AGENTS/CLAUDE 指令或宿主 memory 建议时使用。"
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [knowledge, cleanup, docs, memory, sync]
---

# Neat Freak

> Cross-platform Agent Skill: 只沉淀能减少未来歧义的稳定事实；没有用户明确要求且宿主允许时，不写 memory。

## 触发
- 实现、排障、发布、工具配置、架构决策后，项目持久知识可能过期时使用。
- 文件清理转 `cleanup-guard`。
- SKILL.md 质量优化转 `darwin-skill`。

## 契约
- 项目 docs / README / AGENTS / CLAUDE 要么更新到当前事实，要么明确判断无需改。
- 证据来自本轮变更、当前仓库文档、最近 AGENTS/CLAUDE 规则、README、docs 索引和宿主 memory 策略。
- memory 只有用户明确要求且宿主允许时才写；否则只输出建议写入内容和未写原因。

## 工作流
1. 识别本轮涉及的项目；不要把 shell cwd 当唯一项目。
2. 每个项目先枚举文档，再判断：
   ```bash
   ls
   ls docs 2>/dev/null || true
   find . -maxdepth 2 -name "*.md" -not -path "*/node_modules/*" -not -path "*/.git/*"
   ```
3. 只读相关的 `README.md`、`AGENTS.md`、`CLAUDE.md`、`docs/*.md`。
4. 按层归位稳定事实：
   - 项目指令：长期 agent 规则、路由、红线、环境假设。
   - README/docs：面向使用者的安装、API、架构、runbook、handoff。
   - memory：跨会话偏好或非显而易见的项目事实；只在明确要求时写。
5. 优先修改旧条目；明确过期或重复时删除旧事实。
6. 时间相关事实用绝对日期，不写“今天、最近、yesterday、recently”。
7. 复查文档里的命令、路径、环境变量和链接是否存在。

## 变更映射
- 新增 API / 路由：项目指令里的路由清单 + integration guide + architecture routes。
- 新增/改名环境变量：项目指令 + runbook + 下游 integration guide。
- 新增数据表/实体：项目指令 + architecture data model。
- 跨文件大特性：architecture、runbook、handoff/CHANGELOG 视项目已有结构同步。
- 跨项目改动：上下游 docs 都要检查，不能只改当前项目。
- 对话没有新事实：仍检查相对时间、过期事实、重复事实和已完成待办。

## Memory 边界
- Codex memory：只读当前任务相关 memory；不枚举全局 memory；不主动写入。
- Claude/其他宿主 memory：按宿主策略；写权限不清时输出建议，不直接写。
- 不沉淀密钥、cookie、带 token 的私有 URL、一次性排障日志或实施过程。

## 编辑规则
- 只写稳定事实，不写“本次排查过程”、聊天记录、临时计划或工具日志。
- 代码注释、README、docs、skills、memory 各写给自己的受众，不跨层复制长段落。
- 修改顺序优先项目 docs / README，再改 AGENTS/CLAUDE，最后处理 memory 建议。
- API 文档优先写“怎么用”，architecture 写“怎么工作”，runbook 写“怎么运维”，handoff/CHANGELOG 写“已完成”。
- 全局指令只为用户明确建立的跨项目规则修改。
- 两个持久事实冲突且当前证据无法解决时，停止并列出冲突。

## 自检
- 枚举过的每个 Markdown 文件都标记为已改或不用改。
- AGENTS/CLAUDE/README/docs 提到的路径、命令、环境变量真实存在。
- 记忆建议之间不互相矛盾，且不含相对时间。
- 本轮跨项目时，下游接入文档已检查。

## 输出
简体中文：
- 结论：已同步 / 无需改 / 阻塞。
- 变更：file -> 修改的稳定事实。
- Memory：已写 / 建议写 / 跳过及原因。
- 未处理：冲突、缺失文档或验证缺口。

## 参考资料
- 宿主路径：`references/agent-paths.md`
- 文档映射：`references/sync-matrix.md`
