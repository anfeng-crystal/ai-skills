# 插件类型 → 基类 → 注册位置速查

选型与挂载入口速查;基类、事件签名、字段标识仍以 `rules/cheat-sheet.md`、`references/event-lifecycle.md`、元数据与 `kingdee-sdk-helper` 为准,不凭本表写最终签名。

| 需求场景 | 插件类型 | 基类 | 注册位置 |
|---|---|---|---|
| 单据界面加载/展示/字段控制/按钮 | 单据界面 | `AbstractBillPlugIn` | 单据 → 表单主实体 → 插件 |
| 动态表单界面交互 | 动态表单 | `AbstractFormPlugin` | 动态表单 → 表单主实体 → 插件 |
| 列表过滤/列控制/行点击/批量 | 列表 | `AbstractListPlugin` | 列表 → 表单根节点 → 列表插件 |
| 保存/提交/审核前后干预 | 操作服务 | `AbstractOperationServicePlugIn` | 单据 → 操作 → 修改/新增 → 其他控制 → 服务插件 |
| 报表查询取数/列计算 | 报表取数 | `AbstractReportListDataPlugin` | 报表 → 报表列表 → 查询插件 |
| 报表界面过滤/展示控制 | 报表界面 | `AbstractReportFormPlugin` | 报表 → 表单根节点 → 插件 |
| 下推转换时干预目标单 | 单据转换 | `AbstractConvertPlugIn` | 业务流开发 → 转换路线 → 插件 |
| 反写规则执行时干预 | 单据反写 | `AbstractWriteBackPlugIn` | 单据 → 关联配置 → 反写插件 |
| 基础资料界面交互 | 基础资料界面 | `AbstractBasePlugIn` | 基础资料 → 表单主实体 → 插件 |

> 报表插件(取数/界面)的实现细节与 Algo 精确签名以 `kingdee-report` skill 为权威入口,本表只用于选型与挂载定位。

## 需求信息采集清单

通用必填:实体编码/单据标识、涉及字段标识(含分录 `entryentity.xxx`)、平台版本(影响 API 兼容)。

按类型补充:
- 表单/单据:待控制控件标识、触发时机、涉及事件。
- 列表:绑定单据标识、自定义列、过滤字段与默认条件。
- 操作:操作编码(save/submit/audit)、校验或回写逻辑。
- 报表:数据源、计算字段、过滤与分组(实现交 `kingdee-report`)。
- 转换:源单/目标单标识、转换路线标识。
- 反写:源单/下游单标识、反写规则编码。
