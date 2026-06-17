# ISC 错误诊断路由表

按报错关键词或特征匹配错误大类,再进入对应文档。深挖堆栈见 `dc-catalogs.md`。

| 报错关键词 | 错误分类 | 覆盖问题 |
|---|---|---|
| `ValueConversionRule`、值转换、SQL 类型转换、常量值转换、汇率同步、用户-人员转换失败、`FUserID`、`FLinkObject` | 值转换异常 | 数据类型不匹配、转换规则失败、ID 查不到 |
| 事件触发不生效、触发卡住、`createStatus`、人工正常但事件报错 | 事件触发异常 | 事件监听无反应、事件执行失败 |
| 无执行日志、超时/熔断、权限不足、`您没有业务对象`、启动方案报错、`batch_action` 找不到 | 执行日志与启动 | 日志查不到、方案启动失败 |
| 基础资料不存在、分录长度不一致、候选键、日期格式、`null value in column` | 字段映射与数据 | 字段映射失败、数据校验错误 |
| Oracle ORA 错误、PG 适配、视图 SQL、服务流程脚本节点报错、Schema、父子流程中断 | 数据库与服务流程 | 数据库适配、SQL 执行失败 |
| `MissingRecord`、EAS 联系人/银行重复、DEP 扩展、`CallService.invokeMethod`、人员禁用同步 | EAS 集成异常 | EAS 对接数据同步异常 |
| 许可不足、资源授权、SSL 握手、代理用户校验、用户禁用、`access_token`、MQ 消息丢失、`Connection reset`、DNS 解析、白名单 | 连接与网络 | 网络连接失败、鉴权问题 |
| OpenAPI 乱码、JsonArray、自定义返回参数、固定密钥、`openApiSign`、弹性域集成、`404 IscServiceDispatcher` | OpenAPI/API | OpenAPI 调用异常、接口不存在 |
| 大数据量同步慢、附件集成、中间表方案、高并发重复、熔断规则、报文超限、OOM、`isc_max_response_content_length`、webhook、CPU 占满 | 高级场景 | 性能优化、大数据同步 |
| 执行日志查看、任务监控、耗时统计、事件消息监控、业务调用追溯 | 监控与统计 | 日志追踪、性能监控 |

使用:先按关键词匹配 → 进入对应分类文档 → 可先按执行阶段(取数/转换/写数)定位,再深挖错误类型。
