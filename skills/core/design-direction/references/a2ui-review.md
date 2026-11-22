# A2UI 接入

按目标 renderer 所支持的协议和 catalog 建立 surface。可编辑组件使用稳定 ID，将文本、颜色及布局属性绑定到数据模型。标准组件未提供所需属性时，在当前 catalog 注册对应组件。项目的阅读、导航、提交或媒体等行为接到组件自身的 action。[A2UI 协议](https://a2ui.org/specification/v1.0-a2ui/) · [数据绑定](https://a2ui.org/concepts/data-binding/) · [组件 catalog](https://a2ui.org/guides/defining-a-catalog/) · [组件动作](https://a2ui.org/concepts/actions-and-functions/)

## 编辑与交接

复用 [a2ui-editor.mjs](../scripts/a2ui-editor.mjs) 管理编辑。每个方案独立持有草稿，多个视口订阅同一份值。项目适配层负责把组件和可编辑字段对应起来，并将编辑结果画到作品上。试调与用户确认的版本分开保存。

交接可打开的入口、同版源稿和素材。独立交付时连同所需 renderer、catalog 和依赖一起打包。用所选快照复现用户确认的文本、颜色和位置。

项目通过 `createDataModelPublisher` 将编辑状态发布到 A2UI v1.0 surface。每个方案建立一个 `DraftHistory`，以 `setText`、`setColor` 修改字段，以 `move` 更新坐标或以 `reorder` 调整已绑定的顺序。字号、间距、透明度和时长等数值及枚举值通过 `edit` 更新。适配层按[设计参数规范](design-parameters.md)处理范围、单位和尺寸覆盖。撤销、还原与快照读取复用同一实例。

## 验证

共用编辑函数变更时，在 Skill 目录运行 `node --test scripts/a2ui-editor.test.mjs`。新增组件、变更绑定或更换 renderer 时，复用参数化检查验证输入到数据模型和实际组件的变化，同时核对恢复值。沿用已验证的接入、只换内容或样式时，直接检查目标尺寸下的真实画面。涉及作品自身业务交互的变动，验证对应流程。
