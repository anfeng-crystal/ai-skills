# 生成后自动校验规则 (Post-Check)

`cosmic-post-check.py` 是代码生成后的**统一检查入口**，自动选择最佳检查策略：

- **Gradle 项目** → 执行 `./gradlew :module:compileJava` 真实编译，由 Java 编译器捕获所有错误
- **非 Gradle 项目** → 回退到 `cosmic-post-lint.py` 静态校验（A/B/C 三层规则）

## 触发条件

**每次 AI 生成或修改 `.java` 文件后，自动触发**，无需用户手动请求。

## 默认执行命令

```bash
export KINGDEE_COSMIC_SKILL_ROOT=/Users/anfeng/AI/skills/active/skills/kingdee/kingdee-cosmic
python3 "$KINGDEE_COSMIC_SKILL_ROOT/scripts/cosmic-post-check.py" <生成的文件或目录> --fix-hint
```

脚本自动判断：
1. 从目标文件路径**向上查找** `build.gradle` + `settings.gradle` 共存的目录
2. 找到 → Gradle 编译（解析 `settings.gradle` 确定模块，执行 `./gradlew :module:compileJava`）
3. 未找到 → 回退到 `cosmic-post-lint.py --fix-hint` 静态校验

## 严格模式（仅 post-lint 回退时生效）

当用户明确要求"严格校验""模板升级治理""补事实来源留痕"时，再追加严格模式：

```bash
export KINGDEE_COSMIC_SKILL_ROOT=/Users/anfeng/AI/skills/active/skills/kingdee/kingdee-cosmic
python3 "$KINGDEE_COSMIC_SKILL_ROOT/scripts/cosmic-post-check.py" <生成的文件或目录> --fix-hint --strict
```

说明：

- `--strict` 仅在非 Gradle 回退到 post-lint 时生效，额外检查 **C 层** 验证来源注释。
- Gradle 编译本身不区分严格/宽松——编译器检查的就是全部约束。

## 校验流程

```text
生成代码
  └→ 执行 cosmic-post-check.py
        ├→ 检测到 Gradle 项目?
        │     是 → ./gradlew :module:compileJava
        │           ├→ 编译成功 → ✅ 通过
        │           └→ 编译失败 → 修复代码 → 重新编译（最多 3 轮）
        │
        └→ 否 → 回退 cosmic-post-lint.py
                ├→ 有 ERROR?      是 → 必须修复 → 重新 lint（最多 3 轮）
                ├→ 无 ERROR 但有 WARNING? → 优先修复；若是历史兼容写法，可说明保留理由
                └→ 仅 INFO?       → 记为治理项，不阻断当前交付
```

## 问题级别处理策略

| 级别 | 对应层级 | 处理方式 | 是否阻断 |
|------|----------|----------|----------|
| ❌ ERROR | A 层硬约束 | 必须修复，根据 fix-hint 立即调整代码 | **是** |
| ⚠️ WARNING | B 层推荐项 | 新代码优先修复；历史代码可结合上下文评估是否本次顺手收敛 | 否 |
| 💡 INFO | C 层治理项 | 记录为治理建议，适合模板升级或批量重构 | 否 |

## 规则 ID 与层级映射

| ID 前缀 | 默认层级 | 类别 | 来源文件 |
|----------|----------|------|----------|
| `HAL-METHOD-*` | A | 幻觉方法名 | anti-patterns.md |
| `HAL-CLASS-*` | A | 幻觉类名 | anti-patterns.md |
| `API-*` | A | 知识库 API 校验 | 知识库数据库 |
| `SCENE-*` | A / B | 场景错配 | anti-patterns.md |
| `STYLE-*` | B | 编码偏好 | coding-preferences.md |
| `RESOURCE-*` | A / B | 资源管理 | anti-patterns.md |
| `VERIFY-*` | C | 验证来源留痕 | constraints.md / coding-preferences.md |

补充说明：

- `API-*` 规则通过动态查询 `知识库数据库` 知识库校验方法调用，**仅校验白名单包前缀**（`kd.bos.*`、`kd.bd.*`、`kd.sdk.*`、`kd.cd.common.*`、`kd.cd.core.*`、`kd.cd.webapi.*`、`kd.cd.feature.*`），不校验 Java 标准库或项目自有包。
  - `API-001`：方法名在该类上不存在（含继承链）→ ERROR
  - `API-002`：方法参数个数与所有重载均不匹配 → ERROR
  - `API-003`：类名解析到白名单包但知识库无记录 → WARNING
- `SCENE-*` 与 `RESOURCE-*` 中既有明显硬错误，也可能包含偏治理的 warning；解释结果时要结合上下文，不要机械套标签。
- 需要按 A 层（ERROR）处理的 SCENE/STYLE/RESOURCE 规则 ID，统一定义在 [a-layer-rules.json](a-layer-rules.json)（单一可信源），`cosmic-post-lint.py` 在运行时自动加载。
- 当前列表：`SCENE-010`、`STYLE-009`、`STYLE-011`、`STYLE-012`、`STYLE-014`、`STYLE-015`、`STYLE-016`、`STYLE-018`、`RESOURCE-004`。如需新增/移除，直接编辑 JSON 文件即可，无需改脚本代码。
- `VERIFY-*` 默认不作为当前交付阻断项；只有在 `--strict` 或用户明确要求治理时，才应提高关注度。

## 修复示例

当收到如下 lint 报告时：

```text
❌ L 31 [HAL-METHOD-001] 苍穹不存在 setReadOnly() 方法
   > dataEntity.setReadOnly(true);
   💊 修复: 使用 getView().setEnable(false, "key")
```

AI 应：

1. 将 `dataEntity.setReadOnly(true)` 替换为 `getView().setEnable(false, "fieldKey")`
2. 重新执行 lint，确认该 `ERROR` 消失
3. 检查修复是否引入新的场景错配或资源问题

## 对历史项目的解释口径

- 出现 `WARNING` 时，不要直接说"代码错误"；优先判断它是：
  - 新代码应该采用的默认写法
  - 历史项目当前可接受的兼容写法
  - 适合本次顺手治理的低风险改动
- 出现 `INFO` 时，默认按"后续治理建议"表述，不要阻断当前任务。

## 重试上限

- 单个文件最多执行 **3 轮** "修复 → 复检" 循环
- 3 轮后仍有 `ERROR` 未消除，停止自动修复，向用户报告剩余问题清单并请求人工介入
