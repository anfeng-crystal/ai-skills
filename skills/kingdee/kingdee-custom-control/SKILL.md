---
name: kingdee-custom-control
description: "从零设计、创建、修复、验证、构建、打包和交付金蝶云苍穹 KDApi 前端自定义控件。用于自定义控件方案、index.js 生命周期、handleDirective/triggerCustomMsgEvent/model.invoke、PC/移动端控件工程、版本化运行包、服务端插件联调和目标环境验收；仅有页面脚本联动时使用 kingdee-frontend-script。"
---

# Kingdee Custom Control

> Cross-platform Agent Skill: 使用 UTF-8、宿主中立路径和 Python/Node 标准库；不写死本机开发目录。

## 触发与路由

- 本 skill 负责独立自定义控件的完整工程和交付闭环，不把“页面脚本能调用控件”当成控件已开发完成。
- 仅编写页面侧 `this.$(...).invoke/onCustomMsgEvent` → `kingdee-frontend-script`。
- Java/KingScript 服务端 `customEvent`、`CustomControl.setData` → 分别加载 `kingdee-cosmic` / `kingdee-kingscript`；本 skill 保持前后端事件与数据合同一致。
- 表单、控件、方案、领域或模块标识取证 → `kingdee-metadata-analyzer`；SDK 签名 → `kingdee-sdk-helper`；批准后的页面安装和 E2E → `kingdee-ui-testing`。

## 模式与完成定义

| 模式 | 完成条件 |
|---|---|
| `author` | 工程已生成或修复，源码静态校验和本地单元测试通过 |
| `release` | 测试、构建、包内校验通过；ZIP、SHA-256 和交付 manifest 已生成 |
| `deploy-approved` | 精确环境/页面/方案/动作/回滚合同已批准，上传绑定后完成目标版本运行验证 |

`release` 不等于平台运行通过。按当前模式核对其实际依赖的目标苍穹版本、方案 ID、领域/模块、目标端和数据合同；缺失时先从已有工程和已授权证据补齐，只暂停依赖缺失事实的步骤。保留未知目标版本时的候选工程和候选本地 release 能力，按 helper 既有候选合同如实标记版本未确认及平台/运行 `not-run`，不伪填版本。方案等脚手架必填标识仍不能猜；没有运行授权时最多交付本地产物。

生成或修改面向目标平台的接口代码前，沿用任务已确认的产品版本，核对当前项目依赖、目标 KDApi/服务端 SDK 声明、目标模板或带适用版本的官方依据。候选脚手架仍可按前段生成，此检查决定何时可将其中接口作为目标实现，不取消候选能力。未指定版本时先自主读相关工程与非敏感版本配置，仍缺关键依据才问；用户指定版本与实际依赖/页面证据冲突时，先报告冲突，不自行升级。

`7.0` 且补丁未知不能自动认定 `7.0.4+` 新生命周期或 `8.0.1` 属性/服务端接口可用；目标声明能证实本次接口时可继续，不为补全补丁号或每个 API 重复询问。仅暂停将未知接口作为目标实现的部分，继续候选产物及独立工作；模板、profile 名和本地校验不替代兼容依据，也不能用它们伪填版本。显式 modern profile 仍要求已核实 `7.0.4+`。

## 工作流

1. 按当前模式和改动依赖核对：目标苍穹版本、PC/移动端、`controlId == schemeId`、领域、模块、目标表单、前后端事件、输入输出 JSON、第三方依赖许可证和验收场景。先复用已有工程与已授权证据；标识和版本不能猜。
2. 仅新建工程时从 skill 根运行脚手架；输出目录必须为空或不存在。已有工程修复直接使用现有目录，跳过初始化：
   ```bash
   python3 scripts/custom_control.py init --project <project> --control-id <id> --display-name <name> --domain <domain> --module <module> --platform-version <version> --targets pc,mobile
   ```
   Windows 可用 `py -3 scripts\custom_control.py ...`。
3. 默认修改目标工程的 `src/` 和 `tests/`。读取 `references/runtime-contract.md`；默认新建仍使用经典候选 profile，不自动升级生命周期。修复已有 V7.0.4+ 新生命周期工程时，按目标版本证据显式使用 `runtimeContract: "modern-kdapi-v7.0.4"`；拿到目标环境官方模板后以其为准，并更新 `cosmic-control.json` 的证据字段。
4. 按当前模式执行适用的本地检查与交付步骤：
   ```bash
   python3 scripts/custom_control.py validate --project <project> --fix
   python3 scripts/custom_control.py test --project <project>
   python3 scripts/custom_control.py build --project <project>
   python3 scripts/custom_control.py release --project <project> --output-dir <release-dir>
   python3 scripts/custom_control.py verify-package --project <project> --archive <zip>
   ```
   `--fix` 只修复可证明的方案 ID/注册 ID 偏差；生命周期、消息语义和业务逻辑不做猜测式重写。
5. 需要服务端时，先固定事件名、请求/响应 schema、错误语义和幂等边界，再交对应服务端 skill 实现；前端测试保留同一合同样例。
6. 需要真实交付时，读取 `references/delivery-contract.md`。批准后上传 ZIP、绑定同名控件方案，按 `references/testing-contract.md` 验证加载、更新、三条通信链、销毁清理和回滚。

## 门禁

- `index.js` 的 `KDApi.register` 标识必须与配置和平台方案 ID 完全一致；内置 `flat-runtime-root` 候选 profile 的 ZIP 根直接包含 `index.js`，目标版本官方包格式有证据时才可覆盖。
- 生命周期按 profile 校验：经典工程保留 `init/update`；已确认 V7.0.4+ 的现代工程使用 `init` 与所需的新更新钩子，不能同时保留旧 `update`。官方 KDApi 销毁入口为 `destoryed`；内置经典模板另保留幂等 `destroyed` 别名以兼容候选资料，该别名不是官方要求。仅使用别名时仍须目标证据，清理不能省略。
- DOM 查询限定在 `model.dom`；全局监听、定时器、图表实例和第三方组件必须在销毁阶段释放。
- 不把源码、测试、`.env`、凭据、内部 URL、source map、构建缓存或宿主绝对路径打进运行包。
- 外部框架工程的 build/test 命令先审查，再显式传 `--run-command`；脚本不通过 shell 拼接命令。
- `author` 只按本地源码、测试、构建和包结构报告；局部检查通过不能写成整个 `author` 或 `release` 通过。候选工程可完成本地 release；必须确认目标版本合同后，才能称为目标兼容/可部署的版本化包。版本未确认不阻断候选本地产物，只将依赖目标兼容证据的验证和平台交付步骤标为 `blocked`/`not-run`，不绕过脚本校验。平台运行回滚不可用时，将 `platformInstall`/`runtimeVerification` 标为 `blocked` 或 `not-run`，不得把本地 release 写成平台已验证。`deploy-approved` 才要求目标运行回滚合同可用。
- 生产只接收已在开发/测试验证的不可变包；不在生产现场修改控件元数据或执行更新类测试。

## 资源

- `scripts/custom_control.py`：初始化、确定性修复、静态校验、测试、构建、打包、release 和包复验。
- `assets/classic-control/`：无第三方运行依赖、待目标版本验证的 KDApi 候选工程。
- `references/runtime-contract.md`：生命周期与三条通信链。
- `references/testing-contract.md`：分层验证和失败状态。
- `references/delivery-contract.md`：包格式、平台安装、运行验收和回滚合同。

## 输出

使用简体中文：模式与结论 → 项目/控件标识 → 版本证据 → 自动修复 diff → 静态/单元/构建/包校验 → ZIP 与 SHA-256 → 平台运行状态 → 回滚/残留风险。把 `pass`、`fail`、`blocked`、`not-run` 分开。
