# 多语言与术语变更规则

四个层独立处理：`entity_l`、`form_l`、`entity_term`、`form_term`。实体名不能写到表单侧，术语不能与普通多语言行合并。

`localization-term-contracts.json` 保存目标环境实际侧表列、值形态、locale 集合和行数；完整标准记录中保留每个模板/祖先的实际侧表行。`zh_CN` 只是一个 locale，不能默认代表全部语言。

## 修改已有行

- 按 `kind + Number + Id/PkId + LocaleId` 唯一定位平台包中的现有 wrapper；
- 只改基线中实际存在的标量属性，例如 `Name`；
- `Id/PkId/LocaleId/Number` 属于身份/关联，不按普通属性改；
- 变更实体或页面名称时分别对账对应侧表，不能只看到 DYM 主文件就声明语言已同步。

## 新增或删除行

数据库标准行只证明侧表形态，不证明 DYM/DYMX 身份和序列化生成规则。新增 locale/term 必须由同版本平台生成并导出，走 `verify-platform-candidate`；删除需平台支持和完整语言影响确认。标准链没有某 locale 行是 `confirmed-absent`，不授权自动复制其他语言。
