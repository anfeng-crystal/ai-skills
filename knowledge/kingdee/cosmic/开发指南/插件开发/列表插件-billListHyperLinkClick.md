# 金蝶云苍穹列表插件 - billListHyperLinkClick 超链接点击事件

> 来源: 联网搜索整理
> 整理时间: 2026-04-12

---

## 1. 官方文档 - 列表单元格超链接功能

**来源:** https://vip.kingdee.com/article/647744891501591296

### 摘要

本文介绍了单据列表超链接点击事件的触发时机、事件参数获取、取消界面打开操作、获取列表单元格值的方法，以及创建自定义列表单元格超链接打开指定界面的实现。

### 核心内容

- 触发时机：点击列表单元格超链接时
- 事件参数获取：通过 `HyperLinkClickArgs` 获取
- 可以取消系统默认的打开操作
- 支持创建自定义超链接打开指定界面

---

## 2. 简书 - billListHyperLinkClick 事件案例

**来源:** https://www.jianshu.com/p/5f8b5c54f0f5

（内容较短，主要是代码示例）

---

## 3. 详细代码案例

**来源:** https://yanbo0039.github.io/blog/zh/programBlog/ServerSideLanguage/Kingdee/kingdee80.html

### 实现步骤

1. 新建带组织模板单据
2. 设置表名后保存
3. 在表单的基本信息里面添加文本字段，将标识更改为 `textfield1`，名称更改为"文本1"
4. 进入列表界面，将添加的文本1字段添加到表格视图中并设置为超链接显示
5. 保存并授权

### 完整代码示例

```java
package kd.bos.bill.plugin;

import kd.bos.bill.BillShowParameter;
import kd.bos.bill.OperationStatus;
import kd.bos.dataentity.utils.StringUtils;
import kd.bos.form.ShowType;
import kd.bos.form.events.HyperLinkClickArgs;
import kd.bos.list.plugin.AbstractListPlugin;

/**
 * 列表超链接点击事件示例
 */
public class BillListHyperLinkClickSample extends AbstractListPlugin {
    private final static String KEY_TEXTFIELD1 = "textfield1";

    @Override
    public void billListHyperLinkClick(HyperLinkClickArgs args) {
        // 判断点击的是否是文本1字段
        if (StringUtils.equals(KEY_TEXTFIELD1, args.getHyperLinkClickEvent().getFieldName())) {
            // 当前点击的是文本1
            // 取消系统自动打开本单的处理
            args.setCancel(true);

            // 打开物料新增界面
            BillShowParameter showParameter = new BillShowParameter();
            showParameter.setFormId("bd_material");
            showParameter.getOpenStyle().setShowType(ShowType.Modal);
            showParameter.setStatus(OperationStatus.ADDNEW);
            this.getView().showForm(showParameter);
        }
    }
}
```

### 关键说明

- `args.setCancel(true)` - 取消系统默认的打开单据操作
- `args.getHyperLinkClickEvent().getFieldName()` - 获取点击的字段名
- 可以在事件中打开其他表单界面

---

## 相关文章推荐

1. 【苍穹开发学习笔记】—1—列表插件—获取列表选择行的信息
2. 【苍穹开发学习笔记】—9—列表插件—billClosedCallBack事件
3. 【苍穹开发学习笔记】—8—列表插件—beforeShowBill事件
4. 【苍穹开发学习笔记】—5—列表插件—beforeCreateListDataProvider事件
