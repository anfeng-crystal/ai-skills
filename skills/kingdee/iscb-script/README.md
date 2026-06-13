# ISCB Script Skill Bundle

## 1. 这是什么

这是一个面向 ISCB 集成云 DSL 脚本的专用 skill bundle。

它的目标不是“自由发挥写脚本”，而是在一个可验证、可维护、可分发的边界内稳定完成这些任务：

- 生成 ISCB 脚本
- 解释已有脚本
- 重构或修复脚本
- 查询函数和语法用法
- 在用户明确要求时做静态校验、编译校验或运行验证
- 在用户明确要求时保存到本地

默认行为保持收敛：

- 默认按普通引擎脚本处理
- 默认不自动运行
- 默认不自动保存
- 默认沿用用户给定变量名和数据结构
- 平台层缺资源时只给参考脚本，不宣称本地可运行

## 2. 架构设计

这套 bundle 采用“三层闭环”的结构：

1. 文档层：`SKILL.md` + `references/`
2. 静态能力层：`tools/engine_api_manifest.json` + `tools/iscb_skill_validator.py`
3. 真实运行时层：`isc-iscb-util.jar` + `tools/script_runtime_real.py` + `tools/script_runtime_main/ScriptRuntimeMain.java`

其中各层职责如下：

- `SKILL.md`：定义主行为、上下文路由、输出契约、反幻觉规则
- `references/`：按需提供详细函数文档、上下文约定、语法说明、业务模式
- `engine_api_manifest.json`：引擎能力基线
- `iscb_skill_validator.py`：文档审计、脚本校验、curated case 回归、聚合审计入口
- `isc-iscb-util.jar`：真实 Script 运行时基线

这样做是为了把 4 类风险拆开控制：

- 会不会胡编函数
- 会不会误用平台上下文
- 文档示例是否可信
- 真实 runtime 能否通过编译或运行

## 3. 目录结构

```text
iscb-script/
├── agents/
│   └── openai.yaml
├── cases/
│   ├── engine/
│   ├── platform/
│   └── manifest.json
├── QUICKSTART.md
├── README.md
├── SKILL.md
├── isc-iscb-util.jar
├── references/
│   ├── context-routing.md
│   ├── conventions.md
│   ├── functions-engine.md
│   ├── functions-platform.md
│   ├── functions-platform-services.md
│   ├── patterns.md
│   ├── resources.md
│   └── syntax-complete.md
└── tools/
    ├── engine_api_manifest.json
    ├── iscb_skill_validator.py
    ├── script_runtime_real.py
    └── script_runtime_main/
        └── ScriptRuntimeMain.java
```

## 4. 文档职责划分

本次改造后，文档分层明确如下：

- `SKILL.md`：只保留主规则、上下文路由、输出契约、反幻觉边界、按需加载地图
- `references/context-routing.md`：集中定义上下文判定、平台降级策略、校验与保存契约
- `references/functions-*.md`：函数权威说明
- `references/patterns.md`：常见业务脚本模式
- `references/conventions.md`：常见约定与陷阱
- `QUICKSTART.md`：面向用户的请求模板和使用说明
- `README.md`：面向维护者的架构、目录和回归入口

规范性信息只保留一个权威来源，其他文档只引用，不重复改写。

## 5. Curated Cases

`cases/manifest.json` 是维护侧显式维护的回归清单。每个 case 至少包含：

- `id`
- `intent`
- `context`
- `script_path`
- `validation_mode`
- `notes`

当前支持的 `validation_mode`：

- `engine_compile`
- `engine_run`
- `reference_only`

这些 case 用来覆盖最常见的 3 类风险：

- 普通引擎脚本是否还能稳定生成和编译
- 真实运行 case 是否还能返回预期结果
- 平台上下文缺资源时，是否仍被正确归类为 reference-only

## 6. 验证命令

### 单项命令

```bash
python3 tools/iscb_skill_validator.py audit-skill
python3 tools/iscb_skill_validator.py audit-examples
python3 tools/iscb_skill_validator.py audit-curated-cases
python3 tools/iscb_skill_validator.py runtime-selftest
```

### 聚合命令

```bash
python3 tools/iscb_skill_validator.py audit-bundle
```

`audit-bundle` 会串联：

- `audit-skill`
- `audit-examples`
- `runtime-selftest`
- curated case 审计

## 7. 维护原则

- 主 `SKILL.md` 保持轻量，不再内嵌完整函数索引和大段语法速查。
- 详细知识放进 `references/`，由主 skill 按需加载。
- 默认产品边界不变：不自动运行、不自动保存、不虚构平台上下文。
- 平台层能力依赖真实资源时，只能输出参考脚本，不可声称“已本地验证可运行”。
- 修改主规则、reference、validator 或 curated cases 后，优先跑 `audit-bundle`。
