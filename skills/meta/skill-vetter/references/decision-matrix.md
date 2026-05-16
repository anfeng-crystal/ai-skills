# 决策矩阵

## 典型 `allow`
- 只有 `SKILL.md`、`references/`、少量只读脚本
- 没有安装脚本
- 没有宿主目录写入
- 没有 destructive 命令和远程执行

## 典型 `review_needed`
- 有 `install.sh`、`setup-*.sh`、`bootstrap` 脚本
- 有 `npm install`、`git clone`、`uv tool install`
- 有 `AGENTS.md`、`CLAUDE.md`、宿主命令目录
- 有软链接、复制、目标目录写入逻辑
- 有硬编码用户路径或凭据占位

## 典型 `block`
- 安装脚本里直接 `rm -rf` 宿主目标目录
- `curl | sh`、`wget | bash`
- 强覆盖宿主技能目录且无人工确认门禁
- 明显 destructive + 宿主写入同时出现

## 使用建议
- `allow`：可以继续进入 `skill-installer` 或手工分发流程
- `review_needed`：先看脚本和宿主集成文件，再决定是否安装
- `block`：默认不要继续；除非用户明确接受风险并改写目标 skill
