# 构建、测试与 DEV 交付证据

在报告 Gradle、包、DEV 部署或 Git 交付结果前读取本卡片。

## 测试资产归类

- 生成测试前标记 `task-local` 或 `formal`。用户明确要求交付测试源码，或已授权的产品修复需要长期防回归且仓库测试策略允许时，才归为 `formal`；仅用于本轮探测、复现或 harness 的测试类、脚本、夹具和数据归为 `task-local`，优先放系统临时目录或隔离 worktree。
- `formal` 测试必须属于用户要求或项目既有测试体系，并通过目标模块测试；不能为了保留临时验证代码而擅自改成交付资产。若产品修复没有交付 formal 回归，必须明确报告原因和剩余风险，不能一边删除 task-local reproducer 一边声称已保留回归。
- Git handoff 前对比本轮创建清单、`git status` 和 staged diff。精确清理本轮 `task-local` 资产；保留所有既有、已跟踪或归因不明测试。发现 task-local 文件已进入提交/待推送范围时阻断交付。

## Gradle 证据

- 从向上发现的 Gradle 聚合根/wrapper 运行明确模块任务，不因当前 cwd 是子模块就假设 wrapper 在本目录。
- `SUCCESS` 只说明命令成功。`test NO-SOURCE` 表示没有测试源码被执行，必须报告“0 个自动化测试/无测试源码”，不能写“测试通过”。
- 分层记录 compile、test（实际执行数量）、静态检查、jar/zip 内容；任何一层不能替代另一层。

## 包与部署

- 打包前核对正式源码范围；包内不能混入 task-local 测试、旧候选包或无关工作树改动。检查 ZIP 成员和目标 JAR/字节码，而不只看文件存在或 Gradle 成功。
- `uploadZipRestartAndWait`、HTTP 请求成功或重启命令返回只说明动作已请求。部署完成必须满足项目的服务状态合同；若合同要求 `status=2`、`run_count=desired_count` 和 `lstime` 更新，就逐项取证后再报告完成。
- 服务恢复只证明运行单元可用。页面任务还要从用户真实业务入口（例如首页/菜单），按目标 formId、布局和挂载链验证；开发平台预览不替代业务页面。

## 本地启动交付

用户要求“本地启动某环境，我来测试”时，不能只给命令或把测试交回。至少确认：启动进程仍存活、目标端口监听、项目定义的 `platform_ready`/等价就绪标记成立；若任务包含自动登录或打开页面，还要确认预期登录结果和目标页面/首页已实际打开。任一项未满足时只能报告 `not_started` 或 `not_ready`，不能说“可以测试”。

## 输出状态

只使用与证据相符的状态：

- `compiled`：编译成功；
- `tests_passed`：实际执行的测试用例通过；
- `test_no_source`：测试任务无源码；
- `package_verified`：成员、范围和摘要已核对；
- `restart_requested`：仅请求重启；
- `service_recovered`：服务状态/实例数/时间戳满足合同；
- `runtime_verified`：真实业务入口和指定场景通过。
- `local_ready_for_user`：进程、端口、平台就绪和任务要求的登录/页面标记全部满足。
