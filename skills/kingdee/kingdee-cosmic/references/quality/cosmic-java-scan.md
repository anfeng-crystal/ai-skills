# 苍穹 Java 扫描规则参考

## 使用方式
- 代码审查或实现高风险逻辑时，检查禁用类、禁用方法、关键字、静态集合变量和循环内高风险调用。
- 命中平台底层绕行、直接 SQL、原生线程、缓存/Redis/ZK 直连等风险时，优先改用苍穹标准服务、ORM、QFilter、调度中心、平台缓存或已有封装。
- 扫描规则只作为风险提示；最终以当前项目依赖、官方资料和编译结果为准。

## 规则入口
- 指定类禁用：`incoming/market/cosmic-cus-java-scan/raw/cosmic-cus-java-scan/references/sonar_cve_class.md`
- 指定方法禁用：`incoming/market/cosmic-cus-java-scan/raw/cosmic-cus-java-scan/references/sonar_cve_method.md`
- 关键字禁用：`incoming/market/cosmic-cus-java-scan/raw/cosmic-cus-java-scan/references/sonar_cve_keyword.md`
- 静态变量/集合风险：`incoming/market/cosmic-cus-java-scan/raw/cosmic-cus-java-scan/references/sonar_cve_static.md`
- 循环内高风险类/方法：`incoming/market/cosmic-cus-java-scan/raw/cosmic-cus-java-scan/references/sonar_cve_loop_class.md`、`sonar_cve_loop_method.md`

## 禁止事项
- 不运行会改动 skill 目录结构的维护脚本。
- 不把扫描结果当作自动修复依据。
- 不跳过项目规则、官方资料和本地依赖校验。
