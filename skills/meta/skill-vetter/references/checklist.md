# 审查清单

`skill-vetter` v1 先检查这些项目：

## 1. 路径与结构
- 输入路径是否存在
- 是否能唯一定位到一个 `SKILL.md`
- `SKILL.md` frontmatter 是否包含 `name` 和 `description`
- 是否混入大量与 skill 无关的安装文档、流程文档或打包残留

## 2. 宿主集成风险
- 是否写入或覆盖：
  - `~/.codex/skills`
  - `~/.claude/skills`
  - `~/.agents/skills`
  - `~/.junie/skills`
- 是否包含 `AGENTS.md`、`CLAUDE.md`、安装脚本、命令目录等宿主特化文件

## 3. 危险命令
- `rm -rf`
- `git reset --hard`
- `git checkout --`
- `curl | sh` / `wget | bash`
- 强制复制或删除宿主目录

## 4. 联网与安装行为
- `git clone`
- `npm/pnpm/yarn/pip/uv/brew install`
- 下载远程资源
- 自带 setup / install / bootstrap 脚本

## 5. 代码执行与系统调用
- `child_process.exec/spawn`
- `subprocess.run/Popen`
- `os.system`
- `shell=True`
- `eval` / `new Function`

## 6. 路径与凭据
- 绝对路径、用户目录硬编码
- Token、API key、密码、Basic Auth 提示
- 写死的主机地址、企业内网地址、用户环境假设

## 7. 决策
- 只有结构完整且未发现显著风险时，才建议 `allow`
- 有脚本、联网、宿主写入、软链接、安装行为时，通常至少 `review_needed`
- 有 destructive 或远程执行模式时，直接 `block`
