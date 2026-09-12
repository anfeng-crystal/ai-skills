# 单测生成：项目测试框架与版本适配

先读取目标工程的测试依赖、基类实现、已有通过用例和质量规则。以下 `SvcUnitTest*` 是条件化项目 profile，未取得可将其认定为所有苍穹版本官方统一框架的依据。只在目标项目确实提供相应类和钩子时套用；其他项目沿用其已确认的 JUnit/Mockito 与测试基类合同，不为匹配此表新增不存在的依赖。

## 一、测试基类匹配

项目确认提供 `kd.bos.svc.unittest.util` 下述类且签名匹配时，可按被测类选择；继承是否带泛型、钩子返回值均以实际基类为准：

| 被测类 | 测试基类 | 被测对象创建位置 |
|---|---|---|
| `AbstractFormPlugin` | `SvcUnitTestPluginAbstract` | `initPlugin()` |
| `AbstractListPlugin` | `SvcUnitTestListPluginAbstract` | `initPlugin()` |
| `AbstractReportFormPlugin` | `SvcUnitTestReportPluginAbstract` | `initPlugin()` |
| 其他(Service/工具类/Operate 等) | `SvcUnitTestAbstract` | `setUpAfter()` |

## 二、生命周期钩子（仅适用于上述已确认 profile）

已确认由父类负责初始化/释放时，使用其扩展钩子，避免覆盖框架生命周期。普通 JUnit Jupiter 项目可使用实际框架支持的 `@BeforeEach/@AfterEach` 等生命周期；这些注解不是苍穹平台禁用 API。

| 钩子 | 时机 | 用途 | 禁忌 |
|---|---|---|---|
| `initPlugin()` | setUp 中(仅插件基类) | 创建插件实例,返回 `IFormPlugin` | 普通类无此钩子 |
| `setUpAfter()` | 框架 setUp 与 LogFactory mock 之后 | 创建 mock、被测对象、打开 MockedStatic | 字段声明处不得初始化 mock / new 对象 |
| `setDownBefore()` | tearDown 之前 | **必须关闭 MockedStatic** | 遗漏会泄漏并污染后续用例 |

## 三、MockedStatic 管理

- 在上述 profile 的 `setUpAfter()` 创建、`setDownBefore()` 关闭；其他框架使用其生命周期或 try-with-resources：
  ```java
  // setUpAfter:
  rcMock = mockStatic(RequestContext.class);
  rcMock.when(RequestContext::get).thenReturn(ctx);
  // setDownBefore:
  if (rcMock != null) { rcMock.close(); rcMock = null; }
  ```
- 同一类同一时刻只能有一个活跃 MockedStatic 实例。
- 重载解析有歧义时，使用与真实参数类型匹配的 matcher，如 `anyCollection()`/`anyMap()`/`any(X.class)`；不能把任何裸 `any()` 都称为必然编译失败。
- 需在 mock 生效期触发类加载时,用 try-with-resources 包住 `new TargetClass()`。

## 四、高频陷阱速查

| 现象 | 待核实的常见原因 | 规则 |
|---|---|---|
| `NoClassDefFoundError: LogFactory` | 缺少依赖或类初始化失败；某些项目基类也要求先建立静态 mock | 先查首个异常及测试依赖；仅对已确认初始化顺序的 profile 将对象创建放 `setUpAfter()`，不把移动 new 当通用修复 |
| `NPE` at `RequestContext.get()` | CI 无上下文 | mock RequestContext + 关闭 |
| `NPE` at `ResManager.loadKDString()` | 权限/多语言未 mock | mockStatic ResManager;**varargs 重载按实际参数个数逐一注册**(3 参/4 参都要) |
| `UnfinishedStubbingException` | `when(x).thenReturn(mock(Y))` 内联触发类加载冲突 | 先建 mock 变量再传入 |
| `thenReturn(String)` 不匹配 `LocaleString` | 类型不符 | 用 `new LocaleString("...")` |
| 泛型返回值编译报错 | 类型擦除 | 改 `doReturn().when()` |
| `MockitoException: already registered` | 同类 MockedStatic 嵌套 | 同类同时只一个活跃 |
| `UnnecessaryStubbingException` | stub 未被使用或测试未走预期分支 | 先核对分支并删除无用 stub；确有共享设置需求时仅对必要 stub 使用项目版本支持的 lenient，不默认把整类 strictness 改为 LENIENT |
| `when(void 方法)` 报错 | void 不能 thenReturn | `doNothing().when(mock).method(args)` |
| `anyString()` 不匹配 null | 默认不匹配 null | `nullable(String.class)` |
| 内部 `new XxxBinder()` NPE | 内部 new 未拦截 | `mockConstruction(XxxBinder.class)` |

补充经过静态核对、且不降低现有基类约束的陷阱：

| 现象 | 根因 | 处理 |
|---|---|---|
| `RequestContext.get()` 已 mock，但静态便捷方法仍返回 0/null | 实例入口和静态入口是两条调用路径 | 按源码实际调用分别 stub，并在 teardown 关闭静态 mock |
| 时间相关用例跨日或跨时区偶发失败 | 直接读取当前日期/时间 | 冻结源码实际使用的时钟入口；恢复真实方法并限定静态 mock 生命周期 |
| JUnit 4 `@Test(timeout=...)` 下静态 mock 失效 | timeout 在另一线程运行测试 | 不在方法注解设置 timeout；交由 Gradle/测试任务控制 |
| `DynamicObject` 空值断言与运行结果不符 | 类型 getter 可能转换为默认值，`getDate` 等仍可为 null | 先核对项目 SDK/现有测试，再分别覆盖缺字段、显式 null 和默认值 |
| 分录只有一行时通过，多行时失败 | 测试只构造单对象或未验证集合 `size/isEmpty/顺序` | 覆盖 0/1/多行及重复/顺序分支，使用项目已有 DynamicObject 构造器 |
| 私有方法靠反射单测后仍遗漏公共行为 | 测试绑定实现细节 | 经公共入口验证输出/副作用；不可达逻辑先提出可测试性重构 |
| 测试 PASS 但断言未执行 | catch 后吞异常或提前 return | 让异常传播；每个测试必须到达有效 assert/verify |
| 同一静态方法按不同参数返回不同对象 | 单一宽泛 stub 掩盖分支 | 使用精确 matcher 或 `thenAnswer`，并验证关键参数 |

只从目标源码 import、现有 BaseTest 和项目既有通过用例推断平台 mock。不要凭通用表自动添加未使用的 Helper，也不要将候选材料中的 JUnit 4 生命周期覆盖到项目既有 JUnit 5/苍穹测试基类。

## 五、覆盖率、项目规范与红线

- 覆盖率阈值取项目已批准规则；行 90% / 分支 80% 只在项目已采用时作为门禁，不宣称是金蝶官方所有项目统一标准。
- 按真实行为覆盖正常、空值边界、异常和关键分支；不为无业务行为的方法机械凑测试。
- 仅要求生成测试时不修改被测源码；已授权产品修复按主任务范围修复并验证。
- 项目明确要求父类钩子、禁用某些注解、AssertJ 或禁止字段期初始化时继续遵守。项目没有这些约束时，按已确认测试框架选择，不能把合法的 `@Mock`、`@ExtendWith` 或有意义的 `assertEquals` 直接判错。假断言、吞异常、资源泄漏仍不合格。
- Java 语言级别、构建 JDK 和目标运行 JDK 分别核对。官方公告：苍穹 8.0 支持 JDK 17 并兼容 JDK 8，9.0 及以上最低 JDK 17；不能对所有版本强制 Java 8。旧项目若仍承诺 Java 8 字节码或源码兼容，继续禁止不兼容语法/API，不因公告自动升级构建或运行环境。

生成前读取 `testcase-completeness.md`，先列出行为与分支矩阵，再生成代码；生成后逐项回填执行结果和阻塞原因。

## 来源与适用范围

- 金蝶官方[苍穹 V8.0 及以上 JDK 调整公告](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=218024718795190528&id=767850225473553920&type=Knowledge&productLineId=29&lang=zh-CN)，更新于 2026-03-17：说明目标运行版本，不替代具体项目的编译合同。
- 金蝶官方[Java 插件测试指引](https://vip.kingdee.com/knowledge/specialDetail/218022218066869248?category=243671990643472128&id=224183135616136448&type=Knowledge&productLineId=29&lang=zh-CN)，更新于 2024-02-28：是依赖、部署和注册插件的场景示例，没有确立这里的 SvcUnitTest 基类/90%-80%/断言库为全产品标准；部署例子也不构成执行授权。
- [JUnit 5.12.0 用户指南](https://docs.junit.org/5.12.0/user-guide/#writing-tests-test-instance-lifecycle) 与 [Mockito 5.16.0 UnnecessaryStubbingException](https://javadoc.io/static/org.mockito/mockito-core/5.16.0/org.mockito/org/mockito/exceptions/misusing/UnnecessaryStubbingException.html)：用于核对通用框架语义，不意味着需要升级目标项目依赖。
