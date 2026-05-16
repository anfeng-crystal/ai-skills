# Kingdee Cosmic - 金蝶云苍穹开发 Skill

金蝶云苍穹 Java 二开、插件开发、元数据查询、代码质量核查的完整解决方案。

**核心原则**：封装优先，原生兜底。优先使用 `kd.cd.common.plugin` 扩展基类和项目封装工具类，避免退回到 BOS 原生低层 API。

---

## 功能概览

### 1. 插件开发

支持所有苍穹插件类型的开发：

- **表单插件**：字段联动、控件交互、UI 逻辑
- **单据插件**：审核提交按钮、单据 UI 控制
- **列表插件**：多选操作、批量处理
- **操作插件**：审核、保存、状态流转、校验、回滚
- **转换插件**：下推、选单、来源追踪、BOTP 转换
- **反写插件**：BOTP 回写阶段
- **报表插件**：报表 UI、数据分析
- **报表取数插件**：动态列、自定义数据源
- **打印插件**：套打、打印逻辑
- **OpenAPI 控制器**：外部集成
- **后台任务**：定时任务、调度作业
- **工作流插件**：审批流
- **导入插件**：批量导入

### 2. 元数据查询

#### 表单元数据查询
```bash
# 查询单据字段
python scripts/cosmic-form-metadata.py --config ok-cosmic.json get sal_order

# 批量查询多个单据（逗号分隔，并发请求）
python scripts/cosmic-form-metadata.py --config ok-cosmic.json get sal_order,ap_finapbill

# 混合查询：formId + 中文单据名（自动识别）
python scripts/cosmic-form-metadata.py --config ok-cosmic.json get "ap_finapbill,物料,bd_supplier"

# 模糊筛选字段
python scripts/cosmic-form-metadata.py --config ok-cosmic.json get sal_order --fuzzy qty price amount

# 按字段类型筛选
python scripts/cosmic-form-metadata.py --config ok-cosmic.json get sal_order --type BaseData

# 按多种类型筛选（正则 OR）
python scripts/cosmic-form-metadata.py --config ok-cosmic.json get sal_order --type "combo|check"

# 类型 + 关键词交集筛选
python scripts/cosmic-form-metadata.py --config ok-cosmic.json get sal_order --type decimal --fuzzy amount

# 查看单据所有操作按钮
python scripts/cosmic-form-metadata.py --config ok-cosmic.json get sal_order --op

# 按关键词筛选操作
python scripts/cosmic-form-metadata.py --config ok-cosmic.json get sal_order --op 审核 提交
```

#### 基础资料查询
```bash
# 查询基础资料
python scripts/cosmic-basedata-query.py --config ok-cosmic.json get --entity-id bd_material --number-or-name 01.0001
```

### 3. SDK API 查询

```bash
# 搜索类名
python scripts/cosmic-api-knowledge.py --config ok-cosmic.json search QueryServiceHelper

# 搜索方法名
python scripts/cosmic-api-knowledge.py --config ok-cosmic.json search-method loadSingle

# 查看类详情（全部方法）
python scripts/cosmic-api-knowledge.py --config ok-cosmic.json detail kd.bos.servicehelper.QueryServiceHelper

# 查看类详情（单个方法筛选）
python scripts/cosmic-api-knowledge.py --config ok-cosmic.json detail kd.bos.servicehelper.QueryServiceHelper --method loadSingle --compact

# 批量查类详情（逗号分隔，并发请求）
python scripts/cosmic-api-knowledge.py --config ok-cosmic.json detail kd.bos.servicehelper.QueryServiceHelper,kd.bos.servicehelper.SaveServiceHelper --method save --compact
```

### 4. 代码质量核查

#### 快速单文件校验
```bash
# 单文件或目录快速校验
export KINGDEE_COSMIC_SKILL_ROOT=/Users/anfeng/AI/skills/active/skills/kingdee/kingdee-cosmic
python3 "$KINGDEE_COSMIC_SKILL_ROOT/scripts/cosmic-post-check.py" ./src/main/java/MyPlugin.java --fix-hint
```

#### 全量项目扫描（200+ 条苍穹规则）
```bash
# 1. 扫描禁用类
python scripts/scan/scan_java_class.py <代码目录>

# 2. 扫描禁用方法
python scripts/scan/scan_java_method.py <代码目录>

# 3. 扫描静态集合变量
python scripts/scan/scan_java_static.py <代码目录>

# 4. 扫描循环内禁用方法
python scripts/scan/scan_java_loop_method.py <代码目录>

# 5. 扫描循环内禁用类
python scripts/scan/scan_java_loop_class.py <代码目录>

# 6. 扫描禁用关键字
python scripts/scan/scan_java_keyword.py <代码目录>

# 7. 合并扫描结果
python scripts/scan/merge_scan_results.py

# 8. 生成扫描报告（Markdown + Excel）
python scripts/scan/generate_scan_report.py
```

**扫描规则覆盖**：
- 禁用类（平台内部类、直接 DB 访问、元数据访问、JDK 多线程等）
- 禁用方法（直接删除数据、租户上下文篡改、DDL 操作等）
- 静态集合变量（内存泄漏风险）
- 循环内违规调用（DB 查询、ORM 操作、日志输出等）
- 禁用关键字（SQL 方言、字节码操作等）

**输出格式**：
- Markdown 报告：详细的审查结果文档
- Excel 报告：便于筛选和统计的表格数据（扫描概览、违规明细、规则统计）

### 5. 故障诊断

支持以下场景的故障诊断：
- 插件生命周期 NPE
- 事务回滚
- 挂载点冲突
- 权限问题
- 元数据问题
- 数据库查询问题

### 6. 配置检查

```bash
# 检查项目配置
python scripts/cosmic-config-check.py --config ok-cosmic.json
```

检查项：
- 数据库连接配置
- API 地址配置
- 在线服务可用性
- 知识库存在性

---

## 配置要求

需要在项目根目录创建 `ok-cosmic.json` 配置文件：

```json
{
  "meta": {
    "apiUrl": "http://localhost:8080/api/metadata",
    "timeoutSeconds": 30
  },
  "basedata": {
    "apiUrl": "http://localhost:8080/api/basedata",
    "timeoutSeconds": 30
  }
}
```

---

## 封装优先级

### 插件基类
- **扩展基类（优先）**：`AbstractBillPlugInExt`、`AbstractFormPluginExt`、`AbstractListPluginExt`、`AbstractOperationServicePlugInExt`、`AbstractValidatorExt`
- **原生基类（兜底）**：`AbstractConvertPlugIn`、`AbstractWriteBackPlugIn`（BOTP 转换和反写没有 Ext 版本）

### 工具类
- **错误汇总**：`OpUtils.addErrorMessage()`、`OpUtils.getCompleteFailMsg()`、`PushResult.failThenThrow()`
- **字符串判空**：`CharSequenceUtils`
- **集合判空**：`CollectionUtils`
- **日志记录**：`*Ext` 基类内置的 `public final Log log`，非插件类使用 `kd.bos.logging.LogFactory`

### 业务封装
- **单据状态流转**：`OpUtils`
- **连续操作**：`OperateChain`
- **单据转换**：`BotpUtils`
- **基础资料**：`BaseDataServiceHelper`
- **查询**：`QueryUtils` + `AlgoUtils`
- **基础资料查询**：`BusinessDataServiceHelper.loadFromCache()`
- **动态对象取值**：`DynamicObjectUtils`
- **附件处理**：`AttachmentUtils`

---

## 规则分层

### A 层：硬约束 / 交付红线
直接影响正确性、事件时机、插件上下文、事实准确性。新生成代码必须满足。

参考：`references/rules/constraints.md`、`references/rules/anti-patterns.md`、`references/rules/platform-baseline.md`

### B 层：推荐项 / 新代码默认写法
新代码默认尽量遵守。历史存量代码若暂未满足，不因此直接判为错误。

参考：`references/rules/coding-preferences.md`

### C 层：目标态治理 / 渐进优化
适合模板升级、专项治理、批量重构。默认不作为一次性交付阻断项。

参考：`references/rules/coding-preferences.md`、`references/rules/post-check.md`

---

## 目录结构

```
kingdee-cosmic/
├── scripts/
│   ├── scan/                          # 代码扫描脚本（200+ 条规则）
│   │   ├── scan_java_class.py        # 扫描禁用类
│   │   ├── scan_java_method.py       # 扫描禁用方法
│   │   ├── scan_java_static.py       # 扫描静态集合变量
│   │   ├── scan_java_loop_method.py  # 扫描循环内禁用方法
│   │   ├── scan_java_loop_class.py   # 扫描循环内禁用类
│   │   ├── scan_java_keyword.py      # 扫描禁用关键字
│   │   ├── merge_scan_results.py     # 合并扫描结果
│   │   └── generate_scan_report.py   # 生成扫描报告
│   ├── cosmic-form-metadata.py       # 表单元数据查询
│   ├── cosmic-basedata-query.py      # 基础资料查询
│   ├── cosmic-api-knowledge.py       # SDK API 查询
│   ├── cosmic-post-check.py          # 代码快速校验
│   └── cosmic-config-check.py        # 配置检查
├── references/
│   ├── rules/
│   │   ├── constraints.md            # 硬约束 / 交付红线
│   │   ├── coding-preferences.md     # 编码偏好
│   │   ├── decision-matrix.md        # 决策矩阵
│   │   ├── intent-routing.md         # 自然语言意图路由
│   │   ├── workflow.md               # 开发流程
│   │   ├── fact-confirmation.md      # 关键事实判定
│   │   ├── cheat-sheet.md            # 高频 API 速查
│   │   ├── post-check.md             # 生成后自动校验规则
│   │   ├── anti-patterns.md          # 禁忌清单
│   │   └── platform-baseline.md      # 平台总规范摘要
│   ├── quality/
│   │   ├── scan-rules/               # 扫描规则文件
│   │   │   ├── sonar_cve_class.md   # 禁用类规则
│   │   │   ├── sonar_cve_method.md  # 禁用方法规则
│   │   │   ├── sonar_cve_static.md  # 静态集合规则
│   │   │   ├── sonar_cve_loop_method.md  # 循环内禁用方法规则
│   │   │   ├── sonar_cve_loop_class.md   # 循环内禁用类规则
│   │   │   └── sonar_cve_keyword.md      # 禁用关键字规则
│   │   ├── cosmic-java-scan.md      # 扫描指南
│   │   └── ai-code-review-patterns.md  # 自检规则
│   ├── base/
│   │   └── plugin/                   # 插件开发参考文档
│   ├── adv/
│   │   ├── event-lifecycle.md        # 插件事件生命周期
│   │   ├── form-utils.md             # 界面工具
│   │   ├── basedata-query.md         # 基础资料查询
│   │   └── query-dataset.md          # 查询与 DataSet
│   ├── diagnostics/
│   │   └── issue-analysis.md         # 故障诊断
│   └── governance/
│       └── comment-policy.md         # 注释规范
└── assets/
    ├── *.java                         # 插件模板
    └── snippets/
        └── snippets-guide.md          # 场景化代码片段

```

---

## 使用场景

### 场景 1：开发表单插件
1. 查询表单元数据：`python scripts/cosmic-form-metadata.py --config ok-cosmic.json get sal_order`
2. 查询 SDK API：`python scripts/cosmic-api-knowledge.py --config ok-cosmic.json search QueryServiceHelper`
3. 生成插件代码（使用 `AbstractFormPluginExt` 基类）
4. 代码校验：`python3 "$KINGDEE_COSMIC_SKILL_ROOT/scripts/cosmic-post-check.py" MyPlugin.java --fix-hint`

### 场景 2：开发操作插件
1. 查询操作按钮：`python scripts/cosmic-form-metadata.py --config ok-cosmic.json get sal_order --op`
2. 查询 SDK API：`python scripts/cosmic-api-knowledge.py --config ok-cosmic.json detail kd.bos.servicehelper.operation.OperationServiceHelper`
3. 生成插件代码（使用 `AbstractOperationServicePlugInExt` 基类）
4. 代码校验：`python3 "$KINGDEE_COSMIC_SKILL_ROOT/scripts/cosmic-post-check.py" MyPlugin.java --fix-hint`

### 场景 3：全量代码扫描
1. 执行 6 个扫描脚本
2. 合并扫描结果：`python scripts/scan/merge_scan_results.py`
3. 生成报告：`python scripts/scan/generate_scan_report.py`
4. 查看 `result/scan_result.md` 和 `result/scan_result.xlsx`

### 场景 4：故障诊断
1. 收集错误栈、模块、挂载点、复现步骤
2. 按生命周期定位（表单/操作/报表/工作流）
3. 按错误类型分类（NPE/事务/权限/元数据）
4. 引用 `references/issue-analysis/examples.md` 中的类似案例

---

## 协作 Skills

- **kingdee-metadata-analyzer**：元数据全景分析、插件绑定分析、上下游关系
- **kingdee-sdk-helper**：SDK API 详细查询（完整签名 + Javadoc）
- **kingdee-kingscript**：KingScript 脚本开发
- **kingdee-iscb-script**：集成云脚本开发

---

## 依赖

- Python 3.8+
- Java 8+
- Gradle Wrapper
- psycopg2-binary（元数据查询）
- javalang（代码扫描）
- openpyxl（Excel 报告生成）
