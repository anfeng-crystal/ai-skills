# Regression Playbook

> Migrated from `kingdee-unit-test/examples\regression-cases.md`; the bad literal backslash path is intentionally normalized in this skill.

## RC-2605-01 - BizLogic double-write drift

Trigger when a new BizLogic class exists but the original Flow method still keeps the old implementation.

Expected block:

```text
[阻断] 重构未完成：发现 BizLogic 新文件，但 Flow 原方法体未被改写为谦卑形式
```

## RC-2605-02 - ResManager.loadKDString moved into BizLogic

Trigger when BizLogic imports or calls `ResManager.loadKDString`.

Expected block:

```text
[阻断] BizLogic 不得 import ResManager
```

## RC-2605-03 - Illegal cross-product utility import

Trigger when code from one product line imports utility classes from another product line and the pair is not allowed by `cross-module-allowed.json`.

Expected warning:

```text
[P3 告警] 跨产品线依赖
```

## RC-2605-04 - Operation-code string literal drift

Trigger when code replaces operation constants or enums with literals such as `"audit"`, `"unaudit"`, `"submit"`, or `"unsubmit"` around code fields like `operateKey`, `billStatus`, `billType`, `status`, or `type`.

Expected block:

```text
[阻断] 操作码字面值检测命中
```

## RC-2605-05 - Pure delegation extracted as BizLogic

Trigger when a method with no business branch and only a one-line helper delegation is extracted into a BizLogic wrapper or receives a low-value test.

Expected block:

```text
[阻断] 过度工程化
```

## RC-2605-06 - Deprecated platform API

Trigger when generated or reviewed code calls an API listed in `deprecated-api-blacklist.md`.

Expected warning:

```text
[P4 禁止] 调用了 @Deprecated 方法
```

## RC-2605-07 - Mockito wildcard import or fake assertion

Trigger when tests contain wildcard Mockito imports, `assertTrue(true)`, or self-comparison assertions.

Expected block:

```text
[阻断] 测试代码质量门控失败
```

## Maintenance

- Append new cases instead of deleting existing ones.
- Each case should include example code, trigger rule, and expected output.
- After a major rule update, replay all cases against the current guidance.
