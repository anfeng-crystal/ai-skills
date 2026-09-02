# ISCB Skill 维护与分发

只在修改本 skill 的 validator、runtime、规则、reference、cases、示例或分发结构时读取；普通 ISCB 业务任务不加载。

## Bundle 完整性

- curated regression 位于 `assets/cases/manifest.json` 与 `assets/cases/**/*`。
- 对外分发至少保留：`SKILL.md`、`references/`、`agents/openai.yaml`、engine/platform manifests、`iscb_skill_validator.py`、DTS 服务流程只读分析器、受控 review-copy 改包器、DTS 检查器、外发合同验证器、真实 runtime wrapper、DML 生成器、runtime JAR 和 `assets/cases/`。
- 分发前运行资产校验并检查实际成员；不能只信目录清单。

## 回归命令

```bash
python3 scripts/iscb_skill_validator.py audit-skill
python3 scripts/iscb_skill_validator.py audit-examples
python3 scripts/iscb_skill_validator.py audit-curated-cases
python3 scripts/iscb_skill_validator.py runtime-selftest
python3 scripts/iscb_skill_validator.py audit-bundle
python3 scripts/iscb_skill_validator.py check-script --mode mapping --stdin
python3 scripts/iscb_skill_validator.py check-script --mode platform --stdin
python3 scripts/check_dts_multiselect_cache.py <dts-or-zip> ...
python3 scripts/check_dts_sql_dialect.py --dialect sqlserver-legacy <dts-or-zip> ...
python3 scripts/analyze_service_flow.py <dts-or-zip> --flow <exact-number> --format json
python3 scripts/patch_service_flow.py snapshot --baseline <dts> --flow <exact-number>
python3 scripts/patch_service_flow.py inspect --baseline <dts> --manifest <patch.json>
python3 scripts/validate_outbound_contract.py --contract <contract.json> --payload <payload.json> --provenance <provenance.json> --require-real-provenance
python3 -m unittest discover -s scripts/tests -p 'test_*.py'
```

修改 runtime harness、主规则或重要示例后必须运行 `runtime-selftest`；修改 Markdown 中脚本示例后运行 `audit-examples`；主规则、reference、cases 或 validator 变化最终运行 `audit-bundle`。

## Runtime Java 基线

- wrapper 固定以 Java 8 为最低基线，产物必须是 class major 52。JDK 8 使用 `-source 8 -target 8`，JDK 9+ 使用 `--release 8`。
- runtime 缓存必须包含目标 release 并校验已编译 class major；旧的高版本字节码不得被复用。
- runtime 变更提交前，在真实 JDK 8 和 JDK 17 下分别使用干净临时缓存运行 `runtime-selftest` 与 `audit-bundle`，并用 `javap -verbose` 确认 major 52。
- 本地 wrapper/bundle 回归只能报告本地验证层级；目标苍穹版本的资源、流程与平台运行需另行验收。
