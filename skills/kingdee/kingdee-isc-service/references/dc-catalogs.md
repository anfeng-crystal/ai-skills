# dc_err / dc_stage 诊断目录

两套互补体系:`dc_err` 按错误类型深挖堆栈;`dc_stage` 按执行阶段定位。诊断顺序:先按阶段(取数/转换/写数)定位 → 再深挖错误类型。

## dc_stage(按执行阶段)
| 条目 | 覆盖阶段 | 职责 |
|---|---|---|
| general | 全阶段通用 | 超时、连接拒绝等基础设施问题 |
| read | 取数 | 数据源连接、查询失败 |
| transform | 转换 | 值转换、字段映射、类型转换 |
| write | 写数 | 业务写入、校验失败、权限不足 |

## dc_err(按错误类型)
| 条目 | 职责 |
|---|---|
| auth | EAS 鉴权异常(SHA-256/MD5 算法切换) |
| biz_action_write | `DoBizAction`/`ExecutionData` 业务写入失败 |
| connection | 连接拒绝、超时、DNS 解析失败 |
| connection_unsupported_op | API 连接器不支持特定 SQL 操作 |
| data_copy_mapping | 数据复制时字段映射失败 |
| database_adapt | Oracle/PG 类型适配(如 ORA-00904) |
| eas_integration | EAS 集成特定问题(联系人/银行重复) |
| event_trigger | 事件触发链路问题 |
| external_api_biz_error | 外部 API 业务错误码 |
| field_mapping | 候选键、基础资料、日期格式不匹配 |
| import_package | 资源包导入 JSON 解析/格式错误 |
| k3cloud_read / k3cloud_response / k3cloud_write | 星空读取/返回报文/写入异常 |
| network_auth | 网络认证、代理、SSL |
| timeout | 超时与熔断 |
| value_conversion | 值转换规则执行失败 |

## 典型大类速查
值转换 / 事件触发 / 执行启动 / 字段映射 / 数据库 / EAS 集成 / 连接网络 / OpenAPI / 高级场景(大数据量·附件·高并发·OOM) / 监控统计。每类的关键词见 `error-routing.md`。
