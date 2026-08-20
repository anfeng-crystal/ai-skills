# 构建与交付合同

## 工程配置

`cosmic-control.json` 是工具合同，不进入运行包。关键字段：

- `controlId/displayName/version/runtimeContract/targets`
- `platform.schemeId/domain/module/forms`
- `platformEvidence.version/source/verifiedAt`
- `features.pageInvoke/pageEvents/serverInvoke`
- `sourceDir/build.mode/build.outputDir`
- `test.mode/test.files`

路径必须是工程内相对路径。`static` 构建只复制 `sourceDir`；`external` 构建先清空精确 outputDir，再在审查命令后用 `--run-command` 执行 JSON 参数数组并复验新产物，禁止复用旧 dist。

## Release 产物

完整 release 生成：

- `<controlId>-<version>.zip`：上传包；压缩包根直接含 `index.js`。
- `<controlId>-<version>.zip.sha256`：可复算摘要。
- `<controlId>-<version>.delivery.json`：配置摘要、文件清单、各门禁状态和运行验证状态。

ZIP 使用稳定文件顺序、POSIX 条目名和固定时间戳；拒绝越界、符号链接、Windows 名称碰撞、压缩炸弹和损坏 CRC，并在受限临时目录复用完整运行时校验。源码、测试、工具、配置、缓存、凭据和内部地址不得进入包。`flat-runtime-root` 是内置候选 profile 的布局，只有目标版本证据才能把它标成已验证上传格式。

KDDT 2.3.5-GA 官方工程模板可证实源码侧静态资源根采用 `webapp/isv/<developer_flag>/`，运行 Web 路径由环境配置；它不能证明自定义控件 ZIP 子结构。发现项目目录和 `COSMIC_HOME` 路径，不写 Windows 固定目录。

## 平台安装合同

真实安装前必须确认：

- 环境和苍穹版本；账号权限；应用/领域/模块；目标表单和自定义控件 key。
- 新建或更新的控件方案 ID，且与 `KDApi.register` 完全一致。
- 上传、绑定、保存/发布是否写平台配置；影响页面和用户范围。
- 旧 ZIP/旧方案绑定的备份位置、回滚步骤和验收窗口。

批准后只执行合同内对象：在开发/测试上传目标 profile 产物 → 绑定方案 → 保存/发布 → 清缓存或刷新（仅在目标版本要求时）→ safe smoke → 通信/E2E → 销毁检查。不要扩到其他表单、方案或生产数据。生产只部署已验证不可变包，不现场修改元数据或做更新类测试。

## 完成与回滚

交付状态分别记录：

- `localRelease`: pass/fail
- `platformInstall`: pass/fail/blocked/not-run
- `runtimeVerification`: pass/fail/blocked/not-run
- `rollback`: verified/available/not-defined

运行失败时先保存脱敏网络/控制台/服务端证据，再恢复旧 ZIP 或旧方案绑定并复验。回滚未定义或失败时停止后续安装，不用重复覆盖掩盖问题。
