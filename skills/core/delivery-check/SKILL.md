---
name: delivery-check
description: "Use before commit, push, merge, package, release, publish, skill sync, or when asked 能不能交付/能不能发版/发布前检查. Not for code review, implementation, cleanup, or install/apply actions."
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [delivery, release, readiness, git, package, verification]
---

# Delivery Check

> Cross-platform Agent Skill: evidence-based readiness only, preserve unrelated worktree changes, and avoid destructive git actions.

## 触发
- commit、push、merge、package、release、publish、PR、skill sync 前，或用户问“能不能交付/能不能发版/能不能 push”时使用。
- 只做 readiness 判断；不做代码审查、不实现修复、不清理文件、不 install/apply 链接、不发布，除非用户明确要求继续执行。

## 契约
- 只输出一个判断：`ready`、`blocked` 或 `ready with risks`。
- 判断必须基于当前证据：工作树、diff、测试/build/lint、doctor、manifest/package/release 状态、远端状态和 dry-run。
- 缺失验证是风险或阻塞，不能当作通过。
- dry-run 只能证明计划，不证明动作已经执行。

## 工作流
1. 定交付目标：commit、push、merge、package、release、publish、PR、skill sync 或 readiness only。
2. 读 `git status --short --branch -uall`，区分 intended、unrelated、untracked、staged 和 generated 文件。
3. 将每个目标文件或产物映射到交付目标；不清楚的文件排除在 ready 范围外。
4. 跑或检查项目本地验证：diff check、相关测试、lint/build/doctor、package 内容、版本/manifest、tag/release/origin/CI 和相关 dry-run。
5. 按顺序判断：先列 blocker，再列 risk，最后列已验证证据。
6. 只有用户已明确要求，且判断允许，才继续 stage、commit、push、tag、release、publish、install 或 apply。

## Skills Source Hints
- 在 skills source root 中，优先使用存在的验证器：`git diff --check -- <target-files>`、`node scripts/doctor.mjs --json`、`node scripts/validate-cross-platform.mjs`、`node meta/darwin-skill/scripts/validate-skill-assets.mjs`、`node meta/skill-installer/bin/skill-installer.mjs --json`。
- 从 cwd、`AI_SKILLS_HOME` 或项目配置解析 source root；不要写死用户 home。
- 仓库外任务使用本地项目规则和验证命令，不套用 skills 仓库命令。

## 门禁
- 不 stash、reset、checkout、clean、隐藏用户文件或做破坏性 git 操作。
- 清理删除转 `cleanup-guard`。
- 不把 dry-run 当执行结果。
- 不接受只由子代理完成的验证。
- 没有当前命令输出时，不声明 verified、released、synced 或 pushed。

## 输出
交付判断 -> 阻塞项 -> 已验证证据 -> 未覆盖/风险 -> 下一步。
