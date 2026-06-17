# WebAPI/开放接口开发指南

> 来源: 基于平台API和社区资料整理（https://vip.kingdee.com/knowledge/436173612442080512, https://vip.kingdee.com/article/453488865555495936）
> 日期: 2026-04-12
> 标签: WebAPI, IBillWebApiPlugin, 开放接口, 自定义API, 集成服务云

---

## 摘要
金蝶云苍穹提供多种方式实现 WebAPI 开发：通过 IBillWebApiPlugin 接口创建自定义 API，通过开放平台注册和管理 API，以及通过集成服务云的 WebAPI 登记功能调用外部系统接口。

## 适用版本
- 金蝶云苍穹 V5.0+
- 开放平台 API 2.0 需要 V5.0.020+

## 核心概念

### WebAPI 开发方式分类

| 方式 | 适用场景 | 关键类/工具 |
|------|----------|-------------|
| 自定义 API（IBillWebApiPlugin） | 对外暴露自定义业务接口 | `IBillWebApiPlugin` |
| 开放平台 | 标准操作服务和自定义服务的 API 管理 | 开放平台第三方应用 |
| 集成服务云 WebAPI 登记 | 调用外部系统的 WebAPI | 连接配置、服务编排 |
| 微服务 | 内部跨应用调用 | `DispatchServiceHelper` |

### 认证方式

苍穹开放平台支持以下认证方式：
- **摘要加密认证**：基于 AppKey + AppSecret 生成签名
- **第三方应用认证**：通过开放平台注册第三方应用，获取编码和密钥
- **账套 ID + 租户 ID**：用于标识目标数据中心

## 详细内容

### 一、自定义 API 开发（IBillWebApiPlugin）

#### 1.1 接口定义

`IBillWebApiPlugin` 是苍穹提供的自定义 WebAPI 接口，开发者可以通过实现该接口来创建自定义的 RESTful API。

```java
package kd.bos.openapi.common.custom.annotation;

/**
 * 自定义 WebAPI 插件接口
 * 用于创建对外暴露的自定义业务接口
 */
public interface IBillWebApiPlugin {
    /**
     * API 请求处理入口
     * @param request 请求对象，包含请求参数、请求头等信息
     * @param response 响应对象，用于设置返回数据
     */
    void doCustomService(Map<String, Object> request, Map<String, Object> response);
}
```

#### 1.2 完整实现示例

```java
package com.example.webapi;

import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.openapi.common.custom.annotation.ApiController;
import kd.bos.openapi.common.custom.annotation.ApiMapping;
import kd.bos.openapi.common.custom.annotation.ApiParam;
import kd.bos.servicehelper.BusinessDataServiceHelper;
import kd.bos.servicehelper.QueryServiceHelper;
import kd.bos.orm.query.QFilter;
import kd.bos.orm.query.QCP;

import java.util.*;

/**
 * 自定义 WebAPI 示例：查询单据信息
 *
 * 注册路径：【开发服务云】→【开放平台】→【自定义服务】
 */
@ApiController(value = "billQuery", desc = "单据查询接口")
public class BillQueryWebApi {

    /**
     * 根据单据编号查询单据信息
     * 请求方式: POST
     * 请求路径: /ierp/kapi/v2/f/{appId}/billQuery/queryByNumber
     */
    @ApiMapping(value = "queryByNumber", desc = "根据编号查询单据")
    public Map<String, Object> queryByNumber(
            @ApiParam(value = "entityNumber", desc = "实体编码") String entityNumber,
            @ApiParam(value = "billNo", desc = "单据编号") String billNo) {

        Map<String, Object> result = new HashMap<>();

        try {
            // 构造查询条件
            QFilter filter = new QFilter("billno", QCP.equals, billNo);

            // 查询单据
            DynamicObject bill = BusinessDataServiceHelper.loadSingle(
                entityNumber,
                new QFilter[]{filter}
            );

            if (bill != null) {
                result.put("success", true);
                result.put("data", convertToMap(bill));
            } else {
                result.put("success", false);
                result.put("message", "未找到对应单据");
            }
        } catch (Exception e) {
            result.put("success", false);
            result.put("message", e.getMessage());
        }

        return result;
    }

    /**
     * 批量查询单据
     */
    @ApiMapping(value = "queryList", desc = "批量查询单据列表")
    public Map<String, Object> queryList(
            @ApiParam(value = "entityNumber", desc = "实体编码") String entityNumber,
            @ApiParam(value = "filters", desc = "过滤条件JSON") String filters,
            @ApiParam(value = "pageIndex", desc = "页码") int pageIndex,
            @ApiParam(value = "pageSize", desc = "每页条数") int pageSize) {

        Map<String, Object> result = new HashMap<>();

        try {
            // 解析过滤条件
            QFilter[] qFilters = parseFilters(filters);

            // 分页查询
            String selectFields = "id,billno,billstatus,createtime";
            DynamicObject[] dataList = QueryServiceHelper.query(
                entityNumber, selectFields, qFilters,
                "createtime desc", pageIndex * pageSize, pageSize
            ).toArray(new DynamicObject[0]);

            List<Map<String, Object>> records = new ArrayList<>();
            for (DynamicObject obj : dataList) {
                Map<String, Object> record = new HashMap<>();
                record.put("id", obj.get("id"));
                record.put("billno", obj.getString("billno"));
                record.put("billstatus", obj.getString("billstatus"));
                records.add(record);
            }

            result.put("success", true);
            result.put("data", records);
            result.put("total", QueryServiceHelper.queryCount(entityNumber, qFilters));
        } catch (Exception e) {
            result.put("success", false);
            result.put("message", e.getMessage());
        }

        return result;
    }

    private Map<String, Object> convertToMap(DynamicObject obj) {
        // 将 DynamicObject 转换为 Map
        Map<String, Object> map = new HashMap<>();
        map.put("id", obj.getPkValue());
        map.put("billno", obj.getString("billno"));
        return map;
    }

    private QFilter[] parseFilters(String filters) {
        // 解析过滤条件 JSON 为 QFilter 数组
        // 具体实现根据业务需求
        return new QFilter[]{};
    }
}
```

#### 1.3 注册自定义 API

1. 进入【开发服务云】→【开放平台】→【自定义服务】
2. 新增自定义服务，填写服务编码和名称
3. 配置服务类路径（完整包名 + 类名）
4. 保存并发布

#### 1.4 API 调用方式

```bash
# 获取 access_token
curl -X POST "https://{host}/ierp/api/getToken.do" \
  -H "Content-Type: application/json" \
  -d '{
    "app_id": "你的应用编码",
    "app_secret": "你的应用密钥",
    "tenant_id": "租户ID",
    "account_id": "账套ID",
    "language": "zh_CN"
  }'

# 调用自定义 API
curl -X POST "https://{host}/ierp/kapi/v2/f/{appId}/billQuery/queryByNumber" \
  -H "Content-Type: application/json" \
  -H "access_token: {your_access_token}" \
  -d '{
    "entityNumber": "your_bill_entity",
    "billNo": "BILL-20260001"
  }'
```

### 二、开放平台 API 管理

#### 2.1 第三方应用配置

路径：【开发服务云】→【开放平台】→【第三方应用】

关键配置项：

| 字段 | 说明 |
|------|------|
| 开放应用编码 | 第三方应用的唯一标识 |
| 摘要加密认证密钥 | 用于 API 调用认证的密钥 |
| 账套 ID | 目标数据中心标识 |

#### 2.2 API 2.0 连接配置

适用于与企业外部苍穹系统集成（如 B2B 场景）：

| 字段 | 说明 |
|------|------|
| 开放应用编码 | 目标苍穹系统的第三方应用编码 |
| 摘要加密认证密钥 | 对应的密钥 |
| 账套 ID | 目标系统的数据中心 ID |

### 三、集成服务云 WebAPI 登记

#### 3.1 调用外部系统 WebAPI 的流程

1. **创建连接类型**：定义外部系统的连接方式
2. **创建连接配置**：填写具体连接参数（IP、端口、凭证等）
3. **WebAPI 登记**：登记外部系统的 API（支持 curl 快速导入）
4. **服务编排**：设计数据同步流程

#### 3.2 连接类型脚本配置

```javascript
// 会话登录脚本示例
var url = $protocal + "://" + $ip + ":" + $port + "/api/auth/login";
var param = {
    "username": this.user,
    "password": this.password
};
var response = HttpInvoke(url, param, {}, {}).result;
if (!response.code || response.code != 200) {
    throw "调用登录接口失败，返回结果为：" + response;
}
var session = response.data;
// 设置刷新时间（token 过期前1小时）
session.$refreshTime = L(NOW) + session.expires_in * 60 * 1000 - 60 * 60 * 1000;
return session;
```

```javascript
// 会话刷新脚本示例
var url = $protocal + "://" + $ip + ":" + $port + "/api/auth/refresh";
var header = { Authorization: $session.access_token };
HttpInvoke(url, {}, {}, header).result;
$session.$refreshTime = L(NOW) + 720 * 60 * 1000 - 60 * 60 * 1000;
return $session;
```

#### 3.3 服务编排调用 WebAPI

```javascript
// 在服务编排脚本节点中调用外部 WebAPI
var queryString = { pageNum: 1, pageSize: 10 };

// 调用依赖资源中配置的 WebAPI
var_result = webapi_resource({}, {}, queryString);
// 解析 JSON 字符串
var_result = String.ParseJson(var_result);
```

### 四、微服务方式（内部接口）

#### 4.1 微服务接口定义

```java
package com.example.mservice;

/**
 * 微服务接口定义
 */
public interface IBillService {
    /**
     * 查询单据信息
     * @param entityNumber 实体编码
     * @param billNo 单据编号
     * @return 单据数据 Map
     */
    Map<String, Object> queryBill(String entityNumber, String billNo);
}
```

#### 4.2 微服务调用

```java
// 通过 DispatchServiceHelper 调用微服务
Map<String, Object> result = DispatchServiceHelper.invokeService(
    "com.example.mservice",  // 服务工厂限定前缀
    "your_app_id",           // 应用ID
    "IBillService",          // 服务名称
    "queryBill",             // 方法名
    entityNumber, billNo     // 方法参数
);
```

## 注意事项

1. **认证安全**：API 密钥和 Token 不要硬编码在代码中，应通过 MC 配置管理
2. **参数校验**：对外接口必须对所有输入参数做严格校验，防止 SQL 注入和 XSS
3. **性能考虑**：批量查询接口必须做分页处理，单次返回数据量不宜过大
4. **跨应用调用**：跨云跨应用必须使用微服务，不能直接依赖对应 jar 包
5. **版本兼容**：API 2.0 仅支持 V5.0.020+，旧版本需使用"苍穹-API"连接类型
6. **超时设置**：第三方 API 接口调用必须设置超时时间
7. **错误处理**：统一使用 KDException，返回结构化的错误信息

## 相关链接
- [连接配置（苍穹-API2.0）](https://vip.kingdee.com/knowledge/436173612442080512)
- [集成服务云 WebAPI 数据集成案例](https://vip.kingdee.com/article/453488865555495936)
- [苍穹系统外部接口调用指南](https://vip.kingdee.com/article/753290922178946560)
- [开放平台 SDK 文档](https://dev.kingdee.com/index/open)
- [金蝶AI苍穹定制化开发规范](https://vip.kingdee.com/knowledge/498888207505798912)
