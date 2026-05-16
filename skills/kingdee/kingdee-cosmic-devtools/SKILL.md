---
name: kingdee-cosmic-devtools
description: Kingdee devtools: KDDT project creation, plugin class gen, resource pack staging/apply/rollback.
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [kingdee, cosmic, devtools, gradle, plugin]
---

# Kingdee Cosmic DevTools

> **Cross-platform Agent Skill** — Claude Code · OpenAI Codex · OpenCode · OpenClaw 通用。
> 跨平台 SKILL.md，遵循开放 Agent Skill 规范。

## 路由边界
- 本 skill 只负责工程骨架、模块模板、插件/服务类模板和 `COSMIC_HOME` 资源环境处理。
- 业务插件逻辑、运行时诊断和最终改造收口交给 `kingdee-cosmic`；实体、字段、表单或插件挂载证据交给 `kingdee-metadata-analyzer`；SDK/API 签名查询交给 `kingdee-sdk-helper`。
- 工具任务完成后，将工程、模块、文件路径、资源包 manifest、校验结果或 rollback 信息交回当前主控任务。

## 快速工作流
脚本只依赖 Python 标准库，从 skill 根目录运行。

```bash
python scripts/kddt_devtools.py --help
```

Windows 可用：

```powershell
py -3 scripts\kddt_devtools.py --help
```

1. 先用 `inspect --project <工程根目录>` 判断现有工程是否有 `project_flag`、`COSMIC_HOME`、资源 URL 和模板类型。
2. 创建完整工程用 `create-project`；`project_flag` 可空，空值走旧模板，非空走新模板。
3. 新增模块用 `add-module`；只解压 `*-sub.zip` 增量模板，并补 `settings.gradle` 与调试工程依赖，不创建完整工程。
4. 生成插件或服务用 `create-plugin --kind inherit|extend|service`；默认不覆盖同名文件。
5. 更新环境用 `update-env start/status/resume/apply/rollback`；下载进 staging，校验通过后再短锁应用到 `COSMIC_HOME`。资源包拉取任务必须按“预检 -> 新 staging -> 下载/续传 -> 清单核验 -> apply/回滚”的闭环执行，不要直接把远端包解压到目标目录。

## 资源包下载与更新

适用于用户要求“从 appstore/dev_env 拉取最新资源包”“更新 COSMIC_HOME”“生产/dev 包对比吸收”等场景。

1. 预检目标路径：确认 `COSMIC_HOME`、`mservice-cosmic/lib`、`static-file-service`、磁盘剩余空间、当前进程是否占用目标目录；若目标目录是隐藏目录或受权限限制，先请求/确认写入授权再动手。
2. 预检远端：优先拉取 `update.json`，失败再用 `update.md5`；记录远端 URL、manifest 类型、包数量、MD5/sha1 摘要和缺失项。服务刚恢复时先做一次只读 manifest 检查，不直接 apply。
3. 下载必须落到新的 staging 或新目录，不直接覆盖现有 `COSMIC_HOME`。使用 `update-env start --foreground` 便于实时看到失败点；失败后先查 `status` 和 `worker.log`，再用 `resume --foreground` 续传，避免从头下载。
4. 下载完成后先核验：文件数、总大小、每个 zip/jar 的摘要、是否存在多级目录嵌套、`cus/biz/bos/trd` 是否平铺。发现 `cus/<模块>/<jar>` 这类多级目录时，先生成修正清单并移动到平铺目录，再继续。
5. apply 前必须输出审核摘要：新增、覆盖、同 sha1 跳过、低版本被高版本替代、缺失但本地启动需要保留、将进入 `.quarantine` 的项。用户未明确授权时，只停在 staging 和报告。
6. apply 后立即验证：`cosmic_libs_path` 指向目标目录，`./gradlew ... :ztjg-cosmic-debug:classes` 通过，本地首页至少能到登录页；如失败，执行 `rollback` 或按报告恢复 `.quarantine`。
7. 生产包吸收只复制明确缺失或经比对确认更完整的定制包；Qing/DPP、ISC/DTS、Eye、KingScript 这类平台扩展点包必须单组隔离/恢复验证，不能和业务 jar 批量混动。

常用命令：

```bash
python scripts/kddt_devtools.py update-env start --project <工程根目录> --cosmic-home <目标COSMIC_HOME> --res-url <资源地址> --foreground
python scripts/kddt_devtools.py update-env status --cosmic-home <目标COSMIC_HOME>
python scripts/kddt_devtools.py update-env resume --cosmic-home <目标COSMIC_HOME> --foreground
python scripts/kddt_devtools.py update-env apply --cosmic-home <目标COSMIC_HOME>
python scripts/kddt_devtools.py update-env rollback --cosmic-home <目标COSMIC_HOME> --backup <备份目录>
```

## 输入口径
- `developer_flag`：必填，小写字母开头，2-4 位小写字母或数字。
- `project_flag`：可空；老项目没有项目标识时必须保持空，不要强行补默认值。
- `cloud_flag`：必填，小写字母开头，2-17 位小写字母或数字。
- `app_flag`：必填，小写字母开头，2-22 位小写字母或数字。
- `template_type`：只能是 `app`、`cloud`、`multi`。
- 缺少关键输入且用户允许交互时，加 `--interactive` 让脚本询问；不要复刻 IDEA UI。

## 资料入口
- 模板映射和命名规则：`references/template-map.md`
- 资源更新协议和目录规则：`references/env-update.md`
- 内置模板资产：`assets/kddt/2.3.5-GA/`

## Guardrails
- 新增模块必须使用 `*-sub.zip`，不能用完整工程模板。
- 无项目标识的老工程不能写入 `systemProp.project_flag` 或 `COSMIC_PROJECT_FLAG`，除非用户明确要求迁移工程结构。
- `update-env start` 只下载到 staging；真实替换必须执行 `update-env apply`。
- `apply` 前必须有 job manifest、校验记录和备份目录；失败时提示 `rollback`。
- 远端访问不稳定、下载中断、目录权限异常、文件数为 0、Finder 里看不到包、包落到多级目录、MD5/sha1 不一致时，先停在 staging 并报告失败项；不要猜测成功，也不要清理旧包。
- 清理重复/低版本包只移动到 `.quarantine`，除非用户明确说“可以清理/删除”；平台扩展点包恢复或隔离后必须核验目标路径是否真的存在/不存在。
- 不把本次排查过程、实现取舍或临时路径写进生成的工程代码注释。
