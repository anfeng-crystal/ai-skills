# Testcase Completeness

Use this card before generating tests and again before reporting coverage.

## Build the inventory

For each public behavior, list the observable contract, inputs, collaborators, state, branches, outputs, side effects, and failure modes. Mark every case as `required`, `risk-based`, or `excluded` with a reason.

Cover applicable dimensions:

| Dimension | Minimum cases |
| --- | --- |
| Nominal | One representative successful path with meaningful assertions |
| Null/empty | `null`, empty string, empty collection, missing DynamicObject field |
| Boundary | Zero, one, maximum/minimum, equality boundary, before/at/after date |
| Collection | Zero/one/many, duplicate entries, stable order when contractual |
| Branch | Every business predicate outcome and early return |
| Exception | Collaborator error, invalid input, retry/fallback, exception propagation |
| Side effect | Expected call and absence of forbidden calls on rejected paths |
| State | Every allowed transition and at least one rejected transition |
| Context | User, tenant/account, locale, time, and permission variants actually read by source |
| Metadata | Confirmed field/form/entry variants only; block invented keys |
| Idempotency | Repeat execution when the behavior promises idempotency or deduplication |

## Trace cases to source

Maintain a compact matrix:

```text
behavior -> source branch -> testcase -> assertion/verify -> execution result
```

已有需求、方案、已批准计划或用户范围修订时，在同一矩阵关联“当前有效条目/版本或原文位置 → 可观察行为 → 测试/检查 → 实际证据”；不为普通补测另建需求文档或编号体系。撤销/替换条目不再算本次必交覆盖；未受变更影响且仍匹配当前代码/环境的已通过证据可复用，受影响条目按新范围重新验证。

Line and branch coverage are supporting evidence, not proof of behavioral completeness. Keep the existing 90% line and 80% branch targets when the project uses this gate, but report uncovered business scenarios separately.

## 覆盖率报告的来源与口径

仅在用户要求覆盖率分析、补齐覆盖率或项目门禁需要时收集，不为普通修复新增 CI 查询或报告插件。优先读取已有本地/CI 产物，在线查询仍遵守运行合同与凭据边界。

- 记录报告来源、生成时间、代码提交或工作区状态、构建标识、模块/测试任务，以及包含/排除范围；缺失项写未知，不补造。
- 核对报告原生指标及分母：指令、行、方法和分支覆盖率分别报告，不能把 `INSTRUCTION` 换名为行覆盖率；缺少分支指标不等于分支全部通过。
- 本地新代码与滞后 CI、增量与全量、不同排除范围不能直接合并或比较。先说明对应关系；口径无法对齐时分别给结果，不用旧报告证明本次改动。
- 覆盖率只帮助定位未执行路径；仍回到上面的行为矩阵核对断言。测试通过但报告未生成、测试未执行或 `NO-SOURCE` 各自报告，不伪造百分比。

## Reject weak coverage

- Do not count getters, setters, constructors, or pure delegation solely to raise coverage.
- Do not count a test that swallows an exception, exits before assertions, or only verifies mock setup.
- Do not copy the current defective output into an assertion when the intended contract is known.
- Do not broaden production or runtime scope to fill a local coverage gap.

## Completion report

List required cases passed, required cases blocked, risk-based cases deferred, justified exclusions, and whether evidence is static, local-executed, or runtime-verified.
