# 页面挂载证据

## 目标

判断插件、字段和操作到底挂在哪个苍穹页面入口上，尤其区分 PC 表单、移动表单、移动列表、派生页面和操作插件。

## 页面类型

| 入口 | 常见标识 | 判断要点 |
|---|---|---|
| PC 单据/基础资料 | `BillForm`, `BasedataForm`, `ListForm` | 结合 `formId`、`formPage`、`pageElement` 和设计器页面名称确认。 |
| 移动单据 | `MobileBillFormAp` | 只代表移动编辑/查看入口，不等同于移动列表。 |
| 移动列表 | `MobileListFormAp` | 列表打开、过滤、按钮操作和移动详情入口要分开判断。 |
| 卡片/分录派生页 | `CardEntryViewAp` 等 | 必须标注父页面和分录控件，不能只按类名归并。 |
| 操作插件 | `Operation` / `Plugins` | 绑定在操作上时，以操作编码和操作名称作为入口证据。 |

## 证据要求

- 插件挂载结论至少包含 `className`、`pageElement`、`formPage`、`source` 四项。
- 同一个插件类可同时挂在 PC、移动表单、移动列表或操作上；类名相同不代表执行入口相同。
- 移动端问题必须明确用户说的是移动编辑页、移动查看页、移动列表页还是移动按钮操作。
- 生产和 dev 对比时必须分别列出环境、配置文件和采集时间；不能用 dev 挂载替代生产事实。
- 如果只拿到实体级插件，不能断言移动页面挂载；需要继续查 `t_meta_formdesign.fdata` 或 analyzer `inventory.json`。

## 输出格式

```json
{
  "formId": "MobileBillFormAp",
  "pageType": "mobile-bill",
  "plugins": [
    {
      "className": "com.example.Plugin",
      "pageElement": "form|list|operation|entry",
      "formPage": "edit|view|list",
      "source": "metadata|source|jar"
    }
  ]
}
```

## 失败条件

- 只有源码类名，没有元数据挂载证据。
- 只有实体号，没有页面号或操作号。
- quick query 输出有截断、警告或缺少 `formPage` / `pageElement`。
- 生产和 dev 环境混用，且未明确标注边界。
