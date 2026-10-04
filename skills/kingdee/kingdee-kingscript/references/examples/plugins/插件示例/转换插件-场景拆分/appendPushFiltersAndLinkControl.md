# appendPushFiltersAndLinkControl - 下推前过滤与建链控制

## 场景

单据下推时，通过附加允许条件限制来源行。本例沿用官方锁定状态案例：只允许 `lockstatus = 'A'` 的来源单据，锁定状态 `B` 不符合条件；字段及枚举属于该案例，接入其他实体前须核对目标元数据。这里不附加审核、禁用或组织条件。即便允许生成目标单，也可能要求某些场景不要建立源目标关联关系。

## Java 来源

- `kd.bos.plugin.sample.bill.billconvert.bizcase.BeforeBuildRowConditionSample`
- `kd.bos.plugin.sample.bill.billconvert.bizcase.BeforeCreateLinkSample`
- `kd.bos.plugin.sample.bill.billconvert.bizcase.AutoLinkSample`

## 适用入口

- `beforeBuildRowCondition(e: BeforeBuildRowConditionEventArgs): void`
- `beforeCreateLink(e: BeforeCreateLinkEventArgs): void`
- 插件基类：`AbstractConvertPlugIn`

## 完整 Kingscript 示例

```typescript
import { AbstractConvertPlugIn } from "@cosmic/bos-core/kd/bos/entity/botp/plugin";
import {
  BeforeBuildRowConditionEventArgs,
  BeforeCreateLinkEventArgs
} from "@cosmic/bos-core/kd/bos/entity/botp/plugin/args";
import { QCP, QFilter } from "@cosmic/bos-core/kd/bos/orm/query";

/**
 * 追加来源锁定状态允许条件，并按业务开关控制关联记录；不调用保存或下推服务。
 * 目标需具有本例 lockstatus 字段及 A/B 枚举；开关目前为演示值，须接入已确认业务配置。
 */
class AppendPushFiltersAndLinkControlPlugin extends AbstractConvertPlugIn {

  /** 保留既有规则与插件条件；表达式和查询过滤均按 AND 追加同一允许谓词。 */
  beforeBuildRowCondition(e: BeforeBuildRowConditionEventArgs): void {
    if (this.canPushLockedBill()) {
      return;
    }

    const condition = "lockstatus = 'A'";
    const previousExpression = e.getCustFilterExpression();
    e.setCustFilterExpression(previousExpression == null || previousExpression.trim().length === 0
      ? condition : "(" + previousExpression + ") and (" + condition + ")");

    const reason = "来源单据的锁定状态必须为 A（本例未锁定）";
    const previousDesc = e.getCustFilterDesc();
    e.setCustFilterDesc(previousDesc == null || previousDesc.trim().length === 0
      ? reason : previousDesc + "；" + reason);
    e.getCustQFilters().add(new QFilter("lockstatus", QCP.equals, "A"));
  }

  /** 本次结果集合不记录关联时置 true；无需取消时保留其他插件的标志。 */
  beforeCreateLink(e: BeforeCreateLinkEventArgs): void {
    if (this.shouldSkipLink()) {
      e.setCancel(true);
    }
  }

  /** 演示默认限制锁定单据；替换为项目已确认的业务开关。 */
  private canPushLockedBill(): boolean {
    return false;
  }

  /** 演示默认保留关联记录；不代表平台参数。 */
  private shouldSkipLink(): boolean {
    return false;
  }
}

let plugin = new AppendPushFiltersAndLinkControlPlugin();
export { plugin };
```

## 映射说明

- `BeforeBuildRowConditionSample` 的三件套是拒绝原因、内存运算的允许表达式、数据库选单查询的 `QFilter`。表达式为 `true` 才允许该行通过；原因描述不参与条件运算。两种条件需要等价，不能把描述中的“不允许”直接写成允许谓词。
- 规则自身的数据范围默认保留，并与自定义条件同时满足。本例不调用 `setIgnoreRuleFilterPolicy(true)`；该开关会忽略规则自带数据范围，不能当作一般追加操作。
- 同次事件的各插件共享参数对象：表达式/描述的 setter 是替换，QFilter 是累加列表。本例读取旧表达式并加括号后 AND 追加，同时追加 QFilter、保留旧说明；前置插件本来就需保证两层等价，后置插件仍可能覆盖，须按实际注册顺序核验。
- `BeforeCreateLinkSample` 控制本次目标结果集合的关联记录。当前插件只在需要取消时设 `true`；无须取消时不设 `false`，避免清除前置插件的取消决定。多个插件仍须协作，后置插件显式设 `false` 可以覆盖前值。
- `AutoLinkSample` 属于目标单 `AbstractBillPlugIn` 的引入事件：`afterImportData` 在本单字段填写完毕、保存前触发，不是保存成功后补写数据库。完整入口合同见[引入事件](../表单插件.md#21-afterimportdata)。
- 官方[导入补链示例](https://vip.kingdee.com/knowledge/428136719330883840) 按 `srcbilltype/srcbillno/srcentrykey/srcrowseq` 查询来源及行序号，用 `TableDefine` 取得来源表编码，再向空关联集合填写 `_stableid/_sbillid/_sid`；已有非空关联即跳过，不清除或简化已有复杂链。`entryentity`、主实体 `billhead_lk` 与分录 `<entry>_lk` 应以目标元数据为准。来源单号唯一性、行序号冲突及规则/反写仍需另验；这不是可任意字段套用的通用补链实现。

## 注意事项

- 内存与查询条件必须保持语义一致。当前 SDK 的查询消费者把列表中的非空 QFilter 逐项 AND；需要 OR 时应先组成一个 OR 组，再作为列表的一项追加，表达式也保留相同括号。不能把多个 OR 分支分别 add 后期望平台自动 OR。
- `beforeCreateLink` 触发时目标数据包已创建且字段已映射。当前 SDK 的 `FillLinkInfoAction` 在入口读取一次 cancel；`true` 跳过本次结果集合的规则关联子实体填充，也不触发该动作的 `afterCreateLink`，但不会撤销已创建的目标或终止后续转换动作。普通下推作用于本条转换规则结果集合，自动保存分批路径作用于当前批结果集合；不是对每张单或每行分别回调的取消开关。
- 该取消不会清空目标原有 `_lk` 行，也不等于禁止保存或关闭全部反写。反写消费者还读取实际关联行、规则及操作；目标已有关系、其他插件补链、独立简易链路径需分别核对。若需要阻止目标生成，应在已确认的来源行过滤或校验阶段处理。
- 如果你的场景来自“目标单导入后补建来源关系”，那已经不属于纯转换插件时机，应该参考 `AutoLinkSample` 转到目标单插件侧处理。

## 依据与验证边界

- 官方 [beforeBuildRowCondition事件](https://vip.kingdee.com/knowledge/225657245114565120) 明确锁定案例使用 `lockstatus`、数据库与内存双条件及失败描述；通用状态字母不能跨字段套用。
- 官方 [beforeCreateLink事件](https://vip.kingdee.com/knowledge/225704290760032768) 说明事件发生在目标字段填写后、记录来源关联前；本地 `FillLinkInfoAction`、`AbstractConvertAction` 及普通/分批动作链进一步限定取消范围。
- 本地实际 7.0 SDK 的 `ConvertRuleCompiler.compileRowCondition`、`CRConditionCompiler`、`BuildDrawDataFilter` 与 `ConvertPlugInProxy` 支持以上编译、组合和共享参数说明；各构件补丁以目标依赖为准，不以页面更新时间推定。
- TypeScript 声明检查、局部替身验证和字节码取证不等于真实 KingScript 引擎、选单数据库、权限、保存或反写验收。
