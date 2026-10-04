# 开放平台自定义 API（注解模式）

详细知识、官方来源与验证边界：[云端专题](https://chatgpt.com/space/page_d872e23fa1308191851c407a9eaba5ab)。

## 适用与版本

本页用于服务端自定义 OpenAPI 控制器，采用 `kd.bos.openapi.common.custom.annotation` 声明 HTTP 接口；普通后台服务、表单插件和外部调用客户端分别走对应入口。控制器不继承表单插件基类，也没有自动获得的 view/model/pageCache。

- [官方《自定义API开发》](https://dev.kingdee.com/open/detail/sdk/2000919573355839488) 标注 Cosmic V6.0.15，更新于 2024-11-05；下表按该正文及实际 7.0 构件核对。不能将其标成 V8.0.1 或 V9 合同。
- 本地 7.0 `bos-open-api` 构件分支为 `hotfix_7.0.16_20250901`。不同补丁、V8/V9 的行为仍须核对目标依赖和对应文档；编译通过不证明发布、参数绑定或鉴权运行通过。
- Bean Validation 按真实类包选择：本地依赖虽名为 `jakarta.validation-api-2.0.2.jar`，类包仍是 `javax.validation`。不要仅凭 JAR 名改为 `jakarta.validation.Valid`；其他版本重新核验。

## 注解与路由合同

| 位置 | 注解 | 执行规则 |
|---|---|---|
| 控制器类 | `@ApiController(value="应用编码", desc="描述")` | 标识自定义控制器；本地 7.0 两个属性均无默认值，声明时均填写 |
| 控制器类 | `@ApiMapping("/前缀")` | 可选的公共路径；不能放到方法上代替 GET/POST 注解 |
| 方法 | `@ApiGetMapping` / `@ApiPostMapping` | 每个接口二选一；`value` 是路径，`desc` 是描述，`methodParamNames` 可按方法参数顺序显式指定参数名 |
| 方法参数 | `@ApiParam` | 参数描述、`required`、JSON 格式 `example`；GET 按官方合同用于基础类型参数，复杂 Model/Map/集合使用 POST |
| 方法参数 | `@ApiRequestBody` | 官方合同为 POST、仅一个参数且是 Model，映射整个请求体；该参数与 `@ApiParam` 二选一 |
| Model 类/属性 | `@ApiModel` / `@ApiParam` | 模型标识与字段说明；Body 模式中模型字段仍可标 `@ApiParam`，不是禁止整个方法所涉及类型出现此注解 |
| 返回泛型 | `@ApiResponseBody` | 本地 Target 为 `TYPE_USE`，例如 `CustomApiResult<@ApiResponseBody("结果说明") Boolean>`；不要当作方法级注解 |

`required=true` 不代替正数、长度或业务约束。模型属性的 Bean Validation 使用目标依赖提供的 `@Valid`、`@NotNull`、`@Min` 等；级联校验与直接调用 Java 方法也不是一回事。Map 内部每个值需按接口合同显式解析，不能把整个 Map 的必填声明当作内部字段校验。

注解模式的触发点是平台路由命中后调用方法，没有传统表单插件生命周期回调。调用方身份和租户来自已核实的平台认证上下文；业务入参不能替代权限与数据范围校验。

## 完整模板与输入边界

[OpenApiControllerTemplate.java](../../../assets/OpenApiControllerTemplate.java) 保留 GET 查询、POST Map、POST 单 Model Body 三个入口，以及类、方法、参数、模型和返回注解。

- GET 返回 `U-<id>` 演示值，不查询业务数据。GET 和 Map 的示例 ID 合同是 `1..Long.MAX_VALUE`；该规则只属于此示例，不改变全平台主键规则。
- Map 的 `id` 接受 Byte/Short/Integer/Long、无小数且不溢出的 BigInteger/BigDecimal，以及 1..19 位十进制数字字符串。拒绝零、负数、小数、溢出、空值、布尔值、其他对象和 Float/Double；浮点值可能已丢失原 JSON 精度，不能转 long 截断或舍入。实际绑定产生浮点类型时，应按此合同拒绝并调整输入模型/解析配置，不猜测原 ID。
- `EntityUtils.isEmptyPk` 是目标项目封装的判空谓词，不是正整数转换或持久化存在性检查；任意 JSON number 不应直接传给它。
- 两个保存入口校验通过后仍返回 `OpenApi_NotImplemented`。实现者接入真实保存服务并确认结果后，才能返回成功或保存后的模型；不能用 `success(true)`、回显请求或非空 ID 证明落库。Map 参数错误保留 `KDBizException(ErrorCode)` 示例，GET/Body 保留 `CustomApiResult.fail` 示例。

## Model 校验与返回封装示例

以下完整类展示模型校验和结果封装。业务查询/保存留为抽象方法，因此不能作为已实现控制器直接注册；应在目标项目实现业务方法并完成挂载和验证。这里只保留 `CustomApiResult<T>` 与 `Serializable` 的官方示例模式，不声称所有其他返回类型或非 Serializable 控制器必然无法发布。

```java
import java.io.Serializable;
import javax.validation.Valid;
import javax.validation.constraints.Min;
import javax.validation.constraints.NotNull;
import kd.bos.openapi.common.custom.annotation.ApiController;
import kd.bos.openapi.common.custom.annotation.ApiGetMapping;
import kd.bos.openapi.common.custom.annotation.ApiMapping;
import kd.bos.openapi.common.custom.annotation.ApiModel;
import kd.bos.openapi.common.custom.annotation.ApiParam;
import kd.bos.openapi.common.custom.annotation.ApiPostMapping;
import kd.bos.openapi.common.custom.annotation.ApiResponseBody;
import kd.bos.openapi.common.result.CustomApiResult;

@ApiController(value = "open", desc = "用户API业务骨架")
@ApiMapping("/user")
public abstract class UserController implements Serializable {
    private static final long serialVersionUID = 1L;

    /** 参数校验后查询；具体项目定义未找到记录时的返回合同。 */
    @ApiGetMapping("/get")
    public CustomApiResult<String> getUserNameById(
            @ApiParam(value = "用户ID", required = true) Long id) {
        if (id == null || id <= 0L) {
            return CustomApiResult.fail("PARAM_ID", "id 必须大于 0");
        }
        return CustomApiResult.success(findUserName(id));
    }

    /** 根据实际保存结果决定成功；平台绑定入口使用 @Valid 级联模型校验。 */
    @ApiPostMapping("/save")
    public CustomApiResult<@ApiResponseBody("true-保存成功") Boolean> saveUser(
            @ApiParam(value = "用户数据", required = true) @Valid UserModel user) {
        if (user == null || user.getId() == null || user.getId() <= 0L
                || user.getUserName() == null) {
            return CustomApiResult.fail("PARAM_USER", "用户ID须为正数，用户名不能为空");
        }
        if (!persistUser(user)) {
            return CustomApiResult.fail("SAVE_FAILED", "保存未成功");
        }
        return CustomApiResult.success(Boolean.TRUE);
    }

    /** 实现项目查询与授权范围，不得返回未经授权的数据。 */
    protected abstract String findUserName(Long id);

    /** 实现真实保存，只有确认业务操作成功后才返回 true。 */
    protected abstract boolean persistUser(UserModel user);

    @ApiModel
    public static class UserModel implements Serializable {
        private static final long serialVersionUID = 1L;
        @ApiParam(value = "用户ID", required = true, example = "1001")
        @NotNull
        @Min(1L)
        private Long id;
        @ApiParam(value = "用户名", required = true, example = "Tom")
        @NotNull
        private String userName;

        public Long getId() { return id; }
        public void setId(Long id) { this.id = id; }
        public String getUserName() { return userName; }
        public void setUserName(String userName) { this.userName = userName; }
    }
}
```

`CustomApiResult.success(data)` 只封装传入结果，不执行业务保存；是否成功必须来自实际业务结果。`@ApiResponseBody` 提供描述和示例，不替代响应值的正确性。示例保留控制器/模型的 `Serializable`；额外序列化或非标准返回要求应按目标接口发布与运行合同核实。

## 请求路径与旧模式边界

[官方《自定义API（Java插件）》](https://vip.kingdee.com/knowledge/294499338368404736)（更新于 2026-03-30，变更表列 V5.0.011、V6.0.1）给出的路径为 `/kapi/v2/{isv}/{appId}/{serviceName}`。注解服务的编码由类级公共路径与方法路径组合；以 API 管理生成的实际地址和网关前缀为准，不手工省略部署上下文或开发商段。官方标准接口的开发商标识可为空，不等于任意自建接口可删除该段。

- 旧模式：`IBillWebApiPlugin#doCustomService(...)`。本地 7.0 仍有 Map 参数及 WebApiContext 参数两个重载，未见 `@Deprecated` 标记；这不能证明所有版本继续支持，也不能写成旧接口已经全面移除。
- 注解模式：`@ApiController` 声明式控制器。新建自定义 API 可按已确认版本采用本页；迁移现有接口时先核目标版本支持、已发布路径、入参/返回和调用方依赖，不能仅因有新写法强制替换存量接口。
- 注册、发布、API 在线测试及权限配置是独立平台动作，按任务授权执行；本地编译和静态检查不代替平台验收。
