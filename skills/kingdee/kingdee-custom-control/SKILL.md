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

`release` 不等于平台运行通过。没有目标苍穹版本、方案 ID、领域/模块、目标端或数据合同时，只能停在需求合同；没有运行授权时最多交付本地产物。

## 工作流

1. 确认：目标苍穹版本、PC/移动端、`controlId == schemeId`、领域、模块、目标表单、前后端事件、输入输出 JSON、第三方依赖许可证和验收场景。标识和版本不能猜。
2. 从 skill 根运行脚手架；输出目录必须为空或不存在：
   ```bash
   python3 scripts/custom_control.py init --project <project> --control-id <id> --display-name <name> --domain <domain> --module <module> --platform-version <version> --targets pc,mobile
   ```
   Windows 可用 `py -3 scripts\custom_control.py ...`。
3. 默认修改生成工程的 `src/` 和 `tests/`。读取 `references/runtime-contract.md`；内置经典工程是候选 profile，不是跨版本官方模板。拿到目标环境官方模板后以其为准，并更新 `cosmic-control.json` 的证据字段。
4. 运行闭环：
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
- `init/update` 必须存在；内置候选 profile 同时提供幂等 `destoryed/destroyed` 清理入口。目标版本只使用其中一个时必须保留版本证据。
- DOM 查询限定在 `model.dom`；全局监听、定时器、图表实例和第三方组件必须在销毁阶段释放。
- 不把源码、测试、`.env`、凭据、内部 URL、source map、构建缓存或宿主绝对路径打进运行包。
- 外部框架工程的 build/test 命令先审查，再显式传 `--run-command`；脚本不通过 shell 拼接命令。
- 校验失败、测试缺失、包结构不符、版本合同未确认或运行回滚不可用时，不得报告“可交付”或“已验证”。
- 生产只接收已在开发/测试验证的不可变包；不在生产现场修改控件元数据或执行更新类测试。

## 资源

- `scripts/custom_control.py`：初始化、确定性修复、静态校验、测试、构建、打包、release 和包复验。
- `assets/classic-control/`：无第三方运行依赖、待目标版本验证的 KDApi 候选工程。
- `references/runtime-contract.md`：生命周期与三条通信链。
- `references/testing-contract.md`：分层验证和失败状态。
- `references/delivery-contract.md`：包格式、平台安装、运行验收和回滚合同。

## 输出

使用简体中文：模式与结论 → 项目/控件标识 → 版本证据 → 自动修复 diff → 静态/单元/构建/包校验 → ZIP 与 SHA-256 → 平台运行状态 → 回滚/残留风险。把 `pass`、`fail`、`blocked`、`not-run` 分开。
