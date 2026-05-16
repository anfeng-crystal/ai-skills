# Kingscript Plugin Templates

## 模板选择

| 模板 | 适用场景 | 推荐继续看的示例 |
|---|---|---|
| `form-plugin-template.md` | 表单页面、看板、普通页面交互 | `../examples/plugins/插件示例/表单插件-事件拆分/index.md` |
| `bill-plugin-template.md` | 单据表单、字段联动、F7、关闭回调 | `../examples/plugins/插件示例/表单插件.md` |
| `list-plugin-template.md` | 列表初始化、选择联动、列表回调 | `../examples/plugins/插件示例/列表插件-事件拆分/index.md` |
| `operation-plugin-template.md` | 服务端操作校验、准备属性、校验器 | `../examples/plugins/插件示例/操作插件.md` |
| `print-plugin-template.md` | 打印前后处理、打印数据补充 | `../examples/plugins/插件示例/打印插件.md` |
| `report-form-plugin-template.md` | 报表表单交互 | `../examples/plugins/插件示例/报表表单插件.md` |
| `report-query-plugin-template.md` | 报表查询扩展 | `../examples/plugins/插件示例/报表查询插件.md` |
| `workflow-plugin-template.md` | 工作流扩展 | `../examples/plugins/插件示例/工作流插件.md` |
| `task-plugin-template.md` | 后台任务、调度任务 | `../examples/plugins/插件示例/后台任务.md` |
| `mobile-form-plugin-template.md` | 移动表单、移动控件联动 | `../examples/plugins/插件示例/移动表单.md` |
| `import-plugin-template.md` | 引入插件 | `../examples/plugins/插件示例/引入插件.md` |
| `export-plugin-template.md` | 引出插件 | `../examples/plugins/插件示例/引出插件.md` |
| `convert-plugin-template.md` | 转换插件 | `../examples/plugins/插件示例/转换插件.md` |

## 使用规则
1. 先按插件类型选择最接近的模板。
2. 只保留当前需求真的会用到的生命周期方法。
3. 需要写法时看 `../examples/`；需要事件时机、对象类型和 API 边界时看 `../sdk/`。

## 常用 import
- 表单插件：`@cosmic/bos-core/kd/bos/form/plugin`
- 单据插件：`@cosmic/bos-core/kd/bos/bill`
- 列表插件：`@cosmic/bos-core/kd/bos/list/plugin`
- 操作插件：`@cosmic/bos-core/kd/bos/entity/plugin`
- 打印插件：`@cosmic/bos-core/kd/bos/print/core/plugin`
- 后台任务：`@cosmic/bos-core/kd/bos/schedule`
