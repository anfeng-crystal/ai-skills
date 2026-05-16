| 规则编码 | 规则名称 | 规则等级 | 规则类型 | 规则配置 | 解决方案 |
| --- | --- | --- | --- | --- | --- |
| CVE-KD-0011-2 | 禁止使用关键字java.lang.reflect | 低危 | 关键字 | keyword = java.lang.reflect | 禁止使用反射 |
| CVE-KD-0013-1 | 禁止使用关键字drop table | 低危 | 关键字 | keyword = drop table | 禁止使用drop table |
| CVE-KD-0013-2 | 禁止使用关键字truncate table | 低危 | 关键字 | keyword = truncate table | 关键字禁止使用truncate table |
| CVE-KD-0013-3 | 禁止使用关键字rename table | 低危 | 关键字 | keyword = rename table | 禁止使用rename table |
| CVE-KD-0020 | 禁止使用关键字redis.clients.jedis | 低危 | 关键字 | keyword = redis.clients.jedis | 禁止直接访问Jedis，如需使用缓存的能力，可以考虑AppCache或PageCache等其它工具类 |
| CVE-KD-0022 | 禁止使用关键字org.apache.zookeeper | 低危 | 关键字 | keyword = org.apache.zookeeper | 禁止直接访问苍穹连接Zookeeper的基础类 |
| CVE-KD-0023 | 禁止使用关键字com.rabbitmq.client | 低危 | 关键字 | keyword = com.rabbitmq.client | 禁止直接访问RabbitMQ的客户端，如需要使用MQ的能力，请参考以下文档  https://vip.kingdee.com/knowledge/494909705664368384?specialId=282527627108140288&productLineId=29&isKnowledge=2&lang=zh-CN |
| CVE-KD-0024 | 禁止使用关键字org.apache.rocketmq.client | 低危 | 关键字 | keyword = org.apache.rocketmq.client | 禁止直接访问RocketMQ的客户端，如需要使用MQ的能力，请参考以下文档  https://vip.kingdee.com/knowledge/494909705664368384?specialId=282527627108140288&productLineId=29&isKnowledge=2&lang=zh-CN |
| CVE-KD-0025 | 禁止使用关键字org.apache.kafka.clients | 低危 | 关键字 | keyword = org.apache.kafka.clients | 禁止直接访问Kafka的客户端，如需要使用MQ的能力，请参考以下文档  https://vip.kingdee.com/knowledge/494909705664368384?specialId=282527627108140288&productLineId=29&isKnowledge=2&lang=zh-CN |
| CVE-KD-0026-1 | 禁止使用关键字attachmentServer.url | 低危 | 关键字 | keyword = attachmentServer.url | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-10 | 禁止使用关键字file/getFileSize.do | 低危 | 关键字 | keyword = file/getFileSize.do | 禁止使用file/getFileSize.do访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-11 | 禁止使用关键字file/transferTempToPersist.do | 低危 | 关键字 | keyword = file/transferTempToPersist.do | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-12 | 禁止使用关键字login/getTicket.do | 低危 | 关键字 | keyword = login/getTicket.do | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-13 | 禁止使用关键字tempfile/supportTempfile.do | 低危 | 关键字 | keyword = tempfile/supportTempfile.do | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-14 | 禁止使用关键字tempfile/isSupported.do | 低危 | 关键字 | keyword = tempfile/isSupported.do | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-15 | 禁止使用关键字tempfile/isSupportTempTransToPersist.do | 低危 | 关键字 | keyword = tempfile/isSupportTempTransToPersist.do | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-16 | 禁止使用关键字fileServerManage/getVersion.do | 低危 | 关键字 | keyword = fileServerManage/getVersion.do | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-17 | 禁止使用关键字fileServerManage/getDiskUrlInfos.do | 低危 | 关键字 | keyword = fileServerManage/getDiskUrlInfos.do | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-18 | 禁止使用关键字fileServerManage/getMatchFileMsgInfos.do | 低危 | 关键字 | keyword = fileServerManage/getMatchFileMsgInfos.do | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-19 | 禁止使用关键字fileServerManage/getChildrenFileMsgInfos.do | 低危 | 关键字 | keyword = fileServerManage/getChildrenFileMsgInfos.do | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-2 | 禁止使用关键字imageServer.url | 低危 | 关键字 | keyword = imageServer.url | 禁止imageServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-20 | 禁止使用关键字fileServerManage/getMaxDirectoryScanDepth.do | 低危 | 关键字 | keyword = fileServerManage/getMaxDirectoryScanDepth.do | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-21 | 禁止使用关键字fileServerManage/getFileMsgInfo.do | 低危 | 关键字 | keyword = fileServerManage/getFileMsgInfo.do | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-22 | 禁止使用关键字ServerManage/getFileMsgInfoTree.do | 低危 | 关键字 | keyword = ServerManage/getFileMsgInfoTree.do | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-23 | 禁止使用关键字fileServerManage/buildRmScript.do | 低危 | 关键字 | keyword = fileServerManage/buildRmScript.do | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-24 | 禁止使用关键字fileServerManage/buildCopyScript.do | 低危 | 关键字 | keyword = fileServerManage/buildCopyScript.do | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-25 | 禁止使用关键字ereceipt.url | 低危 | 关键字 | keyword = ereceipt.url | 禁止attachmentServer.url直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-3 | 禁止使用关键字attachment.fileserver | 低危 | 关键字 | keyword = attachment.fileserver | 禁止直接attachment.fileserver访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-4 | 禁止使用关键字image.fileserver | 低危 | 关键字 | keyword = image.fileserver | 禁止image.fileserver直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-5 | 禁止使用关键字file/upload.do | 低危 | 关键字 | keyword = file/upload.do | 禁止file/upload.do直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-6 | 禁止使用关键字file/remove.do | 低危 | 关键字 | keyword = file/remove.do | 禁止直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-7 | 禁止使用关键字file/exists.do | 低危 | 关键字 | keyword = file/exists.do | 禁止file/exists.do直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-8 | 禁止使用关键字file/getForbiddenExtensions.do | 低危 | 关键字 | keyword = file/getForbiddenExtensions.do | 禁止使用file/getForbiddenExtensions.do直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0026-9 | 禁止使用关键字file/getAllowExtensions.do | 低危 | 关键字 | keyword = file/getAllowExtensions.do | 禁止使用file/getAllowExtensions.do直接访问文件服务器，文件服务器使用说明请参考：https://dev.kingdee.com/open/detail/sdk/2077750765610350592 |
| CVE-KD-0028-01 | 禁止使用关键字contains("configKey=redis.serversForCache&id=tempfile") | 严重 | 关键字 | keyword = contains("configKey=redis.serversForCache&id=tempfile") | 修改为临时文件存储模式无关的判断，请使用：contains("tempfile/download.do?configKey") |
| CVE-KD-0028-02 | 禁止使用关键字contains("configKey=tempfile.redis") | 严重 | 关键字 | keyword = contains("configKey=tempfile.redis") | 修改为临时文件存储模式无关的判断，请使用：contains("tempfile/download.do?configKey") |
| CVE-KD-0028-03 | 禁止使用关键字contains("configKey=redis.serversForCache") | 严重 | 关键字 | keyword = contains("configKey=redis.serversForCache") | 修改为临时文件存储模式无关的判断，请使用：contains("tempfile/download.do?configKey") |
| CVE-KD-0028-04 | 禁止使用关键字contains("configKey=tempfile.fileserver") | 严重 | 关键字 | keyword = contains("configKey=tempfile.fileserver") | 修改为临时文件存储模式无关的判断，请使用：contains("tempfile/download.do?configKey") |
| CVE-KD-0028-05 | 禁止使用关键字contains("configKey=tempfile.disk") | 严重 | 关键字 | keyword = contains("configKey=tempfile.disk") | 修改为临时文件存储模式无关的判断，请使用：contains("tempfile/download.do?configKey") |
| CVE-KD-0028-06 | 禁止使用关键字indexOf("configKey=redis.serversForCache&id=tempfile") | 严重 | 关键字 | keyword = indexOf("configKey=redis.serversForCache&id=tempfile") | 修改为临时文件存储模式无关的判断，请使用：indexOf("tempfile/download.do?configKey") |
| CVE-KD-0028-07 | 禁止使用关键字indexOf("configKey=tempfile.redis") | 严重 | 关键字 | keyword = indexOf("configKey=tempfile.redis") | 修改为临时文件存储模式无关的判断，请使用：indexOf("tempfile/download.do?configKey") |
| CVE-KD-0028-08 | 禁止使用关键字indexOf("configKey=redis.serversForCache") | 严重 | 关键字 | keyword = indexOf("configKey=redis.serversForCache") | 修改为临时文件存储模式无关的判断，请使用：indexOf("tempfile/download.do?configKey") |
| CVE-KD-0028-09 | 禁止使用关键字indexOf("configKey=tempfile.fileserver") | 严重 | 关键字 | keyword = indexOf("configKey=tempfile.fileserver") | 修改为临时文件存储模式无关的判断，请使用：indexOf("tempfile/download.do?configKey") |
| CVE-KD-0028-10 | 禁止使用关键字indexOf("configKey=tempfile.disk") | 严重 | 关键字 | keyword = indexOf("configKey=tempfile.disk") | 修改为临时文件存储模式无关的判断，请使用：indexOf("tempfile/download.do?configKey") |
| CVE-KD-0053-01 | 禁止使用关键字select * | 低危 | 关键字 | keyword = select * | 禁止使用select * |
| CVE-KD-0060-1 | 禁止使用关键字/*dialect*/ | 严重 | 关键字 | keyword = /*dialect*/ | 使用金蝶ORM框架 |
| CVE-KD-0209-1 | 禁止使用关键字System.out.print | 低危 | 关键字 | keyword = System.out.print | 使用kd.bos.logging.LogFactory获取kd.bos.logging.Log打印日志 |
| CVE-KD-0209-2 | 禁止使用关键字.printStackTrace( | 低危 | 关键字 | keyword = .printStackTrace( | 使用kd.bos.logging.LogFactory获取kd.bos.logging.Log打印日志 |
| CVE-KD-0720-1 | 禁止使用关键字CREATE VIEW | 严重 | 关键字 | keyword = CREATE VIEW | 目前，为了公有云环境安全，星空旗舰版禁止创建和使用自定义视图； 私有云订阅环境不建议创建和使用自定义视图。 |
| CVE-KD-0721-1 | 禁止使用关键字CREATE PROCEDURE | 严重 | 关键字 | keyword = CREATE PROCEDURE | 目前，为了公有云环境安全，星空旗舰版禁止创建和使用自定义视图； 私有云订阅环境不建议创建和使用自定义视图。 |
| CVE-KD-0721-2 | 禁止使用关键字CREATE OR REPLACE PROCEDURE | 严重 | 关键字 | keyword = CREATE OR REPLACE PROCEDURE | 目前，为了公有云环境安全，星空旗舰版禁止创建和使用自定义存储过程；私有云订阅环境不建议创建和使用自定义存储过程。 |
| CVE-KD-0722-1 | 禁止使用关键字CREATE FUNCTION | 严重 | 关键字 | keyword = CREATE FUNCTION | 目前，为了公有云环境安全，星空旗舰版禁止创建和使用自定义函数；私有云订阅环境不建议创建和使用自定义函数。 |
| CVE-KD-0722-2 | 禁止使用关键字CREATE OR REPLACE FUNCTION | 严重 | 关键字 | keyword = CREATE OR REPLACE FUNCTION | 目前，为了公有云环境安全，星空旗舰版禁止创建和使用自定义函数；私有云订阅环境不建议创建和使用自定义函数。 |
| CVE-KD-0723-1 | 禁止使用关键字CREATE TRIGGER | 严重 | 关键字 | keyword = CREATE TRIGGER | 目前，为了公有云环境安全，星空旗舰版禁止创建和使用自定义触发器；私有云订阅环境不建议创建和使用自定义触发器。 |
| CVE-KD-0723-2 | 禁止使用关键字CREATE OR REPLACE TRIGGER | 严重 | 关键字 | keyword = CREATE OR REPLACE TRIGGER | 目前，为了公有云环境安全，星空旗舰版禁止创建和使用自定义触发器；私有云订阅环境不建议创建和使用自定义触发器。 |
