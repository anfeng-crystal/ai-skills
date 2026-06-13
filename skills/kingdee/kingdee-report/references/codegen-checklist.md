# 报表代码生成规范与验证清单

## 生成顺序
1. 包声明 + 标准 import 集(见 `algo-api.md`)。
2. `extends AbstractReportListDataPlugin`。
3. `private static final Log logger = LogFactory.getLog(...)`。
4. 常量区 `private static final`(分组编码数组等)。
5. `@Override query()`:解析 FilterInfo → 构建 `QFilter[]` → 各数据源方法 → JOIN/UNION → `groupBy().sum().finish()` → `addField()` → 返回。
6. 过滤解析方法(parseOrgId、parsePeriodId 等,按类型拆分)。
7. 数据源方法(每个实体一个 getXxxDs)。
8. 公式/逐行计算方法(如需)。
9. 辅助方法(getBigDecimalValue、emptyDs、addNullSafeFields)。

## 强制规范自检
| 规范 | 检查 | 修复 |
|---|---|---|
| 无实例字段 | 搜 `private` 非 static final | 改局部变量 + 参数传递 |
| BigDecimal | 搜 `double`/`float` 运算 | 改 BigDecimal 运算 |
| AlgoKey 唯一 | 每个 queryDataSet 调用 | `getClass().getName()+"_suffix"` |
| 空值安全 | `row.get(field)` 后 | 用 `getBigDecimalValue()` 兜 ZERO |
| NULL 比较 | 表达式中 `= null` | 改 `IS NULL` |
| 日志 | catch 块 | `logger.error("...", e)` |
| 只读 | 搜 `SaveServiceHelper`/`OperationServiceHelper` | 报表禁写库,移除 |

## 生成前完整性清单
- 报表标识(编码)、至少一个数据源实体编码 —— 必须。
- 过滤项字段 key + 编码值(非中文名)—— 必须。
- 所有输出列字段 key 映射 —— 必须。
- 计算列 BigDecimal 表达式 —— 必须(如有计算)。
- 关联路径(JOIN 字段映射)—— 有关联则必须。

## 生成后验证清单(交 kingdee-testing / kingdee-metadata-analyzer)
- 字段 key 与报表元数据一致(metadata-analyzer 复核)。
- 实体编码在目标环境可用。
- 过滤编码值在基础资料中存在。
- 编译无语法错误,模块级 Gradle 测试通过(kingdee-testing)。
- BigDecimal 精度正确;大数据量(10 万+ 行)性能可接受。
- 无实例字段导致的并发串数据。
