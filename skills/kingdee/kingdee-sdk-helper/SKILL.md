---
name: kingdee-sdk-helper
description: "Kingdee SDK/API lookup and evidence routing: class definitions, exact method signatures, Javadoc, API ownership, version/source verification, and community-snippet confirmation against project JARs or the local SDK index."
license: MIT
metadata:
  author: "anfeng"
  version: "1.1.0"
  tags: "kingdee, cosmic, SDK, API, Javadoc"
---

# Kingdee SDK Helper
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 触发边界
- 用户询问金蝶云苍穹 SDK 的类定义、方法签名、Javadoc 注释或 API 用法时使用。
- 用户描述功能需求（如”单据保存”、”数据库查询”）且当前只需要查找匹配 API 或确认 SDK 归属时使用。
- 报表 Algo/DataSet 精确签名、报表取数架构或 `AbstractReport*` 插件问题转交 `kingdee-report`。
- 本 skill 不负责最终实现、运行时修复或元数据挂载分析；需要写苍穹 Java 插件、排障或改造时，把查询结果交回 `kingdee-cosmic` 主控流程。
- 只查询已有项目代码逻辑时直接按源码做只读调用链分析；非苍穹通用功能实现按当前项目的默认实现流程处理。

## 模式

| 模式 | 输出 |
|---|---|
| `lookup` | 从本地 SDK 索引查类、方法或功能关键词 |
| `verify-source` | 按 `references/evidence-source-routing.md` 核对项目、官方或社区来源并给证据状态 |
| `example` | 只在签名已确认且用户需要实现示例时生成最小代码，把结果交回领域 skill |

## 快速工作流

1. **识别查询类型**：判断用户提供的是类名（如 `SaveServiceHelper`）、全限定名（如 `kd.bos.servicehelper.operation.SaveServiceHelper`）还是功能关键词（如”单据保存”）。

2. **执行 SDK 检索**：
   ```bash
   SDK_HELPER_ROOT=<当前 kingdee-sdk-helper skill 根目录>
   uv run python "$SDK_HELPER_ROOT/scripts/sdk_search.py" "<查询词>"
   ```
   如果 `uv` 不可用，使用 `python3 "$SDK_HELPER_ROOT/scripts/sdk_search.py" "<查询词>"`；Windows PowerShell 使用 `py -3 "${env:SDK_HELPER_ROOT}/scripts/sdk_search.py" "<查询词>"`。

3. **处理检索结果**：
   - **单条结果**：直接进入步骤4格式化输出。
   - **多条结果**：先用用户场景、包归属和目标项目引用消歧；仍有多个会改变答案的候选时，展示摘要列表并询问一次。
   - **无结果**（检查点）：提示”未找到匹配结果”，询问用户：”是否需要调整查询词？建议：缩短类名（如 SaveServiceHelper → Save）或使用功能关键词（如'保存'）。”等待用户确认后再次执行步骤2。
   - **脚本报错**：展示脱敏后的错误摘要和失败类型；先检查脚本路径、索引完整性和解释器，再尝试项目 jar/Javadoc、Gradle 依赖或源码引用等只读替代证据。

4. **来源核对**：社区文章、项目片段、旧文档或反编译摘要出现精确 API 时，读取 `references/evidence-source-routing.md`；先回到目标项目 JAR/编译或当前 SDK 索引确认。

5. **格式化输出**：
   - **类概览**：展示全路径名（如 `kd.bos.servicehelper.operation.SaveServiceHelper`）和类说明。
   - **方法列表**：使用三级标题展示方法名，紧随代码块形式的完整签名（包含返回值类型、参数类型、参数名）和 Javadoc 注释（@param, @return, @throws 等）。

6. **生成代码示例**：用户已要求实现或示例时直接基于已确认签名生成；未要求时只给查询结果。
   - 基于 SDK 定义生成符合金蝶开发规范的 Java/Groovy 代码示例。
   - 结合金蝶云苍穹业务背景（如：插件上下文 `IBizContext`、单据实体数据 `DynamicObject`）。

## 门禁与降级
- 不手动读取 `sdk.json` 文件（文件过大），必须通过 `sdk_search.py` 脚本查询。
- 类名不明确时，先进行模糊搜索，不直接猜测。
- 脚本执行失败时，不展示原始连接串、敏感本机路径、租户、账号、token 或完整环境变量；脱敏后说明失败类型和可用替代证据。
- 替代证据只限只读读取项目 jar/Javadoc、Gradle 依赖、已有源码引用或当前 skill references；仍不能确认时明确写“未确认”，不凭记忆生成签名。
- 社区、项目或反编译资料只作为候选；不得覆盖目标项目依赖证据，也不得把项目实现写成标品 API。

## 输出

使用简体中文，给出类全名、完整签名、Javadoc 摘要、归属、证据状态、来源与版本缺口；多候选时明确消歧依据。
