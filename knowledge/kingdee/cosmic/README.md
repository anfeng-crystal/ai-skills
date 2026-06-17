# 金蝶云苍穹知识库

> 知识库根目录: `/Users/anfeng/AI/knowledge/kingdee/cosmic`
> 上级入库规范: `/Users/anfeng/AI/knowledge/入库规范.md`
> 专项文档规范: `文档规范.md`

---

## 定位
- 保存金蝶云苍穹开发中长期稳定、可复用、可检索的知识。
- 技术结论以官方资料、本地依赖、项目源码和已验证案例为依据。
- 工单、交付物、执行记录、验证日志和任务流水归入 `/Users/anfeng/AI/archive`。
- MCP 服务、依赖、运行日志和服务配置归入 `/Users/anfeng/AI/mcp`。

## 文档统计

截至 2026-04-16，当前目录共 **101** 篇 Markdown 文档。

| 一级目录 | 文档数 | 说明 |
|---|---:|---|
| `开发指南/` | 21 | 插件、报表、元数据、界面、服务开发指南 |
| `API参考/` | 8 | KORM、服务助手、DataSet、KingScript 和常用工具类 |
| `行业/` | 41 | 教育、医疗、建筑、金融、政务等行业场景 |
| `领域/` | 10 | 后端、前端、集成与运维、通用规范等索引 |
| `官方文档/` | 5 | 官方入口和版本检索页 |
| `迭代记录/` | 5 | 历史迭代资料，默认不作为技术主依据 |
| `projects/` | 1 | 项目配置表和项目级知识库入口 |
| `tools/` | 1 | 知识库检索、采集和构建工具说明 |
| 其他目录 | 9 | 常见问题、最佳实践、示例代码、社区资源和根规范 |

## 重点入口

### 开发指南
| 文档 | 说明 |
|---|---|
| [插件开发综合指南](开发指南/插件开发/插件开发综合指南.md) | 插件类型、事件入口和基础开发模式 |
| [插件事件执行顺序详解](开发指南/插件开发/插件事件执行顺序详解.md) | 插件事件时机和执行顺序 |
| [表单插件常用事件与方法](开发指南/插件开发/表单插件常用事件与方法.md) | 表单插件事件和常用方法 |
| [列表插件事件与接口](开发指南/插件开发/列表插件事件与接口.md) | 列表插件事件和接口 |
| [操作插件-AbstractOperationServicePlugIn](开发指南/插件开发/操作插件-AbstractOperationServicePlugIn.md) | 操作插件事务和事件边界 |
| [报表插件开发指南](开发指南/插件开发/报表插件开发指南.md) | 报表插件取数和分页规则 |
| [单据转换插件-AbstractConvertPlugIn](开发指南/插件开发/单据转换插件-AbstractConvertPlugIn.md) | 单据转换插件使用边界 |
| [KingScript-KDE高级脚本开发指南](开发指南/插件开发/KingScript-KDE高级脚本开发指南.md) | KingScript 写法和事件入口 |
| [元数据规则-界面规则与业务规则能力边界](开发指南/元数据设计/元数据规则-界面规则与业务规则能力边界.md) | 配置优先与插件兜底边界 |
| [WebAPI开发指南](开发指南/服务开发/WebAPI开发指南.md) | WebAPI 插件开发 |

### API 参考
| 文档 | 说明 |
|---|---|
| [DynamicObject详解](API参考/KORM/DynamicObject详解.md) | DynamicObject 使用方式 |
| [DynamicObject与BusinessDataServiceHelper指南](API参考/KORM/DynamicObject与BusinessDataServiceHelper指南.md) | 数据访问和 ORM 模式 |
| [QFilter查询详解](API参考/KORM/QFilter查询详解.md) | QFilter 查询条件写法 |
| [事务管理指南](API参考/KORM/事务管理指南.md) | KORM 事务管理 |
| [OperationServiceHelper-executeOperate参数说明](API参考/服务助手/OperationServiceHelper-executeOperate参数说明.md) | 操作服务助手方法、重载和参数 |
| [DataSet-全量API参考](API参考/常用工具类/DataSet-全量API参考.md) | DataSet API 参考 |
| [KingScript-KDE脚本API与事件参考](API参考/常用工具类/KingScript-KDE脚本API与事件参考.md) | KingScript API 与事件 |
| [API参考汇总](API参考/API参考汇总.md) | API 分类索引 |

### 其他入口
- [常见问题索引](常见问题/索引.md)
- [最佳实践](最佳实践/开发规范/最佳实践.md)
- [搜索索引](社区资源/搜索索引/search_index.md)
- [行业索引](行业/README.md)
- [领域索引](领域/README.md)

## 入库规范
- 所有文档遵守 [全局入库规范](/Users/anfeng/AI/knowledge/入库规范.md)。
- 金蝶专项文档遵守 [文档规范](文档规范.md)。
- 新增、移动、清洗、删除或重命名文档后，必须同步更新相关索引。
- API 文档同步更新 [API参考汇总](API参考/API参考汇总.md)。
- 检索关键词同步更新 [搜索索引](社区资源/搜索索引/search_index.md)。
- 行业或领域文档同步更新对应目录索引。

## 配套工具
- MCP 目录: `/Users/anfeng/AI/mcp/active/kingdee-knowledge`
- 本地搜索脚本: `tools/kingdee_search.py`
- 资料采集脚本: `tools/fetch_articles.py`、`tools/fetch_official.py`
- ok-cosmic 知识库构建工具: `tools/ok-cosmic-knowledge-builder/工具说明.md`
- ok-cosmic 离线库: `projects/ztjg/ok-cosmic-knowledge.db`

Claude MCP 配置入口：

```json
{
  "kingdee-knowledge": {
    "command": "node",
    "args": ["/Users/anfeng/AI/mcp/active/kingdee-knowledge/mcp-server.js"]
  }
}
```

## 相关链接
- [金蝶云苍穹开发者门户](https://dev.kingdee.com)
- [金蝶云社区](https://vip.kingdee.com)
- [金蝶云星空开放平台](https://open.kingdee.com)
