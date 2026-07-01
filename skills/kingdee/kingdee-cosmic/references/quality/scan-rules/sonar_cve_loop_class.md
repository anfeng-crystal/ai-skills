| 规则编码 | 规则名称                                                          | 规则等级 | 规则类型 | 规则配置 | 解决方案 |
| --- |---------------------------------------------------------------| --- | --- | --- | --- |
| CVE-KD-0051-03 | 禁止在循环中访问kd.bos.cache.redis.RedisSessionlessCache              | 低危 | 循环里面指定类 | loop class = kd.bos.cache.redis.RedisSessionlessCache | 请使用批量接口访问 |
| CVE-KD-0051-04 | 禁止在循环中访问kd.bos.cache.redis.RedisSessionableCache              | 低危 | 循环里面指定类 | loop class = kd.bos.cache.redis.RedisSessionableCache | 请使用批量接口访问 |
| CVE-KD-0051-07 | 禁止在循环中访问kd.bos.data.BusinessDataReader                        | 低危 | 循环里面指定类 | loop class = kd.bos.data.BusinessDataReader | 请使用批量接口访问 |
| CVE-KD-0051-08 | 禁止在循环中访问kd.bos.data.BusinessDataWriter                        | 低危 | 循环里面指定类 | loop class = kd.bos.data.BusinessDataWriter | 请使用批量接口访问 |
| CVE-KD-0051-09 | 禁止在循环中访问kd.bos.servicehelper.operation.OperationServiceHelper | 低危 | 循环里面指定类 | loop class = kd.bos.servicehelper.operation.OperationServiceHelper | 请使用批量接口访问 |
| CVE-KD-0051-10 | 禁止在循环中访问kd.bos.servicehelper.operation.SaveServiceHelper      | 低危 | 循环里面指定类 | loop class = kd.bos.servicehelper.operation.SaveServiceHelper | 请使用批量接口访问 |
| CVE-KD-0051-11 | 禁止在循环中访问kd.bos.servicehelper.operation.DeleteServiceHelper    | 低危 | 循环里面指定类 | loop class = kd.bos.servicehelper.operation.DeleteServiceHelper | 请使用批量接口访问 |
| CVE-KD-0054-2 | 禁止在循环中访问kd.bos.mvc.cache.RootPageCache                        | 低危 | 循环里面指定类 | loop class = kd.bos.mvc.cache.RootPageCache | 避免在循环内访问RootPageCache |
| CVE-KD-0058-1 | 禁止在循环中访问kd.bos.logging.Log                                    | 严重 | 循环里面指定类 | loop class = kd.bos.logging.Log | 避免在循环内写日志，可将日志内容在循环内拼接后，在循环外写日志。  正确示例  if (logger.isDebugEnabled()) { // 先检查日志级别      StringBuilder logBuffer = new StringBuilder();      for (int i = 0; i < 1000; i++) {          // 循环内仅拼接内容          logBuffer.append("Item ").append(i)                   .append(": ").append(computeResult(i)).append("  ");      }      // 循环外单次输出日志      logger.debug("Processing results:  {}", logBuffer);  } |
| CVE-KD-0058-2 | 禁止在循环中访问org.slf4j.Logger                                      | 低危 | 循环里面指定类 | loop class = org.slf4j.Logger | 避免在循环内写日志，可将日志内容在循环内拼接后，在循环外写日志 |
| CVE-KD-0201 | 禁止在循环中访问kd.bos.servicehelper.DispatchServiceHelper            | 低危 | 循环里面指定类 | loop class = kd.bos.servicehelper.DispatchServiceHelper | 使用批量接口 |
