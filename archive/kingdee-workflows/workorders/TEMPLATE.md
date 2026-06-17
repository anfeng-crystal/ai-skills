# 标准化工单模板

工单文件存放路径：`/Users/anfeng/KingdeeKnowledge/workorders/active/`
归档路径：`/Users/anfeng/KingdeeKnowledge/workorders/archived/`

## 工单文件命名规范
`WO-{YYYYMMDD}-{序号}-{agent类型}.md`

示例：`WO-20260412-001-ops.md`

## 工单模板

```markdown
# 工单 {工单ID}

## 基本信息
- **工单ID**: WO-{YYYYMMDD}-{序号}-{agent类型}
- **需求主题**: {用户需求核心描述}
- **派发对象**: {执行agent类型: ops/requirement/metadata/frontend/backend/testing/asset}
- **创建时间**: {YYYY-MM-DD HH:mm}
- **状态**: {待执行/执行中/已完成/已打回/已归档}

## 任务目标
{明确、可量化、可验收的任务目标}

## 验收标准
{刚性验收要求，必须符合核心规则}
1. {标准1}
2. {标准2}
3. ...

## 交付物清单
- [ ] {交付物1}
- [ ] {交付物2}
- ...

## 关联信息
- **工程路径**: /Users/anfeng/Code/Study/{具体工程}
- **元数据地址**: {如适用}
- **需求文档**: {如适用}
- **前置工单**: {如适用}

## 核心规则
- 必须遵守的刚性规则列表

## 执行记录
### {YYYY-MM-DD HH:mm} - {执行动作}
{执行详情}

## 交付结果
- **完成时间**:
- **交付摘要**:
- **质量评分**: /10
```

## Agent 类型标识
| 标识 | Agent | 生命周期 |
|------|-------|----------|
| ops | 工程运维 agent | 常驻 |
| requirement | 需求管理 agent | 按需 |
| metadata | 元数据开发 agent | 按需 |
| frontend | 前端开发 agent | 按需 |
| backend | 后端开发 agent | 按需 |
| testing | 测试验收 agent | 按需 |
| asset | 资产沉淀 agent | 常驻 |
