---
name: kingdee-sdk-helper
description: "查询和核验金蝶云苍穹 SDK 类、方法签名、Javadoc 与目标版本依据；业务实现交回对应领域 skill。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.2.0"
  tags: "kingdee, cosmic, SDK, API, Javadoc"
---

# Kingdee SDK Helper
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

## 职责

把类名、方法名或功能问题转换成有来源的 API 调用合同：声明者、完整签名、参数语义、返回/回调行为、目标版本及尚缺证据。最终业务实现交 `kingdee-cosmic`；报表 Algo/DataSet 精确签名交 `kingdee-report`。只分析已有项目代码或通用 Java 时不必查 SDK。

| 模式 | 交付 |
| --- | --- |
| `lookup` | 定位类、方法、功能候选 |
| `verify-source` | 按[证据来源](references/evidence-source-routing.md)核对来源与目标，确认到具体事实 |
| `example` | 用户需要且目标 API 合同已确认时给最小示例，交回领域 Skill |

## 查询流程

1. **确认问题和目标**：区分类名、全限定名、方法或业务关键词；纯查询可无项目。实现任务沿用已确认产品/运行版本，按实际依赖、JAR/Javadoc 或声明补证，不从默认索引推断项目版本。
2. **定位候选**：优先复用本次已有证据；需要索引时按下面的脚本入口检索。类名不明确先模糊查，多候选按场景、包和项目引用消歧；只有仍存在会改变答案的选择才询问。
3. **沿声明链核对**：本类未列方法时查已证实的父类/接口、可见性及完整重载，不能把未列出当不存在、猜继承关系或把 private 方法当公开调用。无命中/脚本失败时查现有 JAR、同版本 Javadoc、Gradle 依赖及源码；先核路径、索引和解释器，不原样反复重试。
4. **建立调用合同**：按[证据来源](references/evidence-source-routing.md)确认目标实际可用的类、重载、静态/实例属性、参数顺序/含义及返回类型。多个 String/Object 参数尤其核对应用、实体、记录、权限项等各自语义；事件还需确认触发阶段、上下文和结果映射。编译通过不能补足这些行为证据。
5. **交付或生成示例**：给出能确认的结果和最小缺口。示例使用已确认的目标 API、元数据和项目封装；没有目标兼容依据时只给候选，不写成可运行实现。未要求示例则不额外生成代码。

## 索引入口

不直接读取大型 `sdk.json`，使用查询脚本：

```text
<verified-python> <actual-skill-root>/scripts/sdk_search.py <查询词>
<verified-python> <actual-skill-root>/scripts/sdk_search.py <查询词> --target-version <已知版本> [--sdk-path <已有目标索引>]
```

从当前宿主解析实际根路径和 Python，优先进程参数数组，按 shell 正确引用路径。`uv run python`、`python3`、Windows `py -3` 均按已有条件选择，不要求固定变量、安装目录或下载索引。保留脚本返回的来源/版本与兼容未验证提示。

## 证据与恢复边界

- `7.0` 保持原粒度，不补造补丁号，也不被 8.0.1 索引提升版本。补丁未知但实际目标依赖已证明本次 API 时继续；目标与类路径冲突先查原因，不升级 SDK 来让编译通过。跨版本资料仅作候选。
- 索引唯一命中、版本文本相同、项目源码存在或 mock 通过均不自动证明目标可用。未知事实只暂停依赖它的代码，继续独立查证；不为查版本额外登录、安装或逐项请求批准。
- 字节码无参数名时说明缺失，不编造语义；参数名不同不代表新重载。SDK `@Deprecated`、KingScript `scriptDeprecated`、内部接口和项目封装分别判断，未命中不是废弃证据。
- 只读替代证据仍不足时明确“未确认”。项目片段不当标品事实，官方/社区按发布者、正文和适用版本判断，不按域名一刀切。需要最新在线依据时使用官方一手来源。
- 失败报告只给脱敏类别和可用替代来源，不回显连接串、账号、租户、凭据或完整环境变量。

## 输出

使用简体中文，按问题给出类全名、完整签名、必要 Javadoc/语义、消歧依据、来源与目标版本、证据状态和缺口。签名已确认、行为有依据、已编译、已运行分别陈述；不能将索引比较、示例或推断冒充目标实测。
