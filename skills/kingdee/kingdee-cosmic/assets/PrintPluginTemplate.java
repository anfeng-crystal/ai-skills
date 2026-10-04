package kd.cd.common;


import kd.bos.print.core.data.DataRowSet;
import kd.bos.print.core.data.datasource.CustomDataSource;
import kd.bos.print.core.data.datasource.PrtDataSource;
import kd.bos.print.core.plugin.AbstractPrintPlugin;
import kd.bos.print.core.plugin.event.AfterOutputWidgetEvent;
import kd.bos.print.core.plugin.event.BeforeLoadDataEvent;
import kd.bos.print.core.plugin.event.BeforeOutputWidgetEvent;
import kd.bos.print.core.plugin.event.CustomDataLoadEvent;

import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * 打印插件骨架模板（原生 AbstractPrintPlugin）。
 * 该类仅用于示例写法，生成后请按实际业务删除无用事件并替换占位常量。
 */
public class PrintPluginTemplate extends AbstractPrintPlugin {

    /**
     * 触发时机: 在需要了解当前插件可访问上下文能力时调用。
     * 参数要点: 无入参；仅展示当前插件可通过 this. 访问的方法能力。
     * 典型用途: 作为模板提示，指导在各事件内选择正确的上下文 API。
     */
    private void getContextSample() {
        // this.getMainDataVisitor();
        // this.getDataVisitor("ds_main");
        // this.getPrintSetting();
        // this.getExtParam();
        // this.getTplInfo();
        // this.isPreview();
    }

    /**
     * 既有数据源取数前：仅在已构造替代结果时取消默认取数。
     * 取消后使用本事件的 dataRowSets，不会因此转入 loadCustomData。
     */
    @Override
    public void beforeLoadData(BeforeLoadDataEvent evt) {
        super.beforeLoadData(evt);
        PrtDataSource dataSource = evt.getDataSource();
        if (!"ds_replace".equals(dataSource.getDsName())) {
            return;
        }
        List<DataRowSet> rows = loadReplacementRows(dataSource);
        if (rows != null) {
            // 本例整体替换事件结果；若要保留前序插件行，先复制已有集合并按业务合并。
            evt.setDataRowSets(rows);
            evt.setCancleLoadData(true);
        }
    }

    /**
     * 模板配置了真正的自定义数据源时，在其结果集合中添加数据。
     * 不清空其他插件已经加入的行；确需整体替换时由业务显式决定。
     */
    @Override
    public void loadCustomData(CustomDataLoadEvent evt) {
        super.loadCustomData(evt);
        if (!"ds_custom".equals(evt.getDataSource().getDsName())) {
            return;
        }
        evt.getCustomDataRows().addAll(loadCustomRows(evt.getDataSource()));
    }

    /**
     * 本模板的业务钩子，非 SDK 事件。实现时按当前数据源字段、过滤及批次构造新集合。
     * null 表示不接管默认取数；空集合表示明确返回零行。
     */
    protected List<DataRowSet> loadReplacementRows(PrtDataSource dataSource) {
        return null;
    }

    /**
     * 本模板的业务钩子，非 SDK 事件。实现后返回非 null 的新结果集合。
     * 默认不贡献行；DataRowSet 中按真实字段放入 TextField、DecimalField 等打印 Field。
     */
    protected List<DataRowSet> loadCustomRows(CustomDataSource dataSource) {
        return Collections.emptyList();
    }

    /**
     * 触发时机: 打印控件输出前。
     * 参数要点: evt 可读取控件标识、当前输出值并在输出前改写。
     * 典型用途: 格式化文本、替换图片地址、控制单元格输出内容。
     */
    @Override
    public void beforeOutputWidget(BeforeOutputWidgetEvent evt) {
        super.beforeOutputWidget(evt);
        Map extParam = this.getExtParam();
        if (extParam != null) {
            extParam.put("beforeOutputWidget", evt.getWidgetKey());
        }
    }

    /**
     * 触发时机: 打印控件输出后。
     * 参数要点: evt 可读取输出结果并做后置调整。
     * 典型用途: 记录输出过程、对合并行列或后置格式做补充处理。
     */
    @Override
    public void afterOutputWidget(AfterOutputWidgetEvent evt) {
        super.afterOutputWidget(evt);
        Map extParam = this.getExtParam();
        if (extParam != null) {
            extParam.put("afterOutputWidget", evt.getWidgetKey());
        }
    }
}
