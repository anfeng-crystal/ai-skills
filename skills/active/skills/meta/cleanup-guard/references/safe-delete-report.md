# 安全删除清单模板

用于 `cleanup-guard` 在真正执行删除前输出稳定、可审核的清单。  
这不是骨架占位；它定义了哪些信息必须出现，哪些候选必须停住。

## 适用场景
- 收尾清理测试残留
- 压缩工作区脏区
- 删除未跟踪目录或临时文件前做人工确认

## 输出顺序
1. 先给本轮清理行为统计
2. 再给建议删除清单
3. 再给保留/待确认清单
4. 最后给执行后的回显要求

## 建议删除清单模板

```md
**本轮清理行为统计**
- delete_generated_temp: 是/否，理由
- compress_workspace_noise: 是/否，理由
- no_cleanup: 是/否，理由

**建议删除**
- path: /absolute/path/to/file-or-dir
  type: file | dir
  reason: 本次任务生成的临时产物 / 已确认不在提交范围内 / 用户点名删除
  evidence:
    - 创建来源：本次联调命令 / 本次临时测试目录 / 用户明确指令
    - 提交状态：未进入暂存区 / 未进入本次提交
    - 风险判断：删除不影响已跟踪代码

**保留/待确认**
- path: /absolute/path/to/file-or-dir
  reason: 未跟踪源码文件 / 归因不明 / 位于正式源码目录
  missing_evidence: 无法证明由本次任务生成

**执行后回显**
- 将再次运行 `git status --short`
- 将回显实际删除项与剩余脏区
```

## 最低证据要求
进入 `建议删除` 前，至少要满足以下三条中的两条，且不能违反红线：

1. 能说明文件是本次任务生成的
2. 能说明文件未进入提交范围
3. 能说明文件删除后不会影响正式源码或用户资产

## 红线
出现下列任一情况，默认进入 `保留/待确认`：
- 未跟踪源码文件，且位于正式源码目录
- 只能靠名字像测试文件来判断
- 无法说清创建来源
- 用户没有确认删除范围

## 简短示例

```md
**本轮清理行为统计**
- delete_generated_temp: 是，本轮已确认存在临时测试目录
- compress_workspace_noise: 是，需要先压缩 git status 噪音
- no_cleanup: 否，已有足够证据删除部分临时文件

**建议删除**
- path: /repo/module/src/test
  type: dir
  reason: 本次联调生成的临时测试目录
  evidence:
    - 创建来源：本轮为验证返回结果新增
    - 提交状态：未进入本次提交
    - 风险判断：删除不影响正式源码

**保留/待确认**
- path: /repo/module/src/main/java/.../SomePlugin.java
  reason: 未跟踪源码文件，位于正式源码目录
  missing_evidence: 无法证明它是本次任务生成
```
