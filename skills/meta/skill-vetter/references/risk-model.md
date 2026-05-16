# 风险模型

## 风险等级

### `critical`
- 明显 destructive：
  - `rm -rf`
  - `git reset --hard`
  - `git checkout --`
- 远程命令直接执行：
  - `curl | sh`
  - `wget | bash`
- 明显覆盖宿主目录且带 destructive 语义

### `high`
- 写入或重连宿主 skills 目录
- 软链接覆盖、强制复制、替换现有目录
- 代码里直接调用系统命令执行器
- 需要人工确认的安装脚本、setup 脚本

### `medium`
- 联网安装命令
- 绝对路径、用户目录硬编码
- Token、密码、Basic Auth 或 API key 提示
- 多个候选 `SKILL.md`、结构不清晰

### `low`
- 多余 README/说明文档
- 额外的宿主说明文件
- 未必危险但需要了解的兼容性提示

## 推荐等级

### `allow`
- 没有 `critical`
- 没有 `high`
- 只有少量 `low`，或完全无风险项

### `review_needed`
- 没有 `critical`
- 但存在 `high` 或 `medium`
- 或者静态证据不足，必须人工看安装脚本/宿主集成文件

### `block`
- 任何 `critical`
- 或多条 `high` 且集中指向 destructive 安装/覆盖路径
- 或结构已无法可靠判断真实行为
