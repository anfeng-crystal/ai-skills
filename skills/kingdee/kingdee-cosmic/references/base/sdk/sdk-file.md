# 文件服务 (File Service)

路径分层、同路径覆盖与证据范围见 [云端知识：文件路径与上传覆盖](https://chatgpt.com/space/page_18dfcc834cb881919df3fffa0e48479a)；本页保留执行合同与接口示例。

## 适用与边界

物理文件上传、读取、删除与预览先区分附件服务、图片服务、临时缓存；还需挂到业务附件面板/字段时，继续读[附件绑定 API](../../adv/attachment-api.md)。物理上传成功不等于单据关联已保存。

以下签名由本地实际 7.0 JAR 核验，参数语义结合官方 V7.0.1 Javadoc 和附件 FAQ；FAQ 未给这些接口统一的版本范围。目标为其他版本时重新核对实际依赖，不把本文当作全版本保证。

## 先识别路径

| 输入/目的 | 入口及参数合同 |
|---|---|
| 缓存中的临时附件 | `CacheFactory.getCommonCacheFactory().getTempFileCache().getInputStream(tempPath)`；路径必须仍在缓存有效期内 |
| 持久化附件 | `FileServiceFactory.getAttachmentFileService().getInputStream(relativePath)`；传非加密相对路径 |
| 图片服务器文件 | `FileServiceFactory.getImageFileService().getInputStream(relativePath)`；传该图片的非加密相对路径 |
| 已有加密路径转明文 | 附件用 `FileServiceExtFactory.getAttachFileServiceExt().getRealPath(encryptedPath)`，图片用 `getImageFileServiceExt().getRealPath(encryptedPath)` |
| 相对路径转完整访问地址 | `UrlService.getAttachmentFullUrl(relativePath)` / `getImageFullUrl(relativePath)` |
| 持久附件预览 | `UrlService.getAttachmentPreviewUrl(relativePath)` |
| 临时附件预览 | `IAttachmentModel.getTempFilePreviewUrl(fullTempUrl)`；这是模型实例方法，参数为临时下载绝对地址 |

上述 `CacheFactory`、`FileServiceExtFactory`、`UrlService`、`IAttachmentModel` 分别位于 `kd.bos.cache`、`kd.bos.fileservice.extension`、`kd.bos.url`、`kd.bos.entity.datamodel`。不要把完整下载 URL、加密标识、相对路径互换，也不要自行拼 download 前缀或去掉路径层级。

缓存临时 URL 不能长期保存成业务附件地址。临时转持久、附件面板与字段的绑定接口及对应主键分别按附件文档处理。路径解析或存在性异常时，区分缓存过期、存储端缺失和容器访问问题；不能用 `InputStream.available()` 证明总长度或文件完整性。

## 文件服务 API

`kd.bos.fileservice.FileServiceFactory` 的 `getAttachmentFileService()` / `getImageFileService()` 均返回 `kd.bos.fileservice.FileService`。

- `String upload(FileItem item)`：返回文件存储标识，通常为相对路径。保留实际返回值并按调用目标解析，不能称其为完整 URL、唯一授权凭证或自行拼造业务绑定记录。
- `InputStream getInputStream(String path)`：读取文件流，由调用方关闭；无论大小都可使用。
- `void download(String path, OutputStream out, String userAgent)`：下载到输出流，另有响应对象和请求头/响应头重载。不存在 `download(String) -> byte[]`；需要内存字节数组时还须限定文件大小。
- `void delete(String path)`：物理删除，不负责业务关联数据清理；按已授权业务范围检查权限、引用与恢复条件后使用。
- `FileService` 继承 `kd.bos.fileservice.preview.PreviewService`，其 `preview(String, String, String)` 返回 `Map<String,Object>`，不存在 `preview(String)`。仅需预览 URL 时使用上表官方 URL 入口；底层预览重载的参数语义另核目标文档。

`kd.bos.fileservice.FileItem` 的构造器为 `FileItem(String fileName, String path, InputStream in)`：第一参含扩展名，第二参是存储相对路径，不是 MIME 类型。V7.0.1 上传文档要求路径保留租户、数据中心、日期和业务目录层级；实际附件标准路径按 FAQ 的面板/字段规则及平台路径生成入口取得，不硬编码当前租户或账套。

上传前确认同路径冲突策略：V7.0.1 `FileItem` 文档在 fileserver 场景下说明 `createNewFileWhenExists` 默认 `false`，同路径会覆盖；设置 `true` 时另建文件。该选项不适用于 OSS、MinIO 等二开存储。本地 7.0 构件也将此标志初始化为 `false`，这只核实对象默认值，不证明实际后端行为。需要保留旧文件时，按目标存储合同准备路径和新建策略，并使用上传实际返回的标识；不能把这个开关当作所有后端的防覆盖保证。

## 物理上传示例

调用方提供按目标存储规则生成的相对路径，并确认不会与需保留的文件冲突，或业务明确允许覆盖；下面没有开启同路径另建，不将重复上传当作幂等保证。此方法接管传入流的关闭；`FileItem` 有 `close()`，但本地 7.0 未实现 `AutoCloseable`，使用 `finally` 释放资源。

```java
import kd.bos.fileservice.FileItem;
import kd.bos.fileservice.FileService;
import kd.bos.fileservice.FileServiceFactory;
import java.io.InputStream;

public final class FileDemo {
    public String uploadFile(String fileName, String relativePath, InputStream input) {
        FileItem item = new FileItem(fileName, relativePath, input);
        try {
            FileService fs = FileServiceFactory.getAttachmentFileService();
            return fs.upload(item);
        } finally {
            item.close();
        }
    }

    public void deleteFile(String relativePath) {
        FileServiceFactory.getAttachmentFileService().delete(relativePath);
    }
}
```

流打开后若在调用本方法之前失败，仍由打开方关闭。上传文件名与后缀需准确；预览可用性还取决于文件内容、格式和目标预览服务，不能仅改后缀判定成功。读取返回流时也需处理缺失/失败并关闭资源；不能用编译通过替代存储、下载或预览验收。

## 官方依据

- [附件二开常见问题汇总](https://vip.kingdee.com/knowledge/449213564277170432)，更新于 2024-07-10 15:14，2026-10-05 已登录核验正文；本卡使用第1～6、9～11节及“常见误区”，未标统一 API 版本。
- [FileItem · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/fileservice/FileItem.html)：构造参数、关闭语义及同路径处理的后端范围；2026-10-05 核验。
- [FileService · V7.0.1](https://dev.kingdee.com/sdk/Cosmic%20V7.0.1/javadoc/kd/bos/fileservice/FileService.html)：上传返回标识、路径规范、读取和下载重载。精确签名同时对照实际 7.0 JAR；文档或版本差异不靠方法名推断。
