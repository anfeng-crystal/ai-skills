# 设计输入与实现规则

## 读取设计交接

- 从交接入口核对设计版本、选定依据（用户确认或授权后的决定）和参数来源。用交互稿了解实际操作，按标明的来源读取采用的基准或选定值，核对对应组件、状态和尺寸。小项目可直接使用现有规范、参数表或原型源码；已有设计系统时沿用项目约定的来源和格式，例如主题配置、`DESIGN.md` 或参数快照。Google `DESIGN.md` 的 YAML `version` 表示格式版本。 [Google DESIGN.md](https://github.com/google-labs-code/design.md#the-format)
- 按已有主题和配置映射采用值，保留单位、token 引用以及尺寸和状态覆盖。材料不全时，结合已有代码、需求或指定美工稿实现能明确的部分。材料冲突时，按选定依据核对采用版本和受影响的参数。
- 从项目实际入口复跑关键状态的最短路径，按必要前置条件和动作核对可观察结果，记录实测与未验证项。已有验收用例能说明时直接使用；路径缺项且可从需求或原型确定时，在现有实施或验收记录中补齐。

## 组件状态与动效实现

- 以 Component Variant（组件变体）和 State Matrix（组件状态表）为对照，在项目实际组件中落实适用的悬停、按下、键盘焦点、选中、禁用、加载和错误等状态。用实际渲染核对前景与背景的可读性，走通状态的触发、退出与回退。 [shadcn 组件状态方法](https://github.com/shadcn-ui/ui/blob/main/skills/shadcn/design-system-page.md)
- 动效用来说明状态变化。高频动作优先即时反馈。需要过渡时优先复用项目已有的实现及变量，连续操作从当前画面过渡到最新状态。验证退场、中断、触控和 Reduced Motion（减少动态效果）下的可见反馈。 [Emil 的动效规则](https://github.com/emilkowalski/skills/blob/main/skills/animate/SKILL.md)
