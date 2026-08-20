# 单测生成规范(JUnit 5 + Mockito)

本卡片给出苍穹 Java 插件/服务单测的生成口径:测试基类选择、生命周期钩子、MockedStatic 管理、高频陷阱与覆盖率门禁。与本 skill 既有 `test-strategy.md`、`deprecated-api-blacklist.md`、Quality Gates 配合使用。

## 一、测试基类匹配

基类包路径统一 `kd.bos.svc.unittest.util`(继承不加泛型)。按被测类是否继承平台插件基类判定:

| 被测类 | 测试基类 | 被测对象创建位置 |
|---|---|---|
| `AbstractFormPlugin` | `SvcUnitTestPluginAbstract` | `initPlugin()` |
| `AbstractListPlugin` | `SvcUnitTestListPluginAbstract` | `initPlugin()` |
| `AbstractReportFormPlugin` | `SvcUnitTestReportPluginAbstract` | `initPlugin()` |
| 其他(Service/工具类/Operate 等) | `SvcUnitTestAbstract` | `setUpAfter()` |

## 二、生命周期钩子(只用父类钩子)

禁止 `@BeforeEach/@AfterEach/@BeforeAll/@AfterAll` 和自写 `setUp()/tearDown()`。

| 钩子 | 时机 | 用途 | 禁忌 |
|---|---|---|---|
| `initPlugin()` | setUp 中(仅插件基类) | 创建插件实例,返回 `IFormPlugin` | 普通类无此钩子 |
| `setUpAfter()` | 框架 setUp 与 LogFactory mock 之后 | 创建 mock、被测对象、打开 MockedStatic | 字段声明处不得初始化 mock / new 对象 |
| `setDownBefore()` | tearDown 之前 | **必须关闭 MockedStatic** | 遗漏会泄漏并污染后续用例 |

## 三、MockedStatic 管理

- 在 `setUpAfter()` 创建,在 `setDownBefore()` 关闭:
  ```java
  // setUpAfter:
  rcMock = mockStatic(RequestContext.class);
  rcMock.when(RequestContext::get).thenReturn(ctx);
  // setDownBefore:
  if (rcMock != null) { rcMock.close(); rcMock = null; }
  ```
- 同一类同一时刻只能有一个活跃 MockedStatic 实例。
- **重载方法禁用裸 `any()`**(编译失败):用带类型 matcher `anyCollection()`/`anyMap()`/`any(X.class)`。
- 需在 mock 生效期触发类加载时,用 try-with-resources 包住 `new TargetClass()`。

## 四、高频陷阱速查

| 现象 | 原因 | 规则 |
|---|---|---|
| `NoClassDefFoundError: LogFactory` | 字段声明处 new 非常量对象 | 对象创建统一放 `setUpAfter()` |
| `NPE` at `RequestContext.get()` | CI 无上下文 | mock RequestContext + 关闭 |
| `NPE` at `ResManager.loadKDString()` | 权限/多语言未 mock | mockStatic ResManager;**varargs 重载按实际参数个数逐一注册**(3 参/4 参都要) |
| `UnfinishedStubbingException` | `when(x).thenReturn(mock(Y))` 内联触发类加载冲突 | 先建 mock 变量再传入 |
| `thenReturn(String)` 不匹配 `LocaleString` | 类型不符 | 用 `new LocaleString("...")` |
| 泛型返回值编译报错 | 类型擦除 | 改 `doReturn().when()` |
| `MockitoException: already registered` | 同类 MockedStatic 嵌套 | 同类同时只一个活跃 |
| `UnnecessaryStubbingException` | stub 未被使用 | `@MockitoSettings(strictness = LENIENT)` |
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

## 五、覆盖率门禁与红线

- 行覆盖率 ≥ 90%,分支覆盖率 ≥ 80%。
- 每个方法至少覆盖:正常流程、空值边界(null/空串/空集合)、异常流程、各分支。
- **红线(违反任一即不合格)**:
  - 禁改被测源码(`src/main/java`)。
  - 禁 Mockito 注解(`@Mock/@InjectMocks/@Spy/@ExtendWith`),唯一例外 `@MockitoSettings(strictness = LENIENT)`。
  - 禁自定义生命周期,只用父类钩子。
  - 必须继承项目测试基类,禁裸测试类。
  - Java 8 兼容:禁 `var`/`List.of()`/`Map.of()`/`String.isBlank()`/switch 表达式。
  - 断言用 AssertJ,禁 `assertTrue`/`assertEquals`。
  - 字段声明处禁初始化非常量对象(除 `private static final`)。

生成前读取 `testcase-completeness.md`，先列出行为与分支矩阵，再生成代码；生成后逐项回填执行结果和阻塞原因。
