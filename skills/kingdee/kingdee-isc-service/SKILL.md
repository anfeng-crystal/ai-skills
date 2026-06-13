---
name: kingdee-isc-service
description: "Kingdee Cosmic ISC integration service cloud troubleshooting: value-conversion, event-trigger, exec-log, field-mapping, database, EAS, connection, OpenAPI, performance error diagnosis from DC logs. Use for 苍穹集成服务云(ISC)报错排查、值转换/事件触发/执行日志/字段映射/数据库/EAS集成/连接网络/OpenAPI/大数据量错误诊断;ISCB DSL 脚本编写交 ISCB 脚本 skill,Java 二开交 kingdee-cosmic。"
metadata:
  author: anfeng
  version: "1.0.0"
  license: MIT
  tags: [kingdee, cosmic, isc, integration, troubleshooting, diagnostics]
---

# Kingdee ISC Service
> Cross-platform Agent Skill: use host-neutral paths and current project commands.

苍穹集成服务云(ISC)报错的**离线只读诊断**:按报错关键词/日志路由到错误分类与执行阶段,给出根因与解决方向。需要用户提供 DC 错误日志或报错关键词。

## 触发边界
- **适用**:ISC 集成服务云报错排查 —— 值转换、事件触发、执行日志/启动、字段映射、数据库/服务流程、EAS 集成、连接网络、OpenAPI、大数据量/性能、监控统计。网络/OpenAPI 类问题只分析日志和配置口径，不实际探测接口。
- **不适用(转交)**:
  - ISCB 集成云 DSL 脚本的编写/解释/重构 → ISCB 脚本 skill。
  - 苍穹 Java 插件/报表开发 → `kingdee-cosmic` / `kingdee-report`。
  - 苍穹平台元数据/字段证据 → `kingdee-metadata-analyzer`。
- 必须有报错日志或关键词才能精确诊断;泛泛"集成有问题"先要日志,不凭空给结论。

## 工作方式
- **纯离线、只读诊断**:仅分析与建议,不联网、不执行 `curl`/命令、不改配置或数据。
- **输入**:完整 DC 错误日志(时间戳/错误码/堆栈)或报错关键词 + 场景。
- **输出**:命中的错误分类与参考文档、根因分析、标准解决方向。

## 快速工作流
1. 收集报错日志或关键词;必要时先按执行阶段(取数/转换/写数)定位。
2. 用 `references/error-routing.md` 的关键词路由表命中错误大类与对应文档。
3. 深挖时进入 `references/dc-catalogs.md` 指向的 `dc_err/`(按错误类型)或 `dc_stage/`(按执行阶段)条目。
4. 给出根因 + 解决方向 + 验证建议;涉及改配置/数据时只给方案,由用户在授权环境执行。

## References
- 关键词→分类→文档 路由表:`references/error-routing.md`
- dc_err(按错误类型)/ dc_stage(按执行阶段)目录:`references/dc-catalogs.md`

## Guardrails
- 不联网、不执行命令、不调用接口、不改配置或数据;只读诊断。
- 无日志/关键词时先要输入,不臆测根因。
- 诊断按"先定位阶段(取数/转换/写数)再深挖错误类型"的顺序,避免泛域误判。
- 不在输出中写真实地址、账号、密码、内网信息；输入日志中的 host/IP、tenant/accountId、Authorization、Cookie、access_token、手机号、邮箱和数据库连接串默认脱敏。
- 解决方案涉及生产改动时,只给步骤与风险,执行交用户在授权环境完成。

## Output
使用简体中文:结论(命中分类)→ 根因分析 → 已脱敏字段/未确认字段 → 解决方向(步骤)→ 验证建议 → 未确认项。
