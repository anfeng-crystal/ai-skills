package kd.cd.common;

import kd.bos.entity.api.ApiResult;
import kd.bos.entity.plugin.ImportLogger;
import kd.bos.form.plugin.impt.BatchImportPlugin;
import kd.bos.form.plugin.impt.ImportBillData;

import java.util.Iterator;
import java.util.List;
import java.util.Map;

/**
 * 批量导入插件骨架模板（原生 BatchImportPlugin）。
 * 该类仅用于示例写法，生成后请按实际业务删除无用事件并替换占位常量。
 */
public class BatchImportPluginTemplate extends BatchImportPlugin {

    private static final int BATCH_SIZE = 200;
    private static final String FIELD_BILL_STATUS = "billstatus";
    private static final String FIELD_BILL_NO = "billno";
    private static final String FIELD_NAME = "name";

    // ===== 核心事件 =====

    /**
     * 触发时机: 导入引擎初始化批处理策略时。
     * 参数要点: 返回值决定单批处理行数。
     * 典型用途: 控制批量导入吞吐、内存占用与事务规模。
     */
    @Override
    protected int getBatchImportSize() {
        return BATCH_SIZE;
    }

    /**
     * 触发时机: 导入引擎判断是否强制批处理时。
     * 参数要点: 返回 true 表示按批次执行。
     * 典型用途: 大数据量导入时强制走批处理模式。
     */
    @Override
    protected boolean isForceBatch() {
        return true;
    }

    /**
     * 触发时机: 每批数据执行保存时。
     * 参数要点:
     * - rowdatas: 当前批次行数据。
     * - logger: 导入日志记录器，用于记录行级失败原因。
     * 典型用途: 批量校验、过滤非法数据、自定义保存逻辑。
     * 返回值: 原样返回默认保存结果；空批由默认实现返回 null，不会再次保存。
     */
    @Override
    protected ApiResult save(List<ImportBillData> rowdatas, ImportLogger logger) {
        Iterator<ImportBillData> iterator = rowdatas.iterator();
        while (iterator.hasNext()) {
            ImportBillData data = iterator.next();
            Map<String, Object> rowData = data.getData();
            Object name = rowData == null ? null : rowData.get(FIELD_NAME);
            String billStatus = rowData == null ? null : String.valueOf(rowData.get(FIELD_BILL_STATUS));
            String billNo = rowData == null ? null : String.valueOf(rowData.get(FIELD_BILL_NO));
            if (name == null) {
                logger.log(data.getStartIndex(), "名称不能为空").fail();
                logger.signTotalRow(data.getEndIndex() - data.getStartIndex() + 1);
                iterator.remove();
                continue;
            }
            if ("A".equalsIgnoreCase(billStatus)) {
                logger.log(data.getStartIndex(), "单据" + billNo + "为暂存状态，不允许导入").fail();
                logger.signTotalRow(data.getEndIndex() - data.getStartIndex() + 1);
                iterator.remove();
            }
        }
        return super.save(rowdatas, logger);
    }
}
