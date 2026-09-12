# Hermes 分发排障

仅在使用 Hermes external_dirs、遇到同名入口或误以为需要重新安装时读取。

## Hermes 特有问题

### Hermes external_dirs 下同名 skill 分别在根目录和分类子目录会触发 ambiguous skill 错误
源目录中如果同时存在 `<skill>/SKILL.md` 和 `skills/<category>/<skill>/SKILL.md` 两个同名入口，Hermes 扫描会报 ambiguous skill 并阻塞 `skill_view` 和技能加载。
- **修复**：从源目录删除/合并重复入口，只保留一个 SKILL.md。分类目录优先，避免裸根 duplication。
- **注意**：这不是 install/sync 脚本能自动处理的，需要在源技能仓库归一化 skill 的位置。

### Hermes `external_dirs` 模式下无需"重新安装"
如果 `~/.hermes/config.yaml` 的 `skills.external_dirs` 已指向源目录，Hermes 直接从源目录实时读取技能——远端更新拉取后自动生效。此时 `install.mjs` 会报告所有技能为 `managed_via_external_dir` / `wouldChange: 0`，不需要也不应该做额外安装或 symlink 操作。
