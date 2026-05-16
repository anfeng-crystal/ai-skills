# ISCB 资料导航

## 先读入口
- 普通生成、修改或解释：`references/patterns.md`、`references/conventions.md`
- 上下文不确定：`references/context-routing.md`
- 函数用法：先按函数归属读取 `references/functions-engine.md` 或 `references/functions-platform.md`
- 平台资源、连接别名或流程上下文：`references/resources.md`
- 语法、操作符、嵌入式 SQL 或 XPath：`references/syntax-complete.md`

## 上下文
| 场景 | 参考 | 预置变量边界 |
|---|---|---|
| 普通引擎脚本 | `patterns.md`、`conventions.md` | 无默认预置变量 |
| 数据集成方案 | `context-routing.md`、`resources.md` | 仅在用户明确时使用 `src`、`tar`、`$src`、`$tar` |
| 值转换规则 | `context-routing.md`、`conventions.md` | 仅在用户明确时使用 `param`、`$this` |
| 服务流程脚本节点 | `context-routing.md`、`resources.md` | 仅在用户明确时使用 `$process` |
| 自定义 API / WebAPI | `context-routing.md`、`functions-platform-services.md` | 参数和请求对象结构必须来自用户输入或平台定义 |

## 工具
- 静态检查：`python3 scripts/iscb_skill_validator.py check-script <file>`
- 引擎编译校验：`python3 scripts/iscb_skill_validator.py check-script --runtime <file>`
- 运行验证：`python3 scripts/iscb_skill_validator.py run-script <file>`
- Bundle 回归：`python3 scripts/iscb_skill_validator.py audit-bundle`
