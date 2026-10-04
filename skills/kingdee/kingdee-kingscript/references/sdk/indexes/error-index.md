# SDK 报错索引

这个文件用于从“报错现象”反查最可能相关的 SDK 卡片、示例和第一排查入口。

## 使用方式

- 用户贴出了具体报错文本时，先按关键词匹配本索引。
- 用户没有贴栈信息，只描述“找不到包”“类型不对”“调试起不来”时，也先从这里缩小范围。
- 先定位问题落在哪一层：导入与打包、运行时上下文、序列化、查询过滤、数值/日期、页面生命周期。

## 高频报错条目

### 1. 依赖包无法识别 / 找不到模块

- 常见现象
  - `Cannot find module '@cosmic/bos-core/...'`
  - `找不到包 kd/bos/...`
  - import 路径提示不存在
- 优先排查
  - import 路径是否与模板中的标准路径一致
  - 当前脚本是不是用了错误的插件基类
  - 安装的 skill 是否包含 `references/` 和平台入口文件
  - `this.trace` 在 Java 可见但脚本声明未公开时，核真实日志接口和输出去向，见[脚本日志](../../examples/plugins/插件示例/表单插件.md#52-trace)
- 推荐先看
  - [references/templates/index.md](../../templates/index.md)
  - [AbstractFormPlugin.md](../classes/AbstractFormPlugin.md)
  - [AbstractBillPlugIn.md](../classes/AbstractBillPlugIn.md)
  - [package-index.md](package-index.md)

### 2. 引擎未初始化 / 插件未生效 / 页面打开后没有任何反应

- 常见现象
  - 脚本加载了但事件不触发
  - 页面打开正常，插件方法完全没有进入
  - 控制台提示脚本入口异常或实例未导出
- 优先排查
  - 文件末尾是否正确 `export { plugin }`
  - 实例名是否和模板保持一致
  - `onCreateDynamicUIMetas` 官方注明未触发；Java 方法存在或自行声明同名 TS 方法不证明事件派发，动态字段应核前端配置与后台模型的配套路线，见[事件可用性](../../examples/plugins/插件示例/表单插件.md#47-oncreatedynamicuimetas)
  - `customPrintDataObject` 的事件类型存在不代表脚本基类公开该回调；已核 Java 入口标为废弃/内部使用，打印扩展应核正式打印体系，见[打印数据路线](../../examples/plugins/插件示例/表单插件.md#42-customprintdataobject)
  - 插件挂载类型是否和页面/操作场景一致
  - 页面定时回调是大写 `TimerElapsed`，并需宿主先开启；Java 可见的开启方法不自动等于脚本可见，见[定时事件](../../examples/plugins/插件示例/表单插件.md#51-timerelapsed)
- 推荐先看
  - [references/templates/form-plugin-template.md](../../templates/form-plugin-template.md)
  - [references/templates/bill-plugin-template.md](../../templates/bill-plugin-template.md)
  - [references/templates/list-plugin-template.md](../../templates/list-plugin-template.md)
  - [plugin-index.md](plugin-index.md)

### 3. 事件参数类型不匹配 / `any` 用错位置

- 常见现象
  - `类型“X”不可分配给类型“Y”`
  - 事件参数上预期的方法不存在，或运行时对象明显不对
  - 为了先通过类型检查把事件参数写成 `any`，后续 API 调用仍然报错
- 优先排查
  - 先确认当前插件基类是 `AbstractFormPlugin`、`AbstractBillPlugIn` 还是 `AbstractListPlugin`
  - 再确认当前生命周期对应的事件参数类，不把不同插件体系里的同名事件签名混用
  - 声明层已有明确类型时直接用明确类型；只有声明层本身就是通用类型时才保持通用，不用 `any` 抹平
  - 数据权限事件是 `beforeCheckDataPermission`，参数为 `BeforeDoCheckDataPermissionArgs`；取消与跳过检查是独立标志，见[参数卡](../classes/BeforeDoCheckDataPermissionArgs.md)
  - 如果方法是 `confirmCallBack` 或 `messageBoxClosed`，不要误用 `ClosedCallBackEvent` 或 `BillClosedCallBackEvent`
  - `onGetControl` 的标识为 `getKey()`，返回后台编程模型，不凭 `createCustomControl` 拼前端布局，见[控件模型](../../examples/plugins/插件示例/表单插件.md#48-ongetcontrol)
  - `loadCustomControlMetas` 使用 `getItems()` 返回的 Java List，没有 `getControlMetas/addControlMeta`；任意 JSON 编译通过不证明配置或集合桥接正确，见[控件配置入口](../../examples/plugins/插件示例/表单插件.md#45-loadcustomcontrolmetas)
  - `flexBeforeClosed` 使用 `getFlexKey/getBasedataKey`，没有 `getFlexPropName/getFlexData`；source 模型取值与取消关闭/保存时机分别核验，见[弹性域关闭校验](../../examples/plugins/插件示例/表单插件.md#44-flexbeforeclosed)
  - 水印事件回传 `WaterMark` 对象，文本与样式 setter 属于该对象；构造入口及初始化时机另核，见[水印合同](../../examples/plugins/插件示例/表单插件.md#50-setwatermarkinfo)
- 推荐先看
  - [plugin-index.md](plugin-index.md)
  - [methods-lifecycle.md](methods-lifecycle.md)
  - [AbstractFormPlugin.md](../classes/AbstractFormPlugin.md)
  - [AbstractBillPlugIn.md](../classes/AbstractBillPlugIn.md)
  - [AbstractListPlugin.md](../classes/AbstractListPlugin.md)

### 4. QFilter 类型转换错误 / 过滤条件不生效

- 常见现象
  - `ClassCastException`
  - `类型转换错误`
  - 查询条件写了但结果明显不对
- 优先排查
  - `ParameterSetter.set`、`JSArrayObject` 类转换或 `PolyglotMap` 不可序列化时，区分接口数组与内部 Java 集合：声明为 `QFilter[]` 的外层 filters 使用原生数组，`in` 的内层值使用 Java 集合；`value: any` 不能证明自动深转换
  - `queryOne` 返回第一条拉平数据，无行返回 null；轮询无行时须处理旧显示，过滤唯一性、null 与 0 分开，见[看板查询刷新](../../examples/plugins/插件示例/表单插件-事件拆分/timerElapsed.md)
  - 比较值类型是否和字段真实类型一致
  - 基础资料、组织、枚举字段是否误传成字符串
  - F7 过滤事件里是追加过滤还是覆盖过滤
- 推荐先看
  - [QFilter.md](../classes/QFilter.md)
  - [BeforeF7SelectEvent.md](../classes/BeforeF7SelectEvent.md)
  - [BeforeFilterF7SelectEvent.md](../classes/BeforeFilterF7SelectEvent.md)
  - [beforeF7Select.md](../../examples/plugins/插件示例/基础资料控件-事件拆分/beforeF7Select.md)
  - [beforeFilterF7Select.md](../../examples/plugins/插件示例/基础资料控件-事件拆分/beforeFilterF7Select.md)

### 5. 长整型精度丢失 / 单号或 ID 变形

- 常见现象
  - 大整数尾数被改写
  - 单据 ID、基础资料 ID 变成科学计数法
  - 传输后比对主键失败
- 优先排查
  - 是否把长整型主键直接当普通 `number` 使用
  - 是否在 JSON 序列化前做了字符串保护
  - 前后端传值过程中是否做了隐式数值转换
- 推荐先看
  - [BigDecimal.md](../classes/BigDecimal.md)
  - [SerializationUtils.md](../classes/SerializationUtils.md)
  - [RequestContext.md](../classes/RequestContext.md)

### 6. 序列化 / 反序列化失败

- 常见现象
  - `NotSerializableException`
  - `反序列化失败`
  - 页面回调、任务消息、缓存对象恢复失败
- 优先排查
  - 若异常对象为 `com.oracle.truffle.polyglot.PolyglotMap` 且发生在脚本调用 Java API 入参处，先检查浅转换边界，见 [QFilter.md](../classes/QFilter.md)；不要直接归因为缓存或页面句柄
  - 传递对象是否包含运行时上下文、视图对象或不可序列化句柄
  - 是否把页面对象直接塞进任务消息、缓存或扩展参数
  - 序列化边界是否该改成传主键、字段值或 DTO
- 推荐先看
  - [SerializationUtils.md](../classes/SerializationUtils.md)
  - [CloseCallBack.md](../classes/CloseCallBack.md)
  - [ClosedCallBackEvent.md](../classes/ClosedCallBackEvent.md)

### 7. 关闭回调不触发 / 回调数据为空

- 常见现象
  - 子页面关闭后 `closedCallBack` 或 `billClosedCallBack` 不进
  - `getReturnData()` 返回空
  - 列表打开单据后关闭没有刷新
- 优先排查
  - 打开页面时是否显式设置了回调对象
  - `actionId` 是否前后保持一致
  - 用户是否直接关闭页面导致没有返回有效数据
- 推荐先看
  - [ClosedCallBackEvent.md](../classes/ClosedCallBackEvent.md)
  - [BillClosedCallBackEvent.md](../classes/BillClosedCallBackEvent.md)
  - [closedCallBack.md](../../examples/plugins/插件示例/表单插件-事件拆分/closedCallBack.md)
  - [billClosedCallBack.md](../../examples/plugins/插件示例/列表插件-事件拆分/billClosedCallBack.md)

### 8. 确认框回调不进 / 把消息框回调当成页面关闭回调

- 常见现象
  - `showConfirm` 已经弹出，但 `confirmCallBack` 或 `messageBoxClosed` 没有进入
  - 回调里拿不到 `getResult()`、`getCallBackId()`，或始终分流不到预期分支
  - 把 `ClosedCallBackEvent`、`BillClosedCallBackEvent` 写到了确认框回调方法上
- 优先排查
  - 当前问题属于消息框 / 确认框回调，不是子页面关闭回调
  - `showConfirm` 是否绑定了有效的 `ConfirmCallBackListener`
  - `confirmCallBack` / `messageBoxClosed` 参数是否使用 `MessageBoxClosedEvent`
  - `callBackId` 是否与发起 `showConfirm` 时传入的标识一致；`ConfirmCallBackListener(id, plugin)` 的路由是 `confirmCallBack`
  - 确认后重发保存时，是否按当前金额绑定、消费并在异常路径清理一次许可，是否拒绝旧/重复回调，见[金额确认生命周期](../../examples/plugins/插件示例/表单插件.md#46-messageboxclosed)
- 推荐先看
  - [IFormView.md](../classes/IFormView.md)
  - [MessageBoxClosedEvent.md](../classes/MessageBoxClosedEvent.md)
  - [showMessagesAndConfirmCallback.md](../../examples/plugins/插件示例/表单插件-场景拆分/showMessagesAndConfirmCallback.md)
  - [ClosedCallBackEvent.md](../classes/ClosedCallBackEvent.md)
  - [BillClosedCallBackEvent.md](../classes/BillClosedCallBackEvent.md)

### 9. 字段联动不触发 / propertyChanged 没进

- 常见现象
  - 页面字段改了，但服务端联动没执行
  - `propertyChanged`、`beforePropertyChanged` 不触发
  - 调了 `setCancel(true)` 后后续逻辑消失
- 优先排查
  - 是否在 `beforeFieldPostBack` 中拒绝了已到服务端的字段值进入模型；此取消不是减少浏览器请求的开关，也不保证保存时重传
  - 本事件用 `getKey()` 取得控件标识；`getFieldKey()` 属于 `FieldEdit`。降低纯文本即时更新应核 `FieldEdit.setFireEvtUp(false)` 和真实字段依赖
  - 当前字段是否只是前端展示字段，没有绑定到模型
  - 联动逻辑写在页面事件还是模型事件，层级是否搞混
- 推荐先看
  - [BeforeFieldPostBackEvent.md](../classes/BeforeFieldPostBackEvent.md)
  - [IDataModelChangeListener.md](../classes/IDataModelChangeListener.md)
  - [beforeFieldPostBack.md](../../examples/plugins/插件示例/表单插件-事件拆分/beforeFieldPostBack.md)

### 10. 页面关闭被拦住 / 未保存提示异常

- 常见现象
  - 页面明明没改数据，却一直弹未保存提示
  - 关闭事件中取消和脏检查行为不符合预期
  - 页面释放和关闭拦截逻辑互相干扰
- 优先排查
  - 是否在 `beforeClosed` 中错误设置了 `setCheckDataChange`
  - 是否把所有关闭都当作确认，或在关闭被否决后残留上次回传值；物料选择需确认/取消/X分流，并补齐父页按钮接线
  - 普通按钮若绑定操作，操作先于 `click` 执行；不要让绑定关闭操作抢在确认意图之前关闭页面
  - 基础资料 `setValue` 未抛错不证明引用加载成功；按主键写回后核对模型，部分回填不得报告整批成功或盲目重试
  - 是否把 `beforeClosed` 和 `pageRelease` 的职责写反
  - `pageRelease(e: EventObject)` 必须带参数；正常路径在控件/数据模型释放后触发、页面缓存稍后释放，清理缓存标记不等于删除实际文件，见[释放顺序](../../examples/plugins/插件示例/表单插件.md#49-pagerelease)
  - 是否存在未绑定物理字段导致的脏数据误判
- 推荐先看
  - [BeforeClosedEvent.md](../classes/BeforeClosedEvent.md)
  - [beforeClosed.md](../../examples/plugins/插件示例/表单插件-事件拆分/beforeClosed.md)
  - [pageRelease.md](../../examples/plugins/插件示例/表单插件-事件拆分/pageRelease.md)

### 11. 菜单行索引不存在 / 复制行位置错误

- `ContextMenuClickEvent` 只有菜单来源和菜单项标识，没有 `getRow/getEntryKey`；事件 source 不能当作 `EntryGrid`。
- 在目标菜单已验证派发的前提下，从指定分录控件取当前选择并校验；右键位置不等于选择行。普通分录的下方插行使用已核插入 API 和返回索引，不能把追加说成插入。
- 参见[菜单来源与分录选择](../../examples/plugins/插件示例/表单插件.md#40-contextmenuclick)。

### 12. 自定义事件不分流 / 空批号误合并 / 解析提示掩盖业务错误

- 事件名使用 `CustomEventArgs.getEventName()`，与 `getKey()` 联合路由；字符串载荷按实际控件协议验证。
- 扫码合并须同时匹配物料与批号，空批号不作为通配符；核实物料编码关联字段是否确实随物料更新。
- 将输入解析与查询、算术、字段写入分开；不能把后者的异常全部改称解析失败。地图先校验完整字段，保留合法 0 坐标。
- 参见[扫码与地图载荷](../../examples/plugins/插件示例/表单插件.md#41-customevent)。

### 13. 客户端回调不执行 JS / 设备日志没有返回值

- `addClientCallBack` 的参数是名称及可选数字延时，不是脚本和回调 ID。`ClientCallBackEvent` 用 `getName/getParam`，没有 `getCallBackId/getReturnData`。
- 设备采集需要前端代码及真实通道：自定义控件 `setData → props.data`、`model.invoke → customEvent`。控件 key 与方案 ID 不混用；辅助日志失败不应变成业务失败。
- 参见[客户端回调与配套设备控件](../../examples/plugins/插件示例/表单插件.md#39-clientcallback)。

### 14. 审核后下推误报成功 / 界面回调同步写库

- `afterDoOperation` 无事务保护且不论成功失败都可触发。先检查结果；界面负责提示或派发，实际转换保存由独立业务执行路径负责。
- `JobForm.dispatch` 返回不代表任务受理或目标保存；任务脚本ID与插件类型须真实配置。Java枚举存在不证明脚本模块导出，不能靠数字或类型断言绕过。
- `PushArgs` 使用源/目标/选中行列表构造及 `setRuleId`。区分 `push` 与 `pushAndSave`、目标ID与整批成功；部分保存后先核查，不自动重试。
- 参见[界面结果、派发与后台下推](../../examples/plugins/插件示例/表单插件.md#35-afterdooperation)。

### 15. 自定义公式不显示 / 运行时找不到函数 / 参数校验失败仍返回

- `IFuncParamInputFormPlugin.getFuncInfo/getDesignerParameter` 读取父容器上下文，不是注册工厂；自定义函数实现 `IFormulaFunctions`，设计器和运行引擎分别注册。
- 参数容器可能在 `checkSetting(false)` 后继续调用 `getSetting`，后者也要拒绝非法配置；返回表达式不等于自动持久化任意JSON。
- 参见[公式注册与跨单据参数页](../../examples/plugins/插件示例/公式平台插件.md)。
- 账龄区间先校验原始 JSON 数字词法，避免解析舍入后误认整数；库存每个已填阈值都须验证，不能只在上下限同填时校验。保留完整配置 payload，但返回函数表达式；参见[账龄与库存参数](../../examples/plugins/插件示例/函数参数配置.md)。

### 16. MobTable 行展开类型异常 / 格式信息空指针

- `MobTableHandleResult` 的行列表需要真实 `MobTableRowData`，不能放入 `HashMap`；裸行对象也不能代替带列槽位的模板。
- 新结果的 `fmtInfo` 可能为空；复用已核的原生打包/格式能力，保持额外列、特殊单元格和上游数据源语义，不只重建几项字段。
- 参见[移动表格列与打包合同](../../examples/plugins/插件示例/移动表单-场景拆分/configureMobTableColumnsAndPackageData.md)。

### 17. 转换按数量拆分多生成 / 卡片索引重复

- `as number` 不会实施运行时整数校验；一物一卡先验证精确正整数，拒绝小数、零/负数和越界，不截断数量。
- 新主卡片索引从现有最大索引之后分配；追加方法不重新编号。完整数据包克隆不自动分摊金额、关联和反写量，不能冒称保存/反写已通过。
- 参见[转换后按数量拆分](../../examples/plugins/插件示例/转换插件-场景拆分/splitTargetRowsAfterConvert.md)。

### 18. 下推过滤与选单不一致 / 取消建链仍生成目标

- 自定义表达式是允许条件，需与查询 QFilter 等价；列表外层按 AND 组合。多插件 setter 覆盖但 QFilter 追加，须保留并分组组合旧表达式。
- 锁定案例核对 `lockstatus`，不能用审核/禁用字段代替。建链取消仅跳过本次结果集合的关联填充与该次 `afterCreateLink`，不撤销目标或清空既有关系；不取消时保留前置插件的 cancel。
- 参见[过滤与建链合同](../../examples/plugins/插件示例/转换插件-场景拆分/appendPushFiltersAndLinkControl.md)。

### 19. 引入后事件误当保存成功 / getDataEntities 不存在

- `afterImportData(ImportDataEventArgs)` 在本单填写完毕、保存前触发；源 Map 通过 `getSourceData` 读取，当前实体通过模型读取，事件没有 `getDataEntities`。
- 不将批量逐单事件当整批提交通知；入口开关可能关闭派发。补链保留已有非空关联，保存与反写另按实际规则验证。
- 参见[引入时机及参数](../../examples/plugins/插件示例/表单插件.md#21-afterimportdata)。

### 20. 引入前方法不存在 / 标错后仍继续 / 误以为逐行跳过

- `BeforeImportDataEventArgs` 没有 `getDataEntities/addErrorInfo`，使用当前单原始 Map；模型此时尚未填写当前源值。
- 原因消息不自动取消，须设置 `setCancel(true)`；行号只是错误定位，普通转换消费者取消当前整单，不保留所谓其余合法分录。通过时不覆盖前置取消。
- 基础资料对象、原始 `id`、编码与缓存键分别核验，不能比较对象字符串。币别未就绪不得掩盖金额校验。
- 参见[本单引入前校验](../../examples/plugins/插件示例/表单插件.md#20-beforeimportdata)。

### 21. 取到的采购价不是最新 / 登录组织误作采购组织

- 三参 `queryOne` 实际存在，但无排序取第一条；使用已核实的价格排序及有效范围配合五参 `query(..., orderBy, 1)`，不虚构时间字段。
- 采购组织来自真实单据合同；单选基础资料取真实主键，不把登录组织或整个动态对象当过滤值。缺必要范围时停止取价，不省略过滤。
- 保留查询、单价、数量乘单价和税率回填；空价格/数量不计成功，部分缺价与已填行同时反馈。字段、币种和权限未核实的示例使用明确接入合同。
- 参见[引入后取价核心](../../examples/plugins/插件示例/表单插件.md#21-afterimportdata)。

### 22. 批次初始化没有 getDataEntity / 默认日期被仓库查询跳过

- `InitImportDataEventArgs` 使用本批 `getSourceDataList()`，既有单头/分录为原始 Map；构造器复制外层 List，不通过改List成员控制原导入记录。
- 默认仓库按真实业务组织和默认条件确认唯一结果，按实际导入格式补值；只补null/缺键，保留已有编码、Map、零值和空串。日期独立于仓库和分录存在性。
- 参见[批次默认值核心](../../examples/plugins/插件示例/表单插件.md#19-initimportdata)。

### 23. 基础资料匹配事件单值API不存在 / 同名数据误取第一条

- `QueryImportBasedataEventArgs.getSearchResult()` 返回批量 Map，字段/文本在 `BasedataItem` 上，值为 Java List；没有事件级 `getImportValue/setBaseDataPkId/addErrorInfo`。
- 目标消费者先取走默认唯一项；未匹配/多匹配项才可干预。四策略按优先级判断唯一性，多结果不能取第一条；实际组织、分配、版本和权限需显式保留。
- 不修改作为 Map key 的 BasedataItem，也不把批量缓存当每行独立查询；按行组合条件交适用的行级事件。
- 参见[客户批量匹配核心](../../examples/plugins/插件示例/表单插件.md#25-queryimportbasedata)。

### 24. loadData 中读到旧模型 / 调super后仍未加载 / 行颜色API不存在

- `loadData(LoadDataEventArgs)` 用于提供自定义数据包，发生在默认读库前；通过 `getPkId/getDataEntity/setDataEntity` 协作，不把父类空实现当装载器。补充本次完整模型改用 `afterLoadData(EventObject)`。
- 辅助字段是否保存由元数据和保存路径决定，事件名不提供非持久化保证。状态颜色使用绑定后的 `EntryGrid.setCellStyle(List<CellStyle>)`，不能调用不存在的view方法。
- 订单单头ID去重查询和分录金额逐行求和分开处理；范围不足不做无范围查询，差额独立计算。
- 参见[装载合同与订单辅助展示](../../examples/plugins/插件示例/表单插件.md#22-loaddata)。

### 25. setEntityType不存在 / 换主实体后布局未切换

- 使用 `GetEntityTypeEventArgs.getOriginalEntityType/getNewEntityType/setNewEntityType(MainEntityType)`；不能传字符串，也不能直接改共享原类型。复制前序结果再扩展以保留已有修改。
- 模型主实体按首次读取缓存，布局按formId加载；该事件不是通用业务页面路由器。四业务入口用已核formId和ADDNEW打开对应页面，保留目标权限与未保存状态。
- 参见[主实体扩展与四业务入口](../../examples/plugins/插件示例/表单插件.md#24-getentitytype)。

### 26. 分录引入把日志当数据 / 缺数量仍删行 / 不同批次误合并

- `beforeImportEntry` 的待引入行在 `getSource()` 的 Map/List；`getEntryDataMap()` 对应日志包装。行是 ImportEntryData，其data为原始JSONObject；没有 `getEntryData/addErrorInfo`，Java List不能splice。
- 只在已核新增模式、本批完整业务键相同且数量/价格齐全时合并；缺条件保留原行。数量、2位金额与备注写回成功后才删除重复行，不合并更新匹配ID、不跨批缓存已消费对象。
- 非法行日志、失败计数与移除分开处理；合并不是失败，局部结构投影不证明TS模块导出或真实桥接。
- 参见[分录引入前校验与合并](../../examples/plugins/插件示例/表单插件.md#26-beforeimportentry)。

### 27. 复制后清理未生效 / 新增状态误排除复制 / 普通备注被清空

- `afterCopyData(EventObject)` 在目标复制初始化后派发，父接口默认空实现；super不执行复制。新增状态带真实复制入口参数可进入复制路径，不能按ADDNEW一概排除。
- 按元数据允许复制及真实字段语义清审批、引用、执行字段；初始状态值、业务日期和关联是否可清需单据配置。仅去掉已识别系统历史后缀，保留业务备注。
- 目标引擎把全局Date绑定ScriptDate；保留new Date()，不能编造JavaDate模块。模型清理不证明保存或流程删除。
- 参见[复制初始化与业务清理](../../examples/plugins/插件示例/表单插件.md#23-aftercopydata)。

### 28. 供应商选择返回对象没有getPkValue / 换供应商后残留旧联系信息

- 标准列表使用ListShowParameter和显式lookup/单多选；返回ListSelectedRowCollection，逐行getPrimaryKeyValue，不能把集合当动态对象。保留默认验权，不照搬setHasRight(true)。
- 回调先核action、类型、取消/清空/条数及当前范围，再按真实默认联系/银行规则查询唯一详情；queryOne拉平首条不证明默认项。五项联系字段为null时显式清旧值。
- 多选逐行创建使用真实返回索引，分录创建返回null/非法索引必须失败，不能退回写单头。查询先完成，基础资料引用加载须核实，部分写入不报全批成功、不盲重试追加。
- 参见[供应商选择与回填](../../examples/plugins/插件示例/表单插件.md#27-closedcallback)。

### 29. 确认后删除了另一行 / 删除被取消却报成功 / 整单删除返回值类型错误

- 提示时绑定页面、单据版本、稳定行身份和有序快照；回调不重新以当前焦点决定删除行。`deleteEntryRow`返回void且可被前置事件取消，须核删除后集合，不能调用后立即报成功。
- 整单走已核标准删除操作与原权限/校验/完成配置。`DeleteServiceHelper.delete`不是OperationResult；实例`deleteOperate`也不等同完整表单操作链。
- 标准删除可能再次异步确认，option token在回调重发时恢复，到beforeDoOperation才消费。固定contentChange、平台Cancel残留和其他提示覆盖须联测；不能套用同步保存的finally清理或宣称全面反重放。
- 参见[删除对象绑定与标准操作](../../examples/plugins/插件示例/表单插件.md#28-confirmcallback)。

### 30. preOpenForm读不到view / 无权限仍标大额 / 不同币种共用阈值

- 从事件source取得FormShowParameter，单据PK使用BillShowParameter；真实setCancel/setCancelMessage可用，本路径尚未绑定view，且早于后续普通页面验权。
- 查询敏感金额前先核项目已有读取范围；大额权限不使用猜测权限表/角色。严格超过同币种同存储单位阈值才进入大额分支，空值/未知配置/异常拒绝，不泄露金额。
- 同一事件按插件顺序复用，最终cancel可被后插件覆盖；本插件保留已有取消。大额提示以formId/PK绑定参数、先清旧再消费，不靠跨实例类字段或提示标记授权。
- 参见[打开前金额与访问规则](../../examples/plugins/插件示例/表单插件.md#29-preopenform)。

### 31. initialize动态按钮重复/无效 / 报价集合没有next / 传了基础资料对象

- initialize是频繁重建的轻量事件；三个采购入口在loadCustomControlMetas用真实BarItemAp配置和Java Map/List新增，注册监听现有Toolbar。ID底层转小写，key须规范且唯一；自定义路由不另配opk。
- query返回DynamicObjectCollection，size/get取DynamicObject后再读价格；基础资料getPkValue并按真实类型无损编码，不能JSON整个对象或把toString当主键合同。
- 保留询价全部当前模型物料、当前行比价、供应商评估及已有经理规则；报价范围、同币种/单位/税、排序/top和目标页接收协议须真实接入。按钮可见性不替代点击时验权。
- 参见[初始化与三采购入口](../../examples/plugins/插件示例/表单插件.md#30-initialize)。

### 32. 绑定重入覆盖人工汇率 / 空金额混入旧本位币合计

- beforeBindData实际接收普通EventObject；整页updateView每次先派发本事件，不是一次初始化门禁。模型initCounter与实体初始化/dirty状态不同，不能按事件名保证修改标志。
- 只对已核允许自动初始化的数据包取业务日期、组织真实本位币和唯一有效汇率；历史、人工、复制/导入保留。同币同单位、换算方向、精度及空金额规则须正式配置。
- 先算全部行再求合计，空原币按已确认0/拒绝规则处理；独占页面guard阻止重入，输入/有序行身份取不可变值快照，写后检查字段精度和联动结果。多次setValue不是事务，部分失败不报完成、不盲重试。
- 参见[绑定前汇率与完整换算](../../examples/plugins/插件示例/表单插件.md#32-beforebinddata)。

### 33. F7丢组织限制 / 字段映射错仍打开 / 分录行点击没有响应

- BasedataEdit事件用addCustomQFilter追加到已有列表过滤；getQFilters不是该事件API。已有取消保留，目标控件先匹配，再校验property字段；缺组织、错映射和范围异常取消选择。
- EntryGrid用addRowClickListener派发entryRowClick；普通click不同。事件row直接作为模型全局行号，repository处理startRowIndex，不自行加页偏移、不重读焦点。
- 多监听共享可变F7事件，后插件可覆盖cancel或过滤；追加条件不能替代平台权限。普通行范围检查之外还需确认实际客户端行映射，树形/子分录不能仅靠EntryGrid的instanceof放行。
- 参见[采购F7与分录监听](../../examples/plugins/插件示例/表单插件.md#31-registerlistener)。

### 34. 特殊角色把整批数据规则放行 / 事件权限项为空 / 选择集合不等于消费范围

- BeforeDoCheckDataPermissionArgs source是FormOperate；已核默认派发未填事件权限项，source字段亦可能经facade调整，必须确认真实消费者最终权限实体/项。
- skip是整体操作选项，可传至后台数据规则分支；没有逐对象skip。列表焦点分支、预构PK数组和共享选择集合需精确核作用域，不以当前模型或单个命中对象决定整批放行。
- 只接项目已批准角色规则；逐一匹配主体/租户、操作、权限项、对象、组织职能、有效期及授权修订。未知、异常、过期、部分命中保留默认；组织0不是全部组织，不缓存旧例外。
- 进入已有cancel/skip保留；其他插件后续可改，false未必撤销旧option。局部校验不能保证整个系统最终验权，更不能替代后台入口权限。
- 参见[既有数据权限例外范围](../../examples/plugins/插件示例/表单插件.md#37-beforecheckdatapermission)。

### 35. 暂存单误启用既有限制字段 / 撤回后仍只读 / 关联解除仍锁行

- afterBindData是服务端绑定后回调，后续仍有权限处理；setEnable会写控件元状态，头字段postBack读取lockControl可先于VIEW/设计锁分支，不能无条件true，也不据此宣称最终权限绕过。
- 每次将当前既有允许状态与本例业务条件取交集，恢复来源须排除本例旧输出并随权限修订更新。C/D发VIEW，A/B恢复合同当前合法页面状态；不固定EDIT、不改业务状态。
- 所有受控行按完整有序身份重算，linkedqty归零只解除关联限制。指令/快照不是事务，客户端合并、多插件和最终验权须联测。
- 参见[绑定后状态叠加与恢复](../../examples/plugins/插件示例/表单插件.md#33-afterbinddata)。

### 36. 空白输入行误拦提交 / 分录汇总口径不等于提交数据包

- beforeDoOperation之后Submit仍清空行、取数据包、处理弹性域及可选预保存；当前模型所有行不自动等于最终保留行。空行判定涉及关键字段/变更状态等，不能用amount为空替代。
- 用真实完整保留行和已结算同币种/单位/税/舍入口径做快照校验，明确null金额与容差；数量>0、单价≥0保留零价。首次复制身份/口径/行数组，末次读取后再检查配置和操作漂移。
- 保留已有取消/消息，不宣称无先前界面动作或阻止所有入口；后台操作校验器仍需独立校验最终数据。缓存全局行读取与分批完整性须分开核。
- 参见[提交数据范围与金额预检](../../examples/plugins/插件示例/表单插件.md#34-beforedooperation)。

### 37. 批填错算全单 / false未撤销前行 / RowItem嵌套后串行

- BeforeBatchFillEntryArgs通过getPredicate/setPredicate干预，不提供getFieldKey/getFillValue/setCancel。真实消费者按过滤索引中焦点之后/分页范围逐单元格predicate后即时setValue；false只跳当前单元格。
- 保留原predicate只调用一次及其异常，快照静态复用RowItem的属性/名称/归属/行/拟写值；不自行重放旧predicate预求整批集合。拟写值还可能经目标字段转换，不能当最终值。
- 数量预检只替换真实目标行，其他行保留现值；完整订单和挂起规则下估价必须有合同。信用同客户/组织/币种/单位核唯一额度，used含本单时只加回已占用值；0不等于无限额。
- 已填行不回滚、界面预估不占用额度；标准QFilter条件与输入/配置取值快照，真实事务及并发控制仍归既有后端。
- 参见[实际批填单元格信用预检](../../examples/plugins/插件示例/表单插件.md#16-beforebatchfillentry)。

### 38. 清空数量后仍有旧金额 / 批量变化误当全部计算完成

- qty/price为空不能直接return保留旧金额；税率未知不等于免税。按明确空值合同同时更新所有派生金额，头合计不混入旧值；0仍是有效数值。
- DecimalProp会按允许空配置将null保留或转0，并按元数据处理精度；先核合同，写差异后读回。单次propertyChanged结束不证明后续规则队列已经稳定。
- isSupportBatchPropChanged只决定当前监听器接收当前字段原ChangeData数组或逐条回调，不把整次导入或跨字段变化合为一批。
- 参见[金额完整重算](../../examples/plugins/插件示例/表单插件.md#2-propertychanged)和[采购批量金额](../../examples/plugins/插件示例/表单插件.md#4-issupportbatchpropchanged)。

### 39. beforeAddRow行数限制从未执行 / 批量新增越过50行

- 目标7.0的BeforeAddRowEventArgs为空，实际新增/插入/复制模型链没有调用该前置事件；不能补造getEntryProp或setCancel。
- 已配置表单增长操作在beforeDoOperation取真实增量和完整范围，以increment <= 50-current校验并保留已有取消。复制/批量按最终消费者的行集合或数量，不统一当1行。
- 后续插件可改计划，直接模型/F7/导入/API也可能绕过表单事件；各实际增长边界及最终保存校验需要同一业务上限，不能以afterAddRow删行冒充前置原子取消。
- 参见[50行上限的实际入口](../../examples/plugins/插件示例/表单插件.md#5-beforeaddrow)。

### 40. createNewData拿到空包 / 自定义空包丢默认值 / 预览号当正式号

- createNewData用于回传完整自定义包，非空结果会跳过默认创建；普通无外部对象路径的起始事件包为空。仅补申请默认值应在afterCreateNewData从模型取采用的包。
- 前缀/业务日期接现有正式编码规则，引用对象按真实元数据加载；不以用户ID代部门，不用时间戳尾数/随机数假造正式号，不提前保存。
- 目标编码插件绑定阶段可能预读；实际CodeRuleOp在onAddValidators正式取号，其事务开始覆写为空。预读不等于保留唯一号，不能声称正式取号与保存原子或无跳号。
- 参见[新建数据包与正式编号](../../examples/plugins/插件示例/表单插件.md#17-createnewdata)。

### 41. 批量删除漏掉关联行 / 全选绕过清空保护 / 取消清空后导入仍继续

- 标准批量删除只派发一次完整行号数组；本地消费者排序但不去重，重复下标可能删除移位后的其它行，必须拒绝重复/越界而非只在校验视角去重。
- 真清空与全选删除走不同前置事件，应复用同一完整身份/两类下游关系与清空状态规则。PK非null不证明已保存，pushstatus样例值不证明正式关联。
- 初始化模式会跳过事件；部分覆盖导入消费者在void清空调用后仍继续增删行。取消清空只约束该次清空，不能冒称整个覆盖已阻止；后监听器和并发关系也不被快照锁住。
- 参见[完整删除集合](../../examples/plugins/插件示例/表单插件.md#7-beforedeleterow)与[清空入口](../../examples/plugins/插件示例/表单插件.md#9-beforedeleteentry)。

### 42. beforeSetItemValue取消无效 / 多选准入漏项 / 客户端ID批填先于过滤

- beforeSetItemValue是编号/ID解析附加过滤，无cancel，getValue不是已选DynamicObject。保留原qFilters并AND追加资格条件；无匹配可清空旧值，不能承诺原值不变。
- F7列表完整回填可在BasedataEdit的BeforeBasedataSetValueListener检查原有序集合、供应商及模式，任一未准入即取消该次回填。AfterF7Select仍可能派发，不证明写入成功。
- 单选控件收到多项也可能先增行；客户端ID路径可先batchFill再解析。本例核既有batchFill关闭且非flex/树/同格多值，配置或身份未知拒绝；其它真实赋值边界和正式保存另核。
- 参见[解析过滤与完整选择准入](../../examples/plugins/插件示例/表单插件.md#13-beforesetitemvalue)。

### 43. 初始化供应商已换但银行仍属于旧供应商

- 目标7.0初始化setValue先派发initPropertyChanged，再调用setValuePrivate；回调内模型supplier仍旧。用同一头数据包ChangeData.newValue解析本次拟写身份，不能直接当已转换的DynamicObject。
- 初始化头行可为-1，按数据包归属识别而非固定row0；核change.old与模型旧值一致，普通property则读当前已写入模型值。完整更新银行账户对，无默认或清空时清两项。
- 整包加载/下推不保证逐字段派发；初始化异常传播不回滚此前银行写入，后续供应商转换/规则仍可能改变结果，需既有结束或保存校验核归属。
- 参见[初始化拟写值与银行信息](../../examples/plugins/插件示例/表单插件.md#3-initpropertychanged)。

### 44. 审核排除范围与事件数组不一致 / 返回汇总仍被子结果改变

- BeforeOperationArgs的有效列表是实际可变集合，执行器会重新消费；直接clear/addAll却不更新事件缓存数组。插件自身setDataEntities不是事件过滤，真实Java事件setter/isCancel未暴露于随包TS，须明确项目桥接且只保留原对象子集。
- 排除项不自动生成结果；零金额Info跳过、金额缺失Error及负数分开处理，保留既有校验与权限路径。事件子集不等于服务原数组和完整请求范围。
- onReturnOperation之后仍可能mergeSubOpResult，覆盖message、取成功PK交集并追加错误。最终调用方按完整请求无损PK去重，保留多条明细、Info/全局/范围外/冲突/未知；只setMessage也不保证标准批量页显示。
- 参见[审核有效子集](../../examples/plugins/插件示例/操作插件.md#5-setdataentities---设置数据实体数组)与[最终单据级汇总](../../examples/plugins/插件示例/操作插件.md#21-onreturnoperation---返回操作结果)。

### 45. 审计增强拿不到单据 / 多单描述串单 / 新增描述伪造字段变化

- 该执行器未向操作插件基类getDataEntities/getOperationContext注入数据；从AfterOperationArgs成功数组取本次快照，按EntityModifyInfo.keyID唯一匹配，初始化时清缓存。
- 审计前事件逐单派发，后续消费者继续使用原载荷引用。替换参数载荷或修改getFields返回的新列表不能替代原位修改；真实审核状态字段caption追加上下文，保留old/new及载荷身份，不造一条null→描述变化。
- 没有监控变动可能不派发；摘要截断与写日志吞异常不等于最终落库。真实字段、状态对、主键和桥接归属由项目验证，空金额不补0。
- 参见[逐单审计载荷增强](../../examples/plugins/插件示例/操作插件.md#22-beforesaveauditlog---保存审计日志前)。

### 46. 回滚钩子先于事务关闭 / 中途同步成功无账本 / 误删历史外部对象

- 目标异常路径markRollback后、TXHandle.close前调用rollback，提交监听器onRollbacked为空；外层/close失败及前序回滚异常不保证通知插件。回滚参数也不是外部成功清单。
- 每次外部调用前持久登记尝试和幂等键，回执逐笔即时记录；option单键覆盖、缺键抛错，不能当可恢复账本。回滚钩子只提示，独立协调器必须扫描全部尝试。
- 只有最终事务ROLLED_BACK且本attempt外部副作用已确认归属才幂等补偿；UNKNOWN不删除，COMMITTED但外部未确认不虚报完成。恢复锁、票据状态、诊断与逐项继续属于必须实现的项目合同。
- 参见[回滚通知与外部补偿](../../examples/plugins/插件示例/操作插件.md#19-rollbackoperation---回滚通知与外部补偿)。

### 47. 分Sheet从未调用 / 普通对象不能导出 / 数据流复用导致空页

- 目标7.0的NormalExcelExport先调用export，仅null才继续exportWithSheet；列表元素会强制转换为原生ReportExportDataResult。Java类存在不代表随包TS模块可导入，须明确真实Java桥接和KingScript绑定验收。
- 每个Sheet使用独立DataSet；发现维度与明细使用一致过滤，保留原始主键。对Sheet名清洗、截断与不区分大小写去重，异常时释放尚未移交的数据流并保留原错误；不照搬旧版本null占位绕过。
- 参见[多Sheet真实消费者](../../examples/plugins/插件示例/报表表单插件.md#3-exportwithsheet---分-sheet-页导出数据)及[查询导出共用过滤](../../examples/plugins/插件示例/报表查询插件-场景拆分/queryAndExportByFilter.md)。

### 48. 分批依据已变化但每批仍查全量 / 大主键被Number舍入

- queryBatchBy只提供排序的分批依据；query必须读取byBatchInfo().getCurrentBatchRows()并AND追加当前批键集合。依据缓存不是数据库快照，批次不等于页面，也不证明导出完整。
- 公共条件在依据与明细两端一致，每次构造新过滤数组，主键保留原始值；拒绝缺失批次、空键集合、非法或不安全JS数值，不能静默降为全量查询。正整数及每批数量属于本例合同。
- 参见[当前批供应商范围](../../examples/plugins/插件示例/报表表单插件.md#7-querybatchby---返回分批取数依据)。

### 49. 汇总钩子拼写正确仍不生效 / 平均单价算成逐行平均

- 目标方法为setFloatButtomData。同步消费者只对满足条件的Decimal汇总列创建SummaryEvent，读srcSummaryValue并消费formatSummaryValue；事件不是聚合器配置入口，异步合计路径另验。
- 平均价用总金额/总数量，利润率用(总金额-总成本)/总金额；先收齐源值再处理事件，不能依赖列顺序。保留精确十进制，未知/零分母显示未定义，0与空值分开。
- 非空单号计数需取数层逐行CASE贡献列并在数值列汇总；它是非空结果行数，重复单号计多行，不能冒称去重单据数。只改格式不改源汇总值。
- 参见[同步汇总的真实消费](../../examples/plugins/插件示例/报表表单插件.md#28-setfloatbuttomdata---格式化已有合计值)及[排序过滤与汇总场景](../../examples/plugins/插件示例/报表表单插件-场景拆分/enableSortFilterAndSummary.md)。

### 50. 列头漏斗已显示却未过滤 / false仍被平台开启 / disable未能禁止

- 有查询插件且事件sort/filter=true时，7.0先进入插件接管并缓存对应列；须由query实际消费列头条件/排序。默认自动处理应保留事件原值，并满足控件配置、类型、绑定与行数条件。
- 禁止项同时false+disable=true；单独false会被自动路径重算，单独disable压不过接管分支。多插件顺序传递同一列表，最终策略需协调顺序，未知列不覆盖。
- 参见[列头处理责任与禁止策略](../../examples/plugins/插件示例/报表表单插件.md#26-setsortandfilter---设置过滤排序列)。

### 51. 格式化过滤摘要丢掉其他条件 / 只看第一个值误述整个范围

- FormatShowFilterEvent处理完整FilterInfo与整段formatedFilterString，setter替换整串。保留默认摘要，少量追加明确项目合同的说明；同字段getValue只读第一项，先核完整项数与比较符。
- 默认日期范围已按真实起止属性及用户格式生成，不能从控件名猜字段；本机前端是文本节点，不手工HTML实体编码、不拆分号、不写回过滤和权限集合。
- 参见[整段条件摘要](../../examples/plugins/插件示例/报表表单插件.md#13-formatdisplayfilterfield---格式化筛选过滤字段显示)。

### 52. 必填缺失仍查询 / 异步尚未完成却提示成功 / 参数上读取虚构统计

- ReportQueryParam不是QueryEvent，取消由verifyQuery返回false经代理完成；beforeQuery只处理通过校验的前置参数。部门条件必须由真实query消费，用户/管理员/部门映射未知时不能猜字段或回退全量。
- afterQuery可能在异步任务完成前触发，beforeQuery预写message也可能被refresh提前消费。统计仅在本请求已有物化结果成功后生成；CachedDataSet行数、页面datacount、分组数和完整明细数分别核对，耗时须有真实测量。
- 参见[查询取消与数据范围](../../examples/plugins/插件示例/报表表单插件.md#14-beforequery---查询前取数事件)及[完成消息的真实时点](../../examples/plugins/插件示例/报表表单插件.md#15-afterquery---查询取数后事件)。

### 53. 填了过滤Map却没有生效 / 显示两位仍可输入更多小数

- 目标7.0仅cancel=true且filterInfo非空时采用整张自定义Map，不与默认Map合并；已有来源/前插件结构须保留，不能靠不存在的逐项setter设置类型。
- 日期/金额组件由列editor及真实filterItems决定；显示scale不等于筛选输入sc，金额单值比较不自动变成双端区间。复制真实editor，核日期/长日期与精度、原值和实际查询消费。
- 参见[完整列头过滤结构](../../examples/plugins/插件示例/报表表单插件.md#25-beforecreatefilterinfo---过滤信息加载事件)。

### 54. 修改枚举回调仍不生效 / 普通caption对象导致载荷错误

- ComboReportColumn优先于FilterField；来源存在但为空也不回退。只有无元数据枚举来源的普通动态combofield列才走插件，不能以clear覆盖一个未触发的事件。
- 消费者强转ValueMapItem并读String value/LocaleString name。按真实存储值增补，保留同值原项与其他选项、顺序及多语言；不将显示名当实际过滤值。
- 参见[枚举来源与原生项](../../examples/plugins/插件示例/报表表单插件.md#27-getcomboitems---获取下拉值事件)。

### 55. 条件样式强转失败 / 未知预算误标黄 / 合计仍染色

- 使用原生CellStyleRule及foreColor/backgroundColor/degree/condition；目标载荷没有fontWeight，表达式走归一化和expr-eval，不是任意JS。
- 未知预算可被数值比较当成0，x!=null也不是该引擎的JS空值守卫；使用项目真实输出的可比较标记。明细标记须逐规则参与，客户名称“合计”不能代表技术总计，pinned背景覆盖也不会自动清前景。
- 参见[条件样式与数据合同](../../examples/plugins/插件示例/报表表单插件.md#29-setcellstylerules---自定义单元格样式规则)。

### 56. 融合列跨客户 / 小计仍与下一行融合 / 页面融合误当Excel规则

- 真实入口setMergeColums传递共享列名List，幂等增补并保留前插件；每列独立比较相邻值，数组仅比第0项，null可融合，不排序、不聚合、不减少行数。
- 最近三个连续虚拟块的行跨度不是全结果永久合并。nomerge只切断当前行向前融合，下一行仍可接续；客户边界及小计两侧隔离须真实主键/标记、排序和行载荷合同。
- Excel使用exportInitialize与MergeColumnRule独立分组规则，页面列名不自动导出。参见[页面融合与边界](../../examples/plugins/插件示例/报表表单插件.md#31-setmergecolums---自定义报表融合列)。

### 57. 修改总数后提前停止加载 / 返回null仍保留前插件数字

- resetDataCount覆盖响应datacount，不回改rows/模型总数；datacount进入初始虚拟行数与lastRow，0在部分模式会阻止请求。视觉融合不减行数，树叶数、完整明细数、物化缓存数也不自动等于最终分页数。
- Java nullable与TS可选number分别核对。代理保留最后非null值，后null不清前值；无同pageId/ctrlId/queryId最终计数合同时不覆写，不写固定99或假解析器。
- 参见[总数与分页终点合同](../../examples/plugins/插件示例/报表表单插件.md#32-resetdatacount---重设报表总行数)。

### 58. 导出自定义名称丢失 / 多名称只取首项 / 长名称使导出失败

- setExcelName接收初始空的共享List，框架只消费第0项；clear会抹前插件命名，首项空串覆盖默认、null可异常、超过150个UTF-16单元报错。仅空List按本插件合同命名，空白/过长候选保持默认，不能把后续项当备用名。
- 普通及大数据Excel路径追加.xlsx；全局Date在本机脚本中映射ScriptDate，不存在java/util的Date导出不能等同全局日期API不可用。查询月份/组织与运行时当前月分别说明，不混为同一范围。
- 参见[导出命名与消费者边界](../../examples/plugins/插件示例/报表表单插件.md#30-setexcelname---自定义报表导出名称)。

## 使用建议

- 先按报错现象缩小范围，再跳到类卡或示例确认触发边界。
- 没有精确报错文本时，优先根据“在哪个插件类型里出错”回跳到 `plugin-index.md`。
- 如果本索引没有命中，再继续走 `keyword-index.md`、`method-index.md` 和 `manifests/`。

### 59. FilterInfo 追加了条件，方案保存或空值恢复仍不符合预期

- **原因**：报表 `setOtherEntryFilter` 的对象供 `verifyScheme` 校验；方案 `custfilters` 实际序列化当前模型，`commfilters` 另行保存。`addFilterItem` 不是 upsert，同 key 首项仍优先；也不把模型之外的值自动持久化。
- **处理**：产品分类/最小金额先核模型字段与控件责任；标准字段沿平台加载，插件只适配已核实的独占标量。类型缺属性不读写，已有属性的 null 清旧值，0/空串原样；类型属性存在不证明原始 JSON 出现过键。平台权限清理会同时清空 scheme/model，禁止从另存快照复原被清掉的资料。`loadOtherEntryFilter` 位于 `afterSetModelValue` 后，同字段不得重复负责。
- **依据与入口**：见 [报表表单插件第20/21节](../../examples/plugins/插件示例/报表表单插件.md#20-setotherentryfilter---为保存方案的校验补充条件)。本机 7.0 `ReportFilter`、`FilterInfo` 与随包声明；真实方案/元数据/权限尚需项目验证，两个标量不代表完整单据体。

### 60. 报表写了 _link/_display 字段，链接或零数量横线没有生效

- **原因**：`packageData` 按单元格调用，没有 `getDataList()`；假后缀字段不进入真实 dataindex。链接由列 `ln` 与行 `cprop.nolink` 控制，普通数值列消费 `[display, raw]` 的显示槽。
- **处理**：在列创建阶段启用真实单据编号列链接，打包时按真实 `ReportColumn` 取列键；仅增补禁链名单，业务钻取仍核真实主键与权限。原始数量恰零且为已核普通数值数组时，用 `ArrayList` 复制所有槽位，只替换第0项；保留raw、额外槽及前插件定制显示。不把null当零，不改原行，不用宿主数组没有的slice。
- **边界**：报表该构造的 `getColKey()` 可为null、rowIndex为-1；该消费者不读cancel。标量/未知载荷不接管，导出不执行此事件。见 [报表表单插件第17节](../../examples/plugins/插件示例/报表表单插件.md#17-packagedata---单元格数据打包)。

### 61. 树形报表设了任意父子字段或层级，仍未正确展开

- **原因**：目标事件提供 `setTreeReportList/setTreeExpandColId`，没有 `setIdFieldKey/setParentIdFieldKey/setTreeFieldKey/setExpandLevel/setShowExpandAll`。开关不会自动把费用明细聚成组织/部门/员工树；真实数据消费固定 `rowid/pid/isgroupnode`。
- **处理**：沿已有查询与权限合同投影稳定唯一的字符串身份、根pid为 `"0"`、Boolean有下级标记，先保证父键完整、无环与稳定顺序。用已核显示列承载展开控件；全展开/收起走工具栏对应的 `ReportList.expandAllNode()/collapseAllNode()`，本机指令目标固定 `reportlistap`，不泛化到任意控件名。
- **边界**：官方全展开/收起标V7.0.1，本机7.0不代表已核部署补丁；默认两级仍缺独立初始化合同，不能用全展开冒充。页面/真实三层查询/导出未验，见 [报表表单插件第24节](../../examples/plugins/插件示例/报表表单插件.md#24-settreereportlist---树形报表数据与展开操作)。

### 62. 导出状态变空 / 金额没有千分位 / 后续块列与表头不一致

- **原因**：`preProcessExportData` 是带 `NumberFormatProvider` 的三参数逐块回调；首块之后保存本sheet列快照。状态中文会被真实枚举writer再次按编码查表，`amount_str` 没有真实列也不会自动输出。
- **处理**：保留金额原数值、枚举原编码和真实字段显示属性；金额最终精度还取字段/币别，不能只改provider承诺两位。固定递归剔除内部列，文本联系方式幂等屏蔽，短文本不能把首3末4全部泄露。同sheet策略固定，不按块变列；未知列/结果类型不能宣称已脱敏。
- **边界**：超大数字可走文本保护精度；基础资料名称须真实显示属性或查询关联，任意说明行须独立的一次性布局合同。见[分块导出加工](../../examples/plugins/插件示例/报表表单插件.md#22-preprocessexportdata---保留类型的分块导出加工)。

### 63. validatePrefix写日志后仍允许操作 / 批量单据被套用登录组织前缀

- **原因**：`ValidatePrefixArgs.propName` 配置校验消息的取值字段，不验证或分配编号，也没有取消属性。实际业务校验须通过 `onAddValidators` 加入校验器。
- **处理**：保留已有消息字段与平台校验器；单头业务组织逐单取值，预加载组织编码，空组织/空编码/空单号不能作为空前缀放行。使用真实 `ValidationErrorInfo` 的行实体重载定位错误；直接构造的message自行提供完整提示，不会自动经validatePrefix补前缀。
- **边界**：字面前缀通过不保证编号唯一；校验前未分配正式编号的操作不能直接挂用该例，批量事务策略仍由真实操作决定。见[消息前缀与编号校验](../../examples/plugins/插件示例/操作插件.md#23-validateprefix---校验提示前缀与编号规则分工)。

### 64. 常规向导点击不切换 / 直接跨步绕过前置检查

- **原因**：`StepEvent.getValue()` 只给用户请求的目标下标，前端是受控状态；事件没有当前/目标双字段或取消方法。仅按相邻步骤判断还会漏掉直接跨步。
- **处理**：PC常规三步向导按目标累计校验基本信息及明细，通过后以 `Wizard.setWizardCurrentStep(Map)` 明确提交 `currentStep/currentStatus`；失败不发状态指令，保留原步骤。
- **边界**：步骤条状态不等于保存结果；页签向导另走 `Tab.activeTab`。配置须与三步下标和项目字段一致。见[常规向导步骤监听](../../examples/plugins/插件示例/控件.md#wizardstepslistener)。

### 65. TreeView懒加载无孩子 / 普通节点对象落到根 / 空结果不断请求

- **原因**：孩子经 `TreeView.addNodes` 发送，`TreeNodeEvent` 没有 `setChildNodes/getNodeText`。本机序列化使用 `parentid`，前端由 `children` 决定可展开状态；`parentId/isParent` 不能替代真实TreeNode协议。
- **处理**：使用 `TreeNode(parentId,id,text)` 和显式空children；节点ID全树唯一、父键已存在、关系无环。重复追加跳过旧ID而非更新，未知父键不追加。空结果保留再次查询；永久叶化须原完整节点状态再更新，不能只设leaf或伪造父节点。
- **边界**：普通Map不因此必在Java addNodes抛类型转换异常；拖拽事件不证明移动/保存成功，多选单击须核实际版本。见[组织树懒加载](../../examples/plugins/插件示例/控件.md#treenodequerylistener)及[完整合成示例](../../examples/plugins/插件示例/控件-场景拆分/buildTreeViewAndLazyLoadNodes.md)。

### 66. ProgressBar刚轮询就宣布完成 / 101不停 / 完成后无法重启

- **原因**：`onProgress` 收到新建初值0的事件，要求监听器写本次进度；没有 `getTotal()`，处理满额也不等于业务提交成功。PC和移动消费者在100停止，不能用大于100代替。
- **处理**：读取已存在任务的完整快照并核当前任务身份，RUNNING最多99，明确SUCCEEDED才100、停止并按任务去重提示刷新。失败/取消/非法快照停止，不宣布成功。新任务先stop、归零、start；刷新间隔须有效。
- **边界**：示例只消费当前页面状态，未实现真实导入生产者、事务探测或跨节点缓存传播；PageCache.put可用不等于后台任务已接通。见[进度提供与终态](../../examples/plugins/插件示例/控件.md#progresslistener)。

### 67. Search复杂建议无显示 / 旧响应覆盖新词 / 联想快开目标串错

- **原因**：模式1文本建议与模式3分组对象不同；真实入口为 `getComPlexSearchList`，复杂请求text是type/content/time的JSON，返回扁平id/title/subtitle不能被入口renderer消费。
- **处理**：回显原type/content/time，以titles/childs包装并用name/subName显示；空入口保留一组空childs。文本快开限定模式1和当前页面映射，清旧缓存、主键字符串、歧义标签拒绝，保留双来源及其权限合同。
- **边界**：复杂点击另走itemClick；图标、帮助/最近查询和复杂业务打开未交付，不能伪造协议。PC与移动模式不同，多个监听器不自动合并列表。见[搜索模式与载荷](../../examples/plugins/插件示例/控件.md#searchenterlistener)及[双来源快开](../../examples/plugins/插件示例/控件-场景拆分/configureSearchAndQuickFilter.md)。

### 68. 单据体过滤后表头合计仍是全单 / 清空与零匹配混淆

- **原因**：`EntryFilterChangedEvent` 在GridState采用新过滤结果之前派发；遍历全模型或直接读旧过滤状态会用错范围。普通客户端`rk`是原模型行号，不是排序后的屏幕下标。
- **处理**：用本次`reset/rk`与已核模式/页码范围，先完整校验再按原行对象累加BigDecimal，一次写表头。零命中写0，清空只恢复本次页范围，重复键去重，失效或异常输入不写部分合计。金额编辑/初始加载不保证触发此事件。
- **边界**：cancelSum不是取消前端筛选，换事件List不换标准消费者的原引用；有多插件改载荷须明确顺序与引用合同。服务器跨页、树/子分录、TableCache和追加多页需独立适配。见[过滤事件可见合计](../../examples/plugins/插件示例/控件.md#entryfilterchangedlistener)。

### 69. 轻量表格绑定事件没有行 / 按字段Map计算毛利率不生效

- **原因**：DataGrid供数事件初始为空，真实入口是addBindDataListener与getData/setData；每行是按rk、seq、实际列顺序排列的List，隐藏列也占槽，不是字段Map。
- **处理**：已存在供数监听器先完成供数，后置插件按真实列序增补毛利率文本；复制完整行只替目标槽，保持价格BigDecimal、其它槽及postCols。缺列/冲突不接管，异常行保持原样，不能冒称它们已计算。
- **边界**：独立挂本加工器不会查询业务数据；行键唯一、实际字段类型、权限和监听顺序由项目保证。见[已有供数之后加工毛利率](../../examples/plugins/插件示例/控件.md#datagridbinddatalistener)。

### 70. 单据体写颜色字段仍不标红 / 正常后仍保留红色 / 其它行样式被覆盖

- **原因**：entryGridSetRowData处理按编号输入/粘贴的赋值，不是逐行渲染；虚构颜色槽不会变成行样式。setRowBackcolor最终整体覆盖该行style.s，空颜色也不会恢复他人样式。
- **处理**：在实际绑定完成及字段/分录变化后，以同单位BigDecimal比较数量和库存；在明确独占动态行样式的普通完整载入场景，超库存整行红色，否则撤销本例背景色。有其它样式时先统一合成，或用官方界面规则的设置/清除两支配对。
- **边界**：控件键与模型分录键分开；分页、服务器过滤、TableCache、树/子分录、异步重载等需独立适配，局部类型/VM检查不是页面验收。见[赋值事件与库存行样式分工](../../examples/plugins/插件示例/控件.md#entrygridsetrowdatalistener)。

### 71. FilterGrid点击时限定范围不生效 / 追加条件后标准或前插件过滤丢失

- **原因**：点击事件与选前过滤事件不同；真正过滤入口是 `BeforeFilterF7SelectListener.beforeF7Select`。标准qfilters原List在回调后还会追加审核条件，换事件引用会丢后续追加；setCustomQFilters先clear旧集合，传自身也会清空。
- **处理**：在已核目标字段和引用实体的选前回调中，用addCustomQFilter追加本次真实销售员/公司业务范围，保留前插件过滤和cancel；范围缺失取消目标选择，不按用户ID猜销售员、不按上下文组织猜公司。
- **边界**：事件selectedIds在已核路径初始为空，标准回填来自原缓存；保留单多选和回填不代表事件含完整已选项。RefBill提前分支和其它入口另核，helper不替代权限校验。见[FilterGrid范围追加](../../examples/plugins/插件示例/控件.md#filtergridf7clicklistener)。

### 72. DataGrid成本列setVisible(false)失败 / 隐藏后仍有原始成本数据

- **原因**：建列接口、事件、注册名均为复数Columns；事件给共享DataGridColumns List。DataGridColumn.setVisible接收状态字符串，不能套用Boolean；null是默认63，空字符串才是0。
- **处理**：按真实角色/权限结果，仅把目标成本列setVisible("")；允许时保留既有可见性。保留列List、对象、顺序与key，不删列导致已有行槽错位，不猜bos_user.usertype的权限含义。
- **边界**：隐藏列仍进入dataIndex，rows/postCols可能包含原值，展示隐藏不是数据保密。角色切换和重建须应用完整已有规则，不能强设63恢复。见[成本列展示限制](../../examples/plugins/插件示例/控件.md#beforecreatedatagridcolumnlistener)。

### 73. DataGrid取消选择也回填 / getRowData不存在 / 编号和名称错位

- **原因**：DataGridSelectRowEvent是ADD_ROW/CLEAR_ROW/SELECT_ALL/CLEAR_ALL差量动作，不是完整行DynamicObject；CLEAR_ROW仍有载荷，全选/全清无行。真实两参数DataGridSelectedRow的postCols为空，postRowData按当次最终下发postCols顺序排列。
- **处理**：addSelectRowListener注册后，只对ADD_ROW使用已核本次postCols合同解析纯文本编号/名称，保留编号回填和提示；缺列、重复目标、短载荷、格式化数组/未知类型不强转，不getData重触发供数，不把rk当物料主键。
- **边界**：回填表示最近一次单行选择信息；取消/全选不等于当前完整集合，旧合同同长度重排也不能被长度校验发现。客户端文字不授予业务权限。见[差量选择信息回填](../../examples/plugins/插件示例/控件.md#datagridselectrowlistener)。

### 74. FilterGrid关闭提示误称已回填 / cancel后原值被清 / 清空仍提示供应商

- **原因**：关闭事件返回 `ListSelectedRowCollection`，发生在标准加载回填前；cancel分支仍发setF7Value，省略value在当前PC消费者中写undefined。正常分支持有原rows，替换事件引用不改标准消费者。
- **处理**：使用真实CallBack接口和复数注册，保留前插件及标准回填；仅读取本次非清空且名称完整的行快照，不改cancel/values/rows、不造外部字段写回。清空标记与size独立，缺已核isClearFlag桥时不误提示。
- **边界**：提示不是回填/保存成功，前后插件仍可改变结果；清空标记的Java公开方法未由当前TS声明导出，宿主桥须核验。见[关闭回调与标准回填](../../examples/plugins/插件示例/控件.md#filtergridf7closecallbacklistener)。

### 75. 分页第一页提示第二页 / PagerClick漏记翻页 / “预加载”实际跳页

- **原因**：真实事件用getCurrentPageIndex/getPageRows，一基页码不再+1；条数为原始参数，GridState可另受maxPageSize约束。标准EntryGrid.previous/next/setPageIndex不派发该事件，已派发也在绑定前。
- **处理**：只读提示本次事件页码和条数参数，保留跨批次编辑确认；不要通过事件setter导航，也不在观察回调调用next/setPageIndex/setNextpageData伪装预取。
- **边界**：继承追加页路径仍会派发，不把“EntryGrid类仅一处显式fire”扩大成全部路径；无副作用预加载和所有翻页覆盖尚未交付。见[分页事件观察](../../examples/plugins/插件示例/控件.md#pagerclicklistener)。

### 76. 批量关闭仅提示仍丢未保存页 / force触发确认后仍直接关闭

- **原因**：Tab.batchCloseTabs在每个监听器后立即消费名单；普通分支直接发closeWindow，force分支调用子close后仍发批关。getTabKeys返回原List，closeTabs只是替换事件引用，没有cancel；PC门户右键closeTabs是另一事件通道。
- **处理**：只有独占已核自定义批关事件时，替换为空名单并setForce(false)可阻止该消费者直接关闭；提示逐页走原关闭入口，不修改共享原List、不取NoPlugin视图调用业务逻辑。
- **边界**：不能撤回先前监听器的关闭，后续复写会破坏拦截。完整跨页未保存检查与串行确认批关未交付；拦截不等于已检查或关闭。见[批量关闭与未保存保护边界](../../examples/plugins/插件示例/控件.md#tabbatchcloselistener)。


## 77. Slider 单值百分比被当成标量，或把程序设值当作金额已重算

- `SliderEvent.getValue()` 是两槽数组；移动单值模式使用第2槽，不能 `String(整个数组)` 或使用第1槽。双值区间不自动等于折扣。
- 先核真实 `range=false`、控件ID与既有金额/百分比字段；保留百分比除100时四位 `HALF_UP` 再乘原 `BigDecimal` 的公式，不造范围、步长或货币舍入规则。
- 当前移动 `KDSlider` 在 `afterChange` 且异值时回发；`setSliderValue` 只同步显示，不完成金额重算。初始化、仅改原金额和程序设值须接真实入口，不声称每帧或完整实时联动。
- Java `Number[]` 与声明 `number[]` 不是宿主桥验收；实际字段、桥接、保存权限仍须项目验证。
- 见 [SliderListener](../../examples/plugins/插件示例/控件.md#sliderlistener)。


## 78. 日期过滤事件误用控件范围方法，空include又掩盖禁选集合

- `DateClickListener.resetDateFilter` 是 `changeYear` 的年度过滤协议，事件没有 `setMinDate/setMaxDate`；用真实期间起止与focusedYear合成完整年度列表。
- include非null优先，空include仍压住exclude；当前PC空数组不更新，不能表达全禁或清缓存。前include非空按补集合成，前include为null才采用exclude；原列表不就地改，最终清include后发非空exclude。
- 空include、无法验证的前列表、最终空禁选集合不接管；缺实际期间依据不把系统自然月说成会计期间。当前PC年份缓存要求期间稳定，选择面板限制不是保存或权限校验。
- 见 [DateClickListener](../../examples/plugins/插件示例/控件.md#dateclicklistener)。


## 79. ClientAjax 已解析对象被当成响应文本，发送回调与通信失败覆盖被误判

- 当前7.0注册为 `addResponseListner`，事件为 `getMsg(): Object`，不是 `getResponseText`；标准前端已 `response.json()`，对象参数经后端JSON解码为Map，不能无条件再次JSON.parse。
- `success/code/message` 是需项目确认的业务合同，不是SDK固定响应；严格识别布尔值和字符串，成功仅回填原字段，失败或无效载荷保留旧值，不强制数值/字符串转换。
- 标准request没有afterSendRequest派发；网络、HTTP、JSON失败通常拒绝Promise而无接收回调。不能用业务失败分支冒充通信失败通知，不能用回填提示冒充外部业务或保存成功。
- 见 [ResponseListener](../../examples/plugins/插件示例/控件.md#responselistener)。

## 80. ListExpand 重复回调、误报折叠完成或拿行号控制错误明细

- 标准 PC 列表视图已经将 `ListExpandListener` 接入 `AbstractListPlugin.expandClick`，不要再手动注册同一插件；动态表单嵌入列表和定制装配另核。事件只有 pkId/rowIndex，没有展开布尔值或取消接口。
- 当前渲染器可在明细延迟渲染之前通知，缓存重建也通知；销毁不是折叠回执。只把本事件称为明细展示请求，取数、渲染完成另核。
- 已核链路的 rowIndex 承载当前 rowKey，不能拿业务主键、可见下标、旧分页或重排前行号替代。标准页面接线和控件 key 筛选不证明跨页面唯一对象身份。
- 显式控制使用 `autoExpandOrCloseRowDetail`；当前消费者先关再开，展开优先，空数组与closeOther=true可全关。示例 helper 只接调用当时有效行键，校验整数不证明行存在；不能在请求回调中自动反复展开。
- 业务入口、当前行键来源、页面明细配置、折叠/渲染完成反馈和真实KingScript桥仍须确认。见 [ListExpandListener](../../examples/plugins/插件示例/控件.md#listexpandlistener)。
