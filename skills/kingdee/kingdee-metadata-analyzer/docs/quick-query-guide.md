# 快速查询工具使用指南

## 概述

`quick-query.py` 是一个轻量级的元数据快速查询工具，适合开发时快速查字段、操作、枚举，不需要等待全景分析。

## 功能特性

- ✅ 查询字段列表（支持继承链）
- ✅ 查询操作列表
- ✅ 查询已绑定插件
- ✅ 同时查询实体操作插件和关联表单页面插件
- ✅ 查询枚举字段
- ✅ 模糊搜索实体
- ✅ 按模块列出实体
- ✅ 本地缓存机制
- ✅ 表格输出优化

## 与全景分析的对比

| 维度 | 快速查询 (quick-query.py) | 全景分析 (cosmic-metadata-analyzer.py) |
|------|---------------------------|----------------------------------------|
| **定位** | 快速查询工具 | 全景分析工具 |
| **数据来源** | 仅数据库 | 数据库 + JAR 反编译 + 源码分析 |
| **查询速度** | 秒级 | 分钟级 |
| **输出格式** | 简洁表格/文本 | 结构化产物（inventory.json + sources/*） |
| **本地缓存** | 支持（`.metadata_cache/`） | 支持（`inventory.json`） |
| **继承链** | 支持（`--inherit`） | 支持 |
| **按模块列出** | 支持（`--list --module`） | 不支持 |
| **适用场景** | 开发时快速查字段、操作、枚举和插件清单 | 插件绑定分析、源码证据、上下游关系、复用建议 |

## 环境引导

优先通过 `bootstrap-python-env.py` 主动创建/复用本地 venv 并安装依赖，不把缺少 `psycopg2` 直接抛给用户。macOS/Linux 使用：

```bash
METADATA_SKILL_ROOT=<当前 kingdee-metadata-analyzer skill 根目录>
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" --search "项目信息" --config ok-cosmic.dev.json
```

Windows PowerShell 使用：

```powershell
$env:METADATA_SKILL_ROOT = "<当前 kingdee-metadata-analyzer skill 根目录>"
py -3 "$env:METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$env:METADATA_SKILL_ROOT/scripts/quick-query.py" --search "项目信息" --config ok-cosmic.dev.json
```

下方示例中的 `scripts/` 均指 `METADATA_SKILL_ROOT/scripts/`，不是业务项目仓库的 `scripts/`。在项目根目录执行时必须使用上面的绝对 skill root 写法。

如需指定安装源，可设置 `KINGDEE_METADATA_ANALYZER_PIP_INDEX_URLS`，多个源用逗号或分号分隔。未配置时会先尝试默认源，再尝试内置镜像。

## 配置要求

优先使用当前项目根目录的显式配置。`ztjg` 项目默认查 dev 使用 `ok-cosmic.dev.json`；用户明确要求生产时使用 `ok-cosmic.prod.json`。只有当前项目没有可用配置时，才回退项目配置表或泛化 `ok-cosmic.json`。

配置文件需要包含 `metadataAnalyzer` 节点：

```json
{
  "metadataAnalyzer": {
    "enabled": true,
    "database": {
      "host": "localhost",
      "port": 5432,
      "dbname": "cosmic_metadata",
      "user": "postgres",
      "passwordEnv": "COSMIC_DB_PASSWORD"
    }
  }
}
```

数据库密码解析顺序：
1. 环境变量（`passwordEnv` 指定的变量名）
2. `.env` 文件（`ok-cosmic.json` 同目录或项目根目录）
3. JSON 兼容字段（`database.password`，不推荐）

## 本地缓存

查询结果自动缓存到 `.metadata_cache/` 目录，加速重复查询。

**缓存文件结构**：
```
.metadata_cache/
├── sal_order.json
├── bd_customer.json
└── pur_order.json
```

**自定义缓存目录**：
```bash
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" sal_order --config ok-cosmic.dev.json --fields --cache-dir /path/to/cache
```

**清理缓存**：
```bash
# 预览将清理的缓存
python3 "$METADATA_SKILL_ROOT/scripts/cache_manager.py" clean

# 确认后清理所有缓存
python3 "$METADATA_SKILL_ROOT/scripts/cache_manager.py" clean --apply
```

## 使用方法

### 1. 查询字段列表

```bash
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" sal_order --config ok-cosmic.dev.json --fields
```

**输出示例**：
```
实体 sal_order(销售订单) 共 45 个字段：

  序号  fieldKey    中文名    类型              基础资料  备注
  1     billno      单据编号  TextField
  2     billstatus  单据状态  ComboField
  3     customer    客户      BasedataField    是        [关联:bd_customer]
  4     amount      金额      DecimalField
  ...
```

**含继承字段**：
```bash
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" sal_order --config ok-cosmic.dev.json --fields --inherit
```

**输出示例**：
```
实体 sal_order(销售订单) 共 68 个字段：

  序号  fieldKey    中文名    类型          基础资料  备注
  1     billno      单据编号  TextField
  ...
  45    id          主键      PKField                     [继承自:bos_bill]
  46    creator     创建人    CreatorField                [继承自:bos_bill]
  ...
```

---

### 2. 查询操作列表

```bash
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" sal_order --config ok-cosmic.dev.json --ops
```

**输出示例**：
```
实体 sal_order(销售订单) 共 8 个操作：

  序号  opKey           名称  操作类型  插件数
  1     save(暂存)      暂存  edit      2
  2     submit(提交)    提交  edit      3
  3     audit(审核)     审核  edit      1
  4     push_down       下推  custom    0
  ...
```

---

### 3. 查询已绑定插件

```bash
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" sal_order --config ok-cosmic.dev.json --plugins
```

**输出示例**：
```
实体 sal_order(销售订单) 共 6 个插件：

  序号  类型      挂载点              表单页面                类名                                    状态  说明
  1     操作插件  save(暂存)                                  com.example.SalOrderSavePlugin         启用  保存前校验
  2     操作插件  submit(提交)                                com.example.SalOrderSubmitPlugin       启用  提交后推送
  3     页面插件  单据编辑页面(edit)  sal_order(销售订单)     com.example.SalOrderFormPlugin
  ...
```

插件快查会合并实体设计中的操作插件和关联表单设计中的页面插件；页面插件类名会同时兼容 `ClassName` 和 `oid`。如果需要源码、JAR 反查或判断 PC/移动页面真实执行链路，继续使用全景分析。

如果操作 XML 只有 `action=edit` 且没有 `Key/Name/OperationKey`，快查只输出 `edit#N[oid]` 这类无语义标签，不推断为暂存、提交、审核或反审核；真实业务语义需要结合插件描述、源码或操作设计元数据确认。

---

### 4. 查询枚举字段

```bash
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" sal_order --config ok-cosmic.dev.json --enums
```

**输出示例**：
```
实体 sal_order(销售订单) 共 3 个枚举字段：

  billstatus: 单据状态 [ComboField]
    - A: 暂存
    - B: 已提交
    - C: 已审核

  ordertype: 订单类型 [ComboField]
    - 1: 标准订单
    - 2: 紧急订单

  ...
```

---

### 5. 查询所有信息（概览）

```bash
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" sal_order --config ok-cosmic.dev.json --all
# 或简写（默认查询所有）
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" sal_order --config ok-cosmic.dev.json
```

**输出示例**：
```
实体 sal_order(销售订单)

=== 字段 (45) ===
  billno: 单据编号 [TextField]
  billstatus: 单据状态 [ComboField]
  customer: 客户 [BasedataField] -> bd_customer
  ... 还有 42 个字段

=== 操作 (8) ===
  save(暂存): 暂存 [edit] (插件数: 2)
  submit(提交): 提交 [edit] (插件数: 3)
  ...

=== 插件 (6) ===
  操作插件 @ save(暂存)
    com.example.SalOrderSavePlugin
  ... 还有 5 个插件

=== 枚举字段 (3) ===
  billstatus: 单据状态 [ComboField]
    - A: 暂存
    - B: 已提交
    - C: 已审核
  ...
```

---

### 6. 模糊搜索实体

```bash
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" --search "销售" --config ok-cosmic.dev.json
```

**输出示例**：
```
搜索 '销售' 找到 5 个实体：

  序号  entityNumber  实体名称
  1     sal_order     销售订单
  2     sal_outstock  销售出库单
  3     sal_invoice   销售发票
  4     sal_return    销售退货单
  5     sal_contract  销售合同
```

---

### 7. 按模块列出实体

```bash
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" --list --module sal --config ok-cosmic.dev.json
```

**输出示例**：
```
模块 'sal' 下共 15 个实体：

  序号  entityNumber      实体名称
  1     sal_order         销售订单
  2     sal_outstock      销售出库单
  3     sal_invoice       销售发票
  4     sal_return        销售退货单
  5     sal_contract      销售合同
  ...
```

---

## 使用场景

### 场景 1：开发表单插件时快速查字段

```bash
# 快速查看销售订单有哪些字段
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" sal_order --config ok-cosmic.dev.json --fields

# 找到需要的字段后，直接在代码中使用
this.getModel().getValue("customer");
```

---

### 场景 2：查看操作插件挂载点

```bash
# 查看销售订单有哪些操作
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" sal_order --config ok-cosmic.dev.json --ops

# 查看每个操作绑定了哪些插件
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" sal_order --config ok-cosmic.dev.json --plugins
```

---

### 场景 3：查询枚举值

```bash
# 查看单据状态的枚举值
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" sal_order --config ok-cosmic.dev.json --enums

# 在代码中使用正确的枚举值
if ("C".equals(billStatus)) {
    // 已审核
}
```

---

### 场景 4：搜索实体标识

```bash
# 不确定实体标识时，先搜索
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" --search "物料" --config ok-cosmic.dev.json

# 找到 bd_material 后，再查询详细信息
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" bd_material --config ok-cosmic.dev.json --fields
```

---

### 场景 5：按模块浏览实体

```bash
# 查看采购模块下的所有实体
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" --list --module pur --config ok-cosmic.dev.json

# 查看销售模块下的所有实体
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" --list --module sal --config ok-cosmic.dev.json
```

---

### 场景 6：查询继承字段

```bash
# 查看销售订单的所有字段（含继承自父实体的字段）
python3 "$METADATA_SKILL_ROOT/scripts/bootstrap-python-env.py" -- "$METADATA_SKILL_ROOT/scripts/quick-query.py" sal_order --config ok-cosmic.dev.json --fields --inherit

# 找到继承自 bos_bill 的字段
# 输出会标注 [继承自:bos_bill]
```

---

## 故障排查

### 1. 数据库连接失败

**错误信息**：
```
[ERROR] 数据库连接失败: could not connect to server
```

**解决方法**：
1. 检查 `ok-cosmic.json` 中的数据库配置（host/port/dbname/user）
2. 检查数据库密码是否正确（环境变量或 .env 文件）
3. 检查数据库服务是否启动
4. 检查网络连接

---

### 2. 未找到实体

**错误信息**：
```
[ERROR] 未找到实体: sal_order
```

**解决方法**：
1. 使用 `--search` 搜索实体标识
2. 检查实体标识是否正确（区分大小写）
3. 检查数据库中是否存在该实体

---

### 3. metadataAnalyzer.enabled 为 false

**错误信息**：
```
[ERROR] metadataAnalyzer.enabled 为 false，禁止连接数据库
```

**解决方法**：
在 `ok-cosmic.json` 中设置 `metadataAnalyzer.enabled: true`

---

## 最佳实践

1. **快速查询优先**：开发时优先使用 `quick-query.py`，速度快
2. **全景分析兜底**：需要深度分析时再使用 `cosmic-metadata-analyzer.py`
3. **搜索后查询**：不确定实体标识时，先用 `--search` 搜索
4. **按需查询**：只查询需要的信息（`--fields`、`--ops` 等），不要每次都用 `--all`
5. **配置复用**：使用统一的 `ok-cosmic.json` 配置，与全景分析工具保持一致
6. **利用缓存**：重复查询会自动使用缓存，加速查询
7. **继承链查询**：查看完整字段列表时使用 `--inherit`
8. **模块浏览**：不确定模块下有哪些实体时，使用 `--list --module`

---

## 性能优化

### 查询优化建议
1. **精确查询**：使用完整的实体标识，避免模糊搜索
2. **按需查询**：只查询需要的信息，不要每次都用 `--all`
3. **批量查询**：需要查询多个实体时，使用 `--list --module` 先列出所有实体
4. **继承链**：只在需要完整字段列表时使用 `--inherit`
