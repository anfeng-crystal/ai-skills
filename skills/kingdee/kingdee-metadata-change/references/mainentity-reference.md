# 主实体映射规则

主实体映射的权威标准合同是 `mainentity-contract.json` 和 `standard-mainentity.jsonl.gz`，实际业务状态由 `t_meta_mainentityinfo.fdentityid` 精确关联目标实体。

## 适用范围

物理表、主键、编码/名称字段、主组织字段，以及工作流、BOTP、凭证、导入、打印和名称版本等主实体能力。

## 校验

- 先解析实体实际继承链，再用链上实体 `fid` 关联标准主实体行；不能只按表名或 ModelType 选样本。
- 每个列名和值形态必须存在于固化合同；各 ModelType 的实际非空列用于识别能力边界。
- 表单按钮存在或可见不证明主实体能力已开启；反之亦然。
- `mainentityinfo` 没有 XML `fdata`，实体/表单 XML 哈希不能替代该行证据。
- 目标业务行缺失、不唯一或需要数据库写入时停止离线包修改，交 analyzer 取证并按单独授权的数据库/平台路径执行。
