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
| `example` | 用户需要实现示例且所用 API 已有目标版本依据时生成最小代码，把证据与代码交回领域 skill |

## 目标版本

- 复用用户已明确的产品、运行版本和项目合同，再从实际依赖、SDK/JAR、声明或配置补齐证据。用户说 `7.0` 不等于某个 `7.0.x` 补丁，也不能被内置 `8.0.1` 索引提升为 8.0；版本约束属于目标任务/项目，不将所有项目固定为 7.0。
- 生成或修改平台 API 调用前确认所用类、重载、返回类型和所需行为适用于目标。索引命中只证明该索引有记录，即使版本字符串相同，也不能自动成为目标项目兼容证明。详见 `references/evidence-source-routing.md` 的“生成代码的版本判定”。
- 版本缺口先用已有项目证据解决；补丁号未知但实际目标依赖已能确认本次 API 时，不机械要求用户补全。仅暂停依赖未知 API 的实现，继续独立查询、分析和本地检查，不为核版本新增登录、安装或逐项批准。

## 快速工作流

1. **识别查询类型与目标**：判断用户提供的是类名（如 `SaveServiceHelper`）、全限定名（如 `kd.bos.servicehelper.operation.SaveServiceHelper`）还是功能关键词（如”单据保存”）。纯查询可以没有目标项目；实现任务沿用已确认的目标版本，不将“查询新版本资料”当作升级目标。

2. **执行 SDK 检索**：
   ```text
   <verified-python> <actual-skill-root>/scripts/sdk_search.py <查询词>
   <verified-python> <actual-skill-root>/scripts/sdk_search.py <查询词> --target-version <已知目标版本> [--sdk-path <已有目标索引文件>]
   ```
   从当前宿主解析实际 Skill 根和已核实的 Python；优先进程参数数组。`uv run python`、`python3`、Windows `py -3` 都是可用启动方式，按当前 shell 正确引用路径，不要求某个环境变量或固定目录。已知目标是 7.0 时传 `--target-version 7.0`，不补造补丁号；已有同结构的目标 SDK 索引时可用 `--sdk-path`，不要求下载新索引。保留输出中的索引版本、来源和目标兼容未验证提示；默认随包索引的版本以实际 metadata 为准。

3. **处理检索结果**：
   - **单条结果**：进入步骤4核对来源；唯一命中不表示目标版本可用。
   - **多条结果**：先用用户场景、包归属和目标项目引用消歧；仍有多个会改变答案的候选时，展示摘要列表并询问一次。
   - **无结果**（检查点）：先按门禁使用当前 references、项目 JAR/Javadoc、Gradle 依赖或已有源码引用做只读替代检索；替代证据仍不足时报告“未找到匹配结果/未确认”。只有继续调整查询词会改变结论且用户需要选择时，才询问一次，并建议缩短类名或改用功能关键词。
   - **脚本报错**：展示脱敏后的错误摘要和失败类型；先检查脚本路径、索引完整性和解释器，再尝试项目 jar/Javadoc、Gradle 依赖或源码引用等只读替代证据。

4. **来源与目标核对**：所有结果均按 `references/evidence-source-routing.md` 区分索引事实和目标依据；不能等到发现冲突才查看项目依赖。带版本索引可以确认该来源的签名，目标实现还需与目标一致的实际依赖/声明或适用目标的官方依据；异版或无版本资料只作候选。金蝶社区官方知识库按发布主体和产品/版本归类；索引没命中或新版本没列出某方法，不等于该方法在旧版已废弃。

5. **格式化输出**：
   - **类概览**：展示全路径名（如 `kd.bos.servicehelper.operation.SaveServiceHelper`）和类说明。
   - **方法列表**：展示完整返回值和参数类型、重载、静态/实例属性及已确认的 Javadoc。参数名只有来源确实提供时才列出；字节码缺参数名时说明缺口，不据参数名差异判定新重载或编造签名。SDK 的 `@Deprecated`、KingScript 的 `scriptDeprecated` 与内部 API 标记分别判断。

6. **生成代码示例**：用户已要求实现或示例，且本次所用 API 的目标版本依据明确时生成；`confirmed-index` 单独不足以进入目标实现。未要求示例时只给查询结果。
   - 基于目标版本已确认的 SDK 定义生成符合金蝶开发规范的 Java/Groovy 代码示例；用户明确要求某版本的独立示例时标明该示例目标，不把它写入不同版本的项目。
   - 结合金蝶云苍穹业务背景（如：插件上下文 `IBizContext`、单据实体数据 `DynamicObject`）。

## 门禁与降级
- 不手动读取 `sdk.json` 文件（文件过大），必须通过 `sdk_search.py` 脚本查询。
- 类名不明确时，先进行模糊搜索，不直接猜测。
- 脚本执行失败时，不展示原始连接串、敏感本机路径、租户、账号、token 或完整环境变量；脱敏后说明失败类型和可用替代证据。
- 替代证据只限只读读取项目 jar/Javadoc、Gradle 依赖、已有源码引用或当前 skill references；仍不能确认时明确写“未确认”，不凭记忆生成签名。
- 社区、项目或反编译资料只作为候选；不得覆盖目标项目依赖证据，也不得把项目实现写成标品 API。

## 输出

使用简体中文，给出类全名、完整签名、Javadoc 摘要、归属、来源版本、目标版本及其兼容依据/缺口；多候选时明确消歧依据。区分查询结果、目标实现和已执行的验证，不能将脚本的索引版本比较写成目标编译或运行通过。
