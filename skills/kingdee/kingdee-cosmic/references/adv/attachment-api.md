# 附件面板、附件字段与文件绑定

## 适用与选路

- 项目确有 `kd.cd.common.attachment` 依赖时，优先复用 `AttachmentUtils`、`AttPanelUploader` 等已有包装；这些是项目扩展，不是所有苍穹部署自带的标品 API。先核目标依赖，再用本卡的包装示例。
- 没有该包装时，使用原生 `kd.bos.servicehelper.AttachmentServiceHelper` 与 `AttDto`。纯文件流上传、下载、临时转持久和路径处理读 [文件服务](../base/sdk/sdk-file.md)，使用 `FileServiceFactory` / `FileService`，不要把未核归属的 `FileServiceHelper` 当通用 SDK。
- 物理文件、附件引用记录、业务字段/面板绑定是不同层。上传成功不等于业务附件绑定完成；`updateView` 只负责界面绑定，不证明数据库持久化或重开后可见。

本卡的原生签名和包装行为以实际本地 7.0 JAR 核对；这不证明任意目标补丁兼容或平台执行成功。官方版本范围见文末。

## 绑定前核对

| 输入/条件 | 合同 |
|---|---|
| `formNumber` | 目标单据/表单标识。本地 7.0 按 `MetaCategory.Form` 加载元数据，再解析业务实体；不能传任意实体 UUID，也不能凭同名推断派生布局标识可用 |
| `billPkId` | 已保存并可按该表单实体加载的单据主键。主键已分配不等于记录已持久化 |
| `AttDto.attKey` | 附件面板 Key **或附件字段 Key**，不是目标单据标识。官方示例的此处注释与其参数表冲突，应按真实元数据核实 |
| `entryPkId` | 分录附件字段使用真实分录行主键；不是行号。单据头附件不填。附件面板不作为单据体附件字段的替代 |
| `path` | 已存在文件的附件服务器相对路径。先按文件服务合同区分临时/持久路径、加密路径和下载 URL；不能只去掉 URL 参数就假定得到有效相对路径 |
| `size` | 实际文件字节数；本地 7.0 绑定校验要求大于 0。优先在上传时记录，`getFileSizeByPath` 会读流计算，属于耗时操作 |
| 文件名 | `AttDto` 提供 `setFileName`，没有 `setName`；本地 7.0 绑定校验会从真实路径重算文件名和扩展名，单设 DTO 名称不能保证最终显示名 |
| 附件字段表名 | V5.0.1+ 官方问题说明要求配置数据表名；默认空表名可能出现保存成功但重开附件丢失。该配置是附件字段的持久化条件，不泛化为面板属性 |

## 保存与失败边界

1. 页面尚未保存时，沿用该表单控件的临时附件和正常保存流程；不要只为调用后台绑定而预保存用户单据。后台给已有单据补附件时，先确认单据及所需分录已保存、文件上传成功，再绑定。
2. 绑定调用会写附件关系及相关业务数据；在已授权的操作/服务入口执行，按目标事务所有权和失败恢复合同接入。不能把文件服务器写入当成数据库事务回滚的一部分，也不能从无事务保护的表单回调随意补写数据库。
3. 原生 `bindingAttachment` 返回 `Map<String,Object>`；包装 `bind/bindSingle` 返回 `kd.cd.core.tuple.State`，其判断为 `isTrue()` 和 `text()`，不是 `isSuccess()/getMessage()`。**返回检查不是全部错误处理**：本地 7.0 原生异常路径及包装均可能直接抛异常，应按调用上下文传播/处理，不能吞掉后报告绑定成功。
4. 验证覆盖绑定结果、数据库可见的附件关系、重开单据及对应分录后的附件显示，以及授权范围内的读取/预览。失败清理先区分未绑定文件与已有共享引用；不要因本次绑定失败直接物理删除已有附件。

## 已有项目包装：绑定一份已上传文件

`newAttDto(panelOrFieldKey, path, sizeInBytes, entryPk, consumer)` 返回 `AttDto`；consumer 可为空。下面不假设 DTO 自定义名称能覆盖路径文件名。目标项目必须提供相应 `kd.cd` 依赖。

```java
import kd.bos.exception.KDBizException;
import kd.bos.servicehelper.AttDto;
import kd.cd.common.attachment.AttachmentUtils;
import kd.cd.core.tuple.State;

/** Requires the project-provided kd-cd-cosmic-commons.jar. */
public class ProjectBinding {
    public void bindExistingFile(String formNumber, Object savedBillPk,
                                 String panelOrFieldKey, String path,
                                 long sizeInBytes, Object savedEntryPk) {
        if (sizeInBytes <= 0) {
            throw new IllegalArgumentException("sizeInBytes must be positive");
        }
        AttDto dto = AttachmentUtils.newAttDto(
                panelOrFieldKey, path, sizeInBytes, savedEntryPk, null);
        State result = AttachmentUtils.bindSingle(formNumber, savedBillPk, dto);
        if (!result.isTrue()) {
            throw new KDBizException(result.text());
        }
    }
}
```

## 无项目包装：原生绑定

```java
import java.util.Collections;
import java.util.Map;
import kd.bos.exception.KDBizException;
import kd.bos.servicehelper.AttDto;
import kd.bos.servicehelper.AttachmentServiceHelper;

/** Only call for a saved bill/entry and an existing attachment-server path. */
public class NativeBinding {
    public void bindExistingFile(String formNumber, String savedBillPkId,
                                 String panelOrFieldKey, String path,
                                 long sizeInBytes, String savedEntryPkId) throws Exception {
        if (sizeInBytes <= 0) {
            throw new IllegalArgumentException("sizeInBytes must be positive");
        }
        AttDto dto = new AttDto();
        dto.setAttKey(panelOrFieldKey);
        dto.setPath(path);
        dto.setSize(sizeInBytes);
        if (savedEntryPkId != null) {
            dto.setEntryPkId(savedEntryPkId);
        }
        Map<String, Object> params = AttachmentServiceHelper.genBindingParam(
                formNumber, savedBillPkId, Collections.singletonList(dto));
        Map<String, Object> result = AttachmentServiceHelper.bindingAttachment(params);
        if (!Boolean.TRUE.equals(result.get("success"))) {
            throw new KDBizException(String.valueOf(result.get("message")));
        }
    }
}
```

## 动态表单临时面板转存到已有单据

此路线用于动态表单附件面板已完成临时上传，用户确认后把附件持久化到**已保存目标单据的附件面板**。它不等于往未保存业务单据里自动注入附件，也不是附件字段/分录字段的通用方案。

- 在已授权的确认操作中执行；目标 `formId`、应用编码 `appId`、已保存主键及目标面板 Key 必须来自已核实的业务上下文。页面控件锁定不构成绕过目标权限或业务规则的授权。
- 源数据使用 `AttachmentPanel.getAttachmentData()` 返回的完整 `List<Map<String,Object>>`，外层 Map 的 key 是**目标面板 Key**。不要由文件 URL 猜造缺失属性，也不要传字段 Key 替代面板 Key。
- `AttachmentServiceHelper.saveTempAttachments(String formId, Object pkId, String appId, Map<String,Object> attachments)` 返回 `DynamicObjectCollection`。它承接临时文件转持久及附件记录保存；不能替换为只写附件信息的 `upload`，也不需要依据方法名另加一次物理上传。

下面是供确认事件调用的辅助方法。传入真实源 `AttachmentPanel`（页面插件可用 `getControl(sourcePanelKey)` 获取）与目标信息；示例不负责目标权限验证或业务规则决策。

```java
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import kd.bos.dataentity.entity.DynamicObjectCollection;
import kd.bos.form.control.AttachmentPanel;
import kd.bos.servicehelper.AttachmentServiceHelper;

/** Call from an authorized confirm action for an already saved target bill. */
public final class ConfirmedPanelTransfer {
    private ConfirmedPanelTransfer() {
    }

    public static DynamicObjectCollection transferAfterConfirm(
            AttachmentPanel sourcePanel, String targetFormId,
            Object savedTargetPk, String targetAppId, String targetPanelKey) {
        if (sourcePanel == null || savedTargetPk == null) {
            throw new IllegalArgumentException("Source panel and saved target are required");
        }
        List<Map<String, Object>> attachmentData = sourcePanel.getAttachmentData();
        if (attachmentData == null || attachmentData.isEmpty()) {
            throw new IllegalArgumentException("No attachments to transfer");
        }
        Map<String, Object> attachmentMap = new HashMap<>(1);
        attachmentMap.put(targetPanelKey, attachmentData);
        // The helper may update attachmentData maps while persisting the files.
        return AttachmentServiceHelper.saveTempAttachments(
                targetFormId, savedTargetPk, targetAppId, attachmentMap);
    }
}
```

本地 7.0 实现会改写传入附件 Map 的 `url`、`size`、`extName` 等属性；不要在失败重试时假定还握有原始临时 URL。文件写入与附件数据库保存不是一个可统一回滚的物理事务；附件记录保存使用独立事务，后面还可能执行操作回调，因此异常不能证明“完全未写入”。失败后先核实际路径与目标附件记录，再决定补偿或重试，不能承诺重复确认天然幂等。

若用户取消且尚未调用转存方法，就不要补执行目标绑定；源临时附件仍按平台缓存生命周期处理，不承诺取消会立即物理删除。若已转存成功，再关闭/取消源动态表单也不能当作撤销目标附件。

验收要打开已保存目标，核面板附件及下载、重命名、备注等能力，并确认持久附件路径不含 `tempfile`；仅方法返回或界面刷新不足以验收。此例已用实际 7.0 依赖/Java 8 离线编译，未运行页面确认、取消、故障补偿或附件服务器持久化。

`IAttachmentModel.uploadTemp` 的存在性不等于自动注入方案已经确认。当前未核实其全部 String/Map 参数及对应页面模型生命周期，不提供猜参数代码；未保存页面仍走前述正常临时上传与用户保存流程。

## 附件面板复制与项目辅助能力

以下均属于已核验的 `kd.cd` 包装，使用前匹配项目版本：

- `copyToPanel(srcFormId, srcPk, srcPanelKey, tarFormId, tarPk, tarPanelKey)` 及带末参 `CopyFeature` 的重载；也支持以 `Collection<Long> attPks` 替代前三参。返回 `Object[]`。此处面板参数为**面板 Key**，不能因绑定支持字段就推断复制方法也支持字段。
- 本地实现克隆附件引用记录并保存，按目标已有附件编号跳过重复；不复制物理文件，也不会删除目标多余附件，不是“全量镜像同步”。并发防重和事务恢复仍需目标验证，不声称性能最优。
- `download(pathOrUrl)` 返回 `InputStream`，调用方用 try-with-resources 关闭；包装还提供 `physicDelete(String...)`、`getFileName`、`getSuffix`、`isValidPath`、`isDownloadUrl`、`isTempUrl`、`isImageType`、`stripFromDownloadUrl`、`stripParameter`、`decodeUtf8`。路径解析不等于授权、文件存在性或持久化证明。
- `BindType` 是项目包装枚举，不替代原生附件字段/面板元数据核验。包装上传示例见 [AttachmentUploadBindSample](../../assets/snippets/attachment/AttachmentUploadBindSample.java)，同样要求已保存目标和项目依赖。

```java
import kd.cd.common.attachment.AttachmentUtils;

public class AttDemo {
    public Object[] copyPanelReferences(Object orderPk, Object inbillPk) {
        return AttachmentUtils.copyToPanel(
            "pm_purorderbill", orderPk, "att_panel",
            "stk_purinbill", inbillPk, "att_panel"
        );
    }
}
```

上述标识仅演示参数位置，必须替换为目标元数据确认的标识和已保存主键。

```java
import java.io.IOException;
import java.io.InputStream;
import kd.cd.common.attachment.AttachmentUtils;

public class AttachmentReader {
    public static void process(String fileUrl) throws IOException {
        try (InputStream input = AttachmentUtils.download(fileUrl)) {
            if (input == null) {
                throw new IOException("Attachment stream is unavailable");
            }
            // 在此消费流；不要把已关闭的流传到调用方。
        }
    }
}
```

`CopyFeature` 保留创建人、修改人与描述等复制控制：`setCreatorId(Long)`、`setUseCurrentUserAsCreator(boolean)`、`setUseCurrentUserAsModifier(boolean)`、`setCopyLastModifyTime(boolean)`、`setFileSource(Integer)`、`setClearDesc(boolean)`。按目标审计需求配置，不能以修改创建人替代调用权限。

`physicDelete` 针对物理文件；文件被多个单据引用时会影响其他附件。临时文件存在清理生命周期，持久化和业务绑定按实际路径处理，不能承诺所有 `bind` 都会把任意临时 URL 转正。中文文件名按文件服务编码合同处理，不重复编码或盲目解码。

## 官方依据

- [通过动态表单同步附件到目标单据](https://vip.kingdee.com/knowledge/703637473892578304?specialId=294832938980257024)，更新于 2025-04-25；官方正文示例为临时附件面板转存已有单据，链接 V7.0.1 SDK，未列最低版本。
- [AttachmentServiceHelper V7.0.1 Javadoc](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/servicehelper/AttachmentServiceHelper.html)：`saveTempAttachments` 四参、返回类型及应用编码语义；独立事务和 Map 改写边界另由实际 7.0 实现核实。

- [附件绑定单据接口](https://vip.kingdee.com/knowledge/126693402678062080?productLineId=29&isKnowledge=2&lang=zh-CN)，更新于 2026-07-30 14:21；未列最低版本。参数表、上传后绑定顺序和原生调用。
- [附件字段保存后丢失](https://vip.kingdee.com/knowledge/specialDetail/294832938980257024?category=449215545481861120&id=762626637996212224&type=Knowledge&productLineId=29&lang=zh-CN)，更新于 2025-10-05 18:01，适用 V5.0.1+；字段表名配置。
- [附件字段使用介绍](https://vip.kingdee.com/knowledge/specialDetail/294832938980257024?category=294833007750630656&id=223799007145730048&type=Knowledge&productLineId=29&lang=zh-CN)，更新于 2025-12-19 12:58；面板/字段位置和表名等属性。

以上于 2026-10-02 通过已登录官方知识库读取正文；评论和社区 AI 未作为合同依据。项目包装行为来自实际依赖，不能归称官方标品保证。
