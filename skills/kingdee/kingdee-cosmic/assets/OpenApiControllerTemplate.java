package kd.cd.common;

import java.io.Serializable;
import java.math.BigDecimal;
import java.math.BigInteger;
import java.util.Map;

import kd.bos.dataentity.resource.ResManager;
import kd.bos.exception.ErrorCode;
import kd.bos.exception.KDBizException;
import kd.bos.openapi.common.custom.annotation.ApiController;
import kd.bos.openapi.common.custom.annotation.ApiGetMapping;
import kd.bos.openapi.common.custom.annotation.ApiMapping;
import kd.bos.openapi.common.custom.annotation.ApiModel;
import kd.bos.openapi.common.custom.annotation.ApiParam;
import kd.bos.openapi.common.custom.annotation.ApiPostMapping;
import kd.bos.openapi.common.custom.annotation.ApiRequestBody;
import kd.bos.openapi.common.custom.annotation.ApiResponseBody;
import kd.bos.openapi.common.result.CustomApiResult;

/**
 * 开放平台自定义 API 骨架模板（注解模式）。
 * 查询返回演示值；两个保存入口在接入真实业务前固定返回未实现，不执行持久化。
 * 生成后按实际业务替换占位常量、输入合同和保存逻辑，再注册需要的接口。
 */
@ApiController(value = "open", desc = "示例开放 API")
@ApiMapping("/template")
public class OpenApiControllerTemplate implements Serializable {
    private static final long serialVersionUID = 1L;
    private static final String RES_APP_ID = "kd-cd-common-template";

    /**
     * 触发时机: 在需要了解当前控制器可通过 this. 访问哪些能力时调用。
     * 参数要点: 无入参；OpenAPI 控制器不具备表单插件的 view/model/pageCache 上下文。
     * 典型用途: 查看本类方法；租户、用户等身份上下文来自平台认证，不信任请求体自报身份。
     */
    private void getContextSample() {
        // this.getClass();
        // this.getById(1001L);
        // this.saveMap(java.util.Collections.emptyMap());
        // this.saveBody(new UserModel());
    }

    private static final String ERR_CODE_PARAM = "OpenApi_001";
    private static final String ERR_CODE_NOT_IMPLEMENTED = "OpenApi_NotImplemented";

    /** 演示正整数 Long ID 校验和成功结果封装，不查询实际业务数据。 */
    @ApiGetMapping(value = "/getById", desc = "按 id 返回演示值（不查询实际数据）")
    public CustomApiResult<String> getById(
            @ApiParam(value = "主键ID", required = true, example = "1001") Long id) {
        if (parsePositiveId(id) == null) {
            return CustomApiResult.fail(ERR_CODE_PARAM, ResManager.loadKDString("id 必须大于 0", "OpenApiControllerTemplate_0", RES_APP_ID));
        }
        return CustomApiResult.success("U-" + id);
    }

    /** 演示 Map 参数校验；校验通过仍返回未实现，不能据此认定已经保存。 */
    @ApiPostMapping(value = "/saveMap", desc = "Map 入参保存骨架（未实现持久化）")
    public CustomApiResult<@ApiResponseBody("true-成功，false-失败") Boolean> saveMap(
            @ApiParam(value = "业务数据", required = true) Map<String, Object> data) {
        Long id = data == null ? null : parsePositiveId(data.get("id"));
        if (id == null) {
            throw new KDBizException(new ErrorCode(
                    ERR_CODE_PARAM,
                    ResManager.loadKDString("id 必须是 Long 范围内的正整数", "OpenApiControllerTemplate_1", RES_APP_ID)
            ));
        }
        // 接入业务时使用校验后的 id；仅以真实保存结果决定成功，不能用入参校验代替保存。
        return CustomApiResult.fail(ERR_CODE_NOT_IMPLEMENTED,
                ResManager.loadKDString("示例尚未实现保存", "OpenApiControllerTemplate_3", RES_APP_ID));
    }

    /** 演示 POST 单模型请求体；真实保存完成后才能返回持久化后的模型。 */
    @ApiPostMapping(value = "/saveBody", desc = "@ApiRequestBody 保存骨架（未实现持久化）")
    public CustomApiResult<@ApiResponseBody("保存后的模型") UserModel> saveBody(
            @ApiRequestBody(value = "用户模型", required = true) UserModel model) {
        if (model == null || model.getUserName() == null) {
            return CustomApiResult.fail(ERR_CODE_PARAM, ResManager.loadKDString("userName 不能为空", "OpenApiControllerTemplate_2", RES_APP_ID));
        }
        return CustomApiResult.fail(ERR_CODE_NOT_IMPLEMENTED,
                ResManager.loadKDString("示例尚未实现保存", "OpenApiControllerTemplate_3", RES_APP_ID));
    }

    /**
     * 本示例的 ID 合同：1..Long.MAX_VALUE，不代表平台所有实体的主键规则。
     * 接受整数包装类型、精确整数 BigInteger/BigDecimal 和 1..19 位十进制数字字符串。
     * Float/Double 可能已丢失 JSON 原值精度，拒绝它们及其他类型；不截断、不舍入。
     * 无效值返回 null，由各入口按自己的错误返回方式处理。
     */
    private static Long parsePositiveId(Object value) {
        final long id;
        try {
            if (value instanceof Byte || value instanceof Short
                    || value instanceof Integer || value instanceof Long) {
                id = ((Number) value).longValue();
            } else if (value instanceof BigInteger) {
                id = ((BigInteger) value).longValueExact();
            } else if (value instanceof BigDecimal) {
                id = ((BigDecimal) value).longValueExact();
            } else if (value instanceof String && ((String) value).matches("[0-9]{1,19}")) {
                id = Long.parseLong((String) value);
            } else {
                return null;
            }
        } catch (ArithmeticException | NumberFormatException ex) {
            return null;
        }
        return id > 0L ? id : null;
    }

    /**
     * 示例请求体模型。
     */
    @ApiModel
    public static class UserModel implements Serializable {
        private static final long serialVersionUID = 1L;

        @ApiParam(value = "用户ID", example = "1001")
        private Long id;

        @ApiParam(value = "用户名", required = true, example = "Tom")
        private String userName;

        public Long getId() {
            return id;
        }

        public void setId(Long id) {
            this.id = id;
        }

        public String getUserName() {
            return userName;
        }

        public void setUserName(String userName) {
            this.userName = userName;
        }
    }
}
