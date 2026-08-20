# 发布授权与来源矩阵

记录金蝶 skill 公开发布(GitHub)前,每个二进制 / 大文件 / 外部知识来源的处置。处置类型:`publish`(确认可再分发)/ `link-only` / `fetch`(首次运行拉取)/ `generate-local`(本地生成)/ `exclude`(不进发布集)。**不能一概标 MIT**;凡"待授权"项在用户确认前不得 `publish`。

## 大文件 / 二进制(git 已跟踪)

> **授权状态:用户已批准再分发(2026-06-13)。** 下列条目随仓库 `publish`。第三方开源 jar 按其自身 license 保留(需在发布说明标注)。

| 条目 | 大小 | 性质 | 处置 |
|---|---|---|---|
| `kingdee-sdk-helper/assets/sdk.json` | 47MB | 金蝶 SDK/Javadoc 索引 | `publish`(<50MB,GitHub 可直推;后续如增大可转 LFS) |
| `kingdee-cosmic/setup/setup.jar` | 3.1MB | 平台二进制 | `publish`(已授权) |
| `kingdee-cosmic/setup/ok-cosmic-docs.db` | 9.1MB | 知识库 db | `publish`(已授权) |
| `kingdee-metadata-analyzer/scripts/cfr-0.152.jar` | 2.1MB | CFR 反编译器(MIT/GPL,见其声明) | `publish` + 标注 CFR license |
| `kingdee-cosmic/scripts/scan/javaparser-core-3.25.8.jar` | 1.4MB | JavaParser(Apache-2.0/LGPL 双授权) | `publish` + 标注 JavaParser license |
| `kingdee-kingscript/references/sdk/manifests/types.json` | 2.3MB | SDK 类型清单 | `publish`(已授权) |
| `kingdee-kingscript/references/sdk/manifests/const-exports.json` | 2.2MB | SDK 常量清单 | `publish`(已授权) |
| `iscb-script/assets/isc-iscb-util.jar` | 1.5MB | ISCB 运行时 | `publish`(已授权) |

> 注:`.gitignore` 含 `*.jar`/`*.db` 规则,但上述已被强制跟踪的 jar/db 维持跟踪并随仓库发布(已授权)。第三方开源 jar 的 license 在发布 README/NOTICE 中标注。

## 知识/源码来源

| 条目 | 处置 | 说明 |
|---|---|---|
| rpt-gen 65 实战报表源码 | `exclude` 原文 | 仅 `publish` 已脱敏的模式/签名(已落入 kingdee-report,无业务字段) |
| ISC 90+ 错误库文本 | `exclude` | 低增量诊断 skill 及其两张路由表已移除，发布集不含该错误库原文或改写目录 |
| Algo/SDK 方法签名 | `publish` | 已在 kingdee-report/算子文档中以手写签名表呈现,非 sdk.json 原文搬运 |

## 失败条件(发布门禁)
- 任一"待授权"项在用户确认前被标 `publish` → 停止发布。
- 发布集出现未授权二进制、真实内网信息、私有路径、密码/手机号 → 停止,继续脱敏。
