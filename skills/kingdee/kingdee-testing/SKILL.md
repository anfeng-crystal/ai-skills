---
name: kingdee-testing
description: "为金蝶云苍穹 Java 插件/服务设计与执行测试、诊断测试失败，或按任务范围验证运行行为；UI 测试交 kingdee-ui-testing。"
license: MIT
metadata:
  author: "anfeng"
  version: "1.1.0"
  tags: "kingdee, cosmic, java, testing, gradle, runtime"
---

# Kingdee Testing
> Cross-platform Agent Skill: use UTF-8, host-neutral paths, and current project commands.

## 职责与交接

把业务验收点转为最小有效检查，区分产品缺陷、测试缺陷和环境问题，给出可核验结果。源码修复与 `kingdee-cosmic` 协同；页面/F7/分录交互测试交 `kingdee-ui-testing`；多日志 Trace、慢 SQL、N+1、线程/GC 交 `kingdee-observability`。

先确认谁做业务验收。用户说“我来测试”时，完成授权的本地检查、构建和环境就绪，保留其页面/业务操作；“总体检查”不自动撤销该分工。用户要求代理实测时按下述运行合同执行，不能用计划或静态检查冒充实测。

## 范围与证据合同

| 模式 | 范围 | 必要事实 |
| --- | --- | --- |
| `local` | 静态、单元测试、Gradle、隔离 harness | 项目、窄测试目标；网络探测仅 loopback |
| `dev-test` | 指定 DEV/TEST 的只读运行验证 | 环境、URL/方法、scope id、预期证据 |
| `prod-readonly` | 已授权生产范围的只读验证 | 授权、环境、时间/记录边界、脱敏 |
| `approved-write` | 任务明确授权的业务写操作 | 方法/路径、载荷来源、范围、恢复、请求上限及结果核对 |

从当前指令、项目配置和连接器恢复已有事实，不让用户重复可查值；凭据存在不代表获授权。运行请求前读[执行合同](references/execution-contract.md)。授权覆盖的步骤继续执行，不逐次确认；越出目标、动作、记录、路径或时间范围则停在边界。凭据仅在运行内存使用，不进入输出或资产。

## 验证流程

1. **建立验收映射**：`业务结果 → 受影响调用链/分支 → 检查和断言 → 证据/缺口`。失败时保存命令、断言、堆栈和位置，区分编译、测试逻辑、产品、依赖、元数据或运行问题。按变更选择正常、空值、边界、失败、状态和副作用，不机械穷举。
2. **确认平台事实**：字段/入口复用有效 analyzer inventory，缺失或范围不足才补查；API 交 `kingdee-sdk-helper`。测试基类、断言、JDK 与 SDK 使用实际项目合同，`SvcUnitTest*` 只是条件化示例，不默认要求，也不靠无来源黑名单判废弃。
3. **选择最小有效检查**：纯逻辑优先单元测试；平台事件核对独立的 SDK/客户端/运行证据再设输入。回调只注入实现期待的枚举、自己比较自己或只断言无异常，不能证明真实链路；至少观察本次相关的保存调用、错误、返回/关闭或刷新结果。
4. **修正并复核**：授权内做最小产品/测试修改，按[测试策略](references/test-strategy.md)复用已有用例。先定 `task-local`/`formal` 归属，再生成资产；针对性检查通过后，只有共享影响、残余缺口或项目规则要求才扩大回归，不隐藏既有失败。
5. **执行对应运行验证**：仅在任务范围和模式要求时做真实入口/数据核对；用户保留的验收不代做。模拟、静态、目标编译、运行和用户验收各留各的证据。
6. **交付并清理**：按[交付证据](references/delivery-evidence.md)核对包、部署与临时资产。环境恢复不等于业务通过，完成当前授权的验证点后交付。

## 测试质量

- 拒绝假断言、自比较、吞异常、未达到断言的测试、Mockito 通配导入和泄漏的 `MockedStatic`；保留常量/枚举，不用字符串伪造缺失平台符号。
- 目标版本沿用任务，测试实际类路径必须匹配；7.0 不能以 8.0 索引、桩或异版编译证明兼容。不为通过测试升级依赖；实际 JAR 足够时不重复索要补丁，冲突只阻塞相关结论。
- `test NO-SOURCE` 表示未执行测试；编译成功不能证明事件映射、权限、事务或保存生效。部署请求返回也不等于服务恢复或页面验收。
- `formal` 仅限用户要求交付测试源码，或产品修复确需长期回归且项目策略允许；一次性探测、harness、夹具属于 `task-local`。交付前按本轮创建记录精确清理，不凭 Test/Probe 文件名删除已有资产。
- 本 Skill 不自行提交、推送、改在线元数据/配置或扩大业务写范围；主任务另有授权时由对应交付流程执行。证据去除凭据、会话、租户/人员标识、内网地址、连接串、SQL 参数和业务样本。

## 按需资料与工具

- 单元测试：`references/unit-test-generation.md`；覆盖映射：`testcase-completeness.md`；策略/批量补测：`test-strategy.md`；回归：`regression-playbook.md`（均在 references/ 下）。
- 运行：`references/execution-contract.md`、`cosmic-runtime-harness.md`、`dev-runtime-verification.md`；元数据：`references/metadata-driven-testing.md`；API/跨模块：`references/deprecated-api-blacklist.md`、`cross-module-allowed.json`。
- `scripts/run_gradle_tests.py` 跑明确模块任务，解析不明先 `--dry-run`；`scripts/run_dev_probe.py --dry-run` 校验运行合同；`collect_runtime_evidence.py`、`create_test_harness.py` 只写明确输出目录（均在 scripts/ 下）。

## 输出

用中文报告验证结论、必要诊断/改动、实际检查及其来源、既有失败和剩余缺口。用户验收通过按其确认记录，不冒称代理亲自操作；未经运行的场景明确未验证，不以检查数量代替质量。
