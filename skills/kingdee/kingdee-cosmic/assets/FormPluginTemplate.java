package kd.cd.common;

import kd.bos.bill.OperationStatus;
import kd.bos.dataentity.OperateOption;
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.dataentity.resource.ResManager;
import kd.bos.dataentity.serialization.SerializationUtils;
import kd.bos.entity.datamodel.RowDataEntity;
import kd.bos.entity.datamodel.events.AfterAddRowEventArgs;
import kd.bos.entity.datamodel.events.AfterDeleteEntryEventArgs;
import kd.bos.entity.datamodel.events.AfterDeleteRowEventArgs;
import kd.bos.entity.datamodel.events.BizDataEventArgs;
import kd.bos.entity.datamodel.events.PropertyChangedArgs;
import kd.bos.entity.operate.result.OperationResult;
import kd.bos.form.CloseCallBack;
import kd.bos.form.ConfirmCallBackListener;
import kd.bos.form.FormShowParameter;
import kd.bos.form.IFormView;
import kd.bos.form.MessageBoxOptions;
import kd.bos.form.MessageBoxResult;
import kd.bos.form.ShowType;
import kd.bos.form.control.events.BeforeItemClickEvent;
import kd.bos.form.control.events.ItemClickEvent;
import kd.bos.form.events.AfterDoOperationEventArgs;
import kd.bos.form.events.BeforeClosedEvent;
import kd.bos.form.events.BeforeDoOperationEventArgs;
import kd.bos.form.events.ClosedCallBackEvent;
import kd.bos.form.events.MessageBoxClosedEvent;
import kd.bos.form.events.PreOpenFormEventArgs;
import kd.bos.form.field.events.BeforeF7SelectEvent;
import kd.bos.form.operate.AbstractOperate;
import kd.bos.list.ListShowParameter;
import kd.bos.orm.query.QCP;
import kd.bos.orm.query.QFilter;
import kd.cd.common.form.FormUtils;
import kd.cd.common.form.ShowParameterUtils;
import kd.cd.common.plugin.AbstractFormPluginExt;
import kd.cd.common.util.DynamicObjectUtils;
import kd.cd.core.util.CharSequenceUtils;
import kd.cd.core.util.CollectionUtils;

import java.util.EventObject;
import java.util.List;
import java.util.Set;

/**
 * 表单/单据/基础资料插件骨架模板。
 * 该类仅用于示例写法，生成后请按实际业务删除无用事件并替换占位常量。
 * <p>
 * 低频事件（分录移动/置顶/拖拽/合计、导入、定时器、自定义事件等）已省略，
 * 需要时请查阅 references/base/plugin/plugin-form.md 获取方法签名。
 * <pre>
 * 方法索引（按需保留，各方法下方有参数/用途说明）
 * 生命周期：initialize / registerListener / preOpenForm / beforeClosed
 * 数据：createNewData / afterCreateNewData / beforeBindData / afterBindData / afterCopyData
 * 菜单：beforeItemClick / itemClick；操作：beforeDoOperation / afterDoOperation
 * 字段：propertyChanged；回调：confirmCallBack / closedCallBack
 * F7：beforeF7Select；分录：afterAddRow / afterDeleteRow / afterDeleteEntry
 * </pre>
 * @template FormPluginTemplate
 * @extends AbstractFormPluginExt (kd.cd.common.plugin)
 * @highFreqEvents afterBindData, propertyChanged, beforeDoOperation, afterDoOperation, itemClick, closedCallBack
 * @medFreqEvents registerListener, beforeF7Select, confirmCallBack, afterCreateNewData, afterAddRow, beforeClosed
 * @relatedDocs references/adv/plugin-base.md, references/base/plugin/plugin-form.md
 */
public class FormPluginTemplate extends AbstractFormPluginExt {

    // 占位常量：复制模板后请统一替换为业务真实 key。
    private static final String KEY_1 = "key1";
    private static final String KEY_2 = "key2";
    private static final String KEY_3 = "key3";
    private static final String TB_MAIN = "tbmain";
    private static final String TB_MAIN_1 = "tbmain1";
    private static final String TB_MAIN_2 = "tbmain2";
    private static final String ENTRY_KEY_1 = "entrykey1";
    private static final String ENTRY_KEY_2 = "entrykey2";
    private static final String FORM_ID_F7 = "billformid1";
    private static final String FORM_ID_MODAL = "billformid2";
    private static final String CLOSE_ACTION_ID = "actionid";
    private static final String CONFIRM_CALLBACK_ID = "callbackid1";
    private static final String CUSTOM_PARAM_KEY = "key";
    private static final String CUSTOM_PARAM_VALUE = "val2";
    private static final String PAGE_CACHE_SUBMIT_FLAG = "submitflag";
    private static final String PAGE_CACHE_OPERATE_KEY = "operatekey";
    private static final String RETURN_DATA_CONTINUE = "continueoperate";
    private static final String FIELD_BILL_NO = "billno";
    private static final String FILTER_VALUE_A = "A";
    private static final String OPTION_VAR_VALUE = "value1";
    private static final String RES_APP_ID = "kd-cd-common-template";

    // ===== 生命周期事件 =====

    /**
     * 视图注入后的轻量初始化，可能随请求重建再次执行。
     * 缓存仅在键缺失时设默认值，保留页面此前恢复的业务状态。
     */
    @Override
    public void initialize() {
        super.initialize();
        if (this.getPageCache().get(PAGE_CACHE_SUBMIT_FLAG) == null) {
            this.getPageCache().put(PAGE_CACHE_SUBMIT_FLAG, "false");
        }
    }

    /**
     * 在当前控件实例上注册菜单、点击、F7、超链接及分录行监听。
     * EventObject 为通用参数；同一路径避免重复 add，不假定每页仅调用一次。
     */
    @Override
    public void registerListener(EventObject e) {
        super.registerListener(e);
        // 注册按钮、菜单、F7（基础资料/引用数据选择控件）等监听。
        this.addBeforeF7SelectListeners(KEY_1, KEY_2, KEY_3);
        this.addItemClickListeners(TB_MAIN, TB_MAIN_1, TB_MAIN_2);
        this.addClickListeners(KEY_1, KEY_2, KEY_3);
        this.addHyperClickListeners(KEY_1, KEY_2, KEY_3);
        this.addEntryRowClickListeners(ENTRY_KEY_1, ENTRY_KEY_2, KEY_3);
    }

    /**
     * 触发时机: 表单打开前，参数准备阶段。
     * - PreOpenFormEventArgs e: 包含表单打开参数。
     * - e.getFormShowParameter(): 获取和修改表单打开参数。
     * - e.getFormShowParameter().getParentPageId(): 获取父页面 ID。
     * 典型用途: 调整表单打开参数、访问父页面数据进行参数传递。
     */
    @Override
    public void preOpenForm(PreOpenFormEventArgs e) {
        super.preOpenForm(e);
        // 打开前参数处理示例。
        FormShowParameter fsp = e.getFormShowParameter();
        String parentPageId = fsp.getParentPageId();
        IFormView parentView = FormUtils.getViewByPageId(parentPageId);
        if (parentView != null) {
            Object value = parentView.getModel().getValue(KEY_1);
            fsp.setCustomParam(CUSTOM_PARAM_KEY, value);
        }
    }

    /**
     * 触发时机: 表单关闭前，用户点击关闭按钮或程序调用关闭前。
     * - BeforeClosedEvent e: 关闭前事件参数。
     * - e.setCancel(true): 取消关闭操作。
     * 典型用途: 关闭前校验、返回数据到父页面、触发父页面操作。
     */
    @Override
    public void beforeClosed(BeforeClosedEvent e) {
        super.beforeClosed(e);
        if ("true".equals(this.getView().getPageCache().get(PAGE_CACHE_SUBMIT_FLAG))) {
            this.getView().returnDataToParent(RETURN_DATA_CONTINUE);
            return;
        }
    }

    // ===== 数据创建/绑定事件 =====

    /**
     * 新建数据包阶段，可自定义构建逻辑；BizDataEventArgs 为数据事件参数。
     * 本例把打开参数转入页面缓存，供初始赋值使用。
     */
    @Override
    public void createNewData(BizDataEventArgs e) {
        super.createNewData(e);
        Object value = getView().getFormShowParameter().getCustomParams().get(CUSTOM_PARAM_KEY);
        if (value != null) {
            getView().getPageCache().put(CUSTOM_PARAM_KEY, String.valueOf(value));
        }
    }

    /**
     * 新数据包完成后设置字段默认值、处理分录初始数据。
     * 此时字段赋值不触发 propertyChanged；所需初始计算必须显式完成。
     */
    @Override
    public void afterCreateNewData(EventObject e) {
        super.afterCreateNewData(e);
        getModel().setValue(KEY_1, getView().getPageCache().get(CUSTOM_PARAM_KEY));
        getModel().setValue(KEY_2, FILTER_VALUE_A);
        List<DynamicObject> selectRowsEntity = getEntrySelectRowsEntity(ENTRY_KEY_1);
        if (CollectionUtils.isNotEmpty(selectRowsEntity)) {
            Set<Object> pks = DynamicObjectUtils.setOf(selectRowsEntity, "id");
            getView().getPageCache().put("selectedEntryIds", SerializationUtils.toJsonString(pks));
        }
    }

    /**
     * 生成前端刷新指令前，调整参与绑定的精度等视图属性。
     * 直接 setEnable/setVisible 放 afterBindData；此时改字段会置数据修改标志。
     * 新建默认值和初始计算放 afterCreateNewData，本例只记录绑定前值。
     */
    @Override
    public void beforeBindData(EventObject e) {
        super.beforeBindData(e);
        // 本例只记录绑定前数据；新建赋值与直接控件状态分别放在对应事件。
        log.info("beforeBindData: billNo={}", getModel().getValue(FIELD_BILL_NO));
    }

    /**
     * 服务端数据绑定后，根据已有数据设置可见、可编辑等界面状态。
     * 此回调不证明浏览器已经完成渲染，不在此补初始化字段赋值。
     */
    @Override
    public void afterBindData(EventObject e) {
        super.afterBindData(e);
        // 设置可见/隐藏状态。
        getView().setVisible(true, KEY_1, KEY_2, KEY_3);
        // 设置可编辑/锁定状态。
        getView().setEnable(false, KEY_1, KEY_2, KEY_3);
    }

    /**
     * 触发时机: 单据复制后，新数据包初始化完毕。
     * - EventObject e: 通用事件参数。
     * 典型用途: 复制后清理字段（如单号、日期等不应被复制的字段）。
     */
    @Override
    public void afterCopyData(EventObject e) {
        super.afterCopyData(e);
        getModel().setValue(KEY_1, null);
        getModel().setValue(KEY_2, FILTER_VALUE_A);
    }

    // ===== 菜单/按钮事件 =====

    /**
     * 触发时机: 用户点击菜单项前（系统的菜单点击前置校验）。
     * - BeforeItemClickEvent evt: 包含菜单项信息。
     * - evt.getItemKey(): 获取菜单项标识。
     * - evt.setCancel(true): 取消菜单点击。
     * 典型用途: 菜单点击前校验，必要时取消菜单动作。
     */
    @Override
    public void beforeItemClick(BeforeItemClickEvent evt) {
        super.beforeItemClick(evt);
        String itemKey = evt.getItemKey();
        if (KEY_1.equals(itemKey)) {
            Object currentValue = getModel().getValue(KEY_1);
            if (currentValue == null) {
                evt.setCancel(true);
                getView().showErrorNotification(String.format(
                        ResManager.loadKDString("%s 不能为空", "FormPluginTemplate_0", RES_APP_ID),
                        KEY_1
                ));
            }
        } else if (KEY_2.equals(itemKey)) {
            getView().getPageCache().put("lastMenuKey", KEY_2);
        }
    }

    /**
     * 触发时机: 用户点击菜单项后（菜单点击已执行，触发自定义逻辑）。
     * - ItemClickEvent evt: 包含菜单项信息。
     * - evt.getItemKey(): 获取菜单项标识。
     * 典型用途: 处理菜单项的点击动作，如打开表单、列表、确认框等。
     */
    @Override
    public void itemClick(ItemClickEvent evt) {
        super.itemClick(evt);
        String itemKey = evt.getItemKey();
        if (KEY_1.equals(itemKey)) {
            // f7弹窗
            ListShowParameter lsp = ShowParameterUtils.getF7List(FORM_ID_F7, true);
            getView().showForm(lsp);
            // 普通单据/动态表单弹窗
            FormShowParameter fsp = ShowParameterUtils.getForm(FORM_ID_MODAL, OperationStatus.ADDNEW, ShowType.Modal, "500px", "300px");
            fsp.setCustomParam(CUSTOM_PARAM_KEY, CUSTOM_PARAM_VALUE);
            fsp.setCloseCallBack(new CloseCallBack(this, CLOSE_ACTION_ID));
            getView().showForm(fsp);
            // 确认框弹窗
            ConfirmCallBackListener confirmCallBackListener = new ConfirmCallBackListener(CONFIRM_CALLBACK_ID, this);
            this.getView().showConfirm(
                    ResManager.loadKDString("xxxxxx，请确认是否使用xxx功能", "FormPluginTemplate_1", RES_APP_ID),
                    MessageBoxOptions.YesNo,
                    confirmCallBackListener
            );
        } else if (KEY_2.equals(itemKey)) {
            getView().showTipNotification(String.format(
                    ResManager.loadKDString("点击了菜单：%s", "FormPluginTemplate_2", RES_APP_ID),
                    KEY_2
            ));
        }
    }

    // ===== 操作事件 =====

    /**
     * 触发时机: 用户点击 save、submit、audit 等操作前（系统校验前）。
     * - BeforeDoOperationEventArgs args: 操作前置事件参数。
     * - getOpKey(args): 获取操作类型（"save"、"submit"、"audit"、"reject" 等）。
     * - getOperate(args): 获取操作对象。
     * - getValue(fieldKey): 获取字段值。
     * - args.setCancel(true): 取消操作。
     * 典型用途: 业务前置校验、设置操作参数。
     * 建议: 简单校验用此事件；复杂逻辑优先使用校验器插件。
     */
    @Override
    public void beforeDoOperation(BeforeDoOperationEventArgs args) {
        super.beforeDoOperation(args);
        String opKey = getOpKey(args);
        if (KEY_1.equals(opKey)) {
            if (getValue(KEY_1) == null) {
                args.setCancel(true);
                getView().showErrorNotification(String.format(
                        ResManager.loadKDString("%s 未填写，不能执行操作", "FormPluginTemplate_3", RES_APP_ID),
                        KEY_1
                ));
            }
        } else if (KEY_2.equals(opKey)) {
            AbstractOperate operate = getOperate(args);
            OperateOption option = operate.getOption();
            option.setVariableValue(KEY_3, OPTION_VAR_VALUE);
            getView().getPageCache().put(PAGE_CACHE_OPERATE_KEY, opKey);
        }
    }

    /**
     * 触发时机: 表单操作（save、submit、audit 等）完成后。
     * - AfterDoOperationEventArgs args: 操作后置事件参数。
     * - getOpKey(args): 获取操作类型。
     * - args.getOperationResult(): 获取操作结果对象。
     * - result.isSuccess(): 判断操作是否成功。
     * 典型用途: 处理操作完成后的逻辑，如刷新列表、关闭表单、调用外部系统。
     */
    @Override
    public void afterDoOperation(AfterDoOperationEventArgs args) {
        super.afterDoOperation(args);
        String opKey = getOpKey(args);
        OperationResult operationResult = args.getOperationResult();
        if (KEY_1.equals(opKey) && operationResult.isSuccess()) {
            getView().showSuccessNotification(String.format(
                    ResManager.loadKDString("操作成功：%s", "FormPluginTemplate_4", RES_APP_ID),
                    KEY_1
            ));
        } else if (KEY_2.equals(opKey) && operationResult.isSuccess()) {
            getView().showTipNotification(String.format(
                    ResManager.loadKDString("操作完成：%s", "FormPluginTemplate_5", RES_APP_ID),
                    KEY_2
            ));
        }
    }

    // ===== 字段变化事件 =====

    /**
     * 触发时机: 用户修改表单字段值后（字段值已更新到模型）。
     * - e.getChangeSet() 返回发生改变的数据。通常本属性只返回一条数据，当批量触发字段值改变事件时，本属性会返回多条数据。
     * - PropertyChangedArgs e: 属性变更事件参数。
     * - ChangeData[] changeSet = e.getChangeSet(): 获取变更集合（通常一条，批量触发时可能多条）。
     * - String fieldKey = e.getProperty().getName(): 获取变更字段标识。
     * - 对每个 ChangeData change 读取 getRowIndex()、getNewValue()、getOldValue()；字段标识从 e.getProperty() 获取。
     * - 只有已确认集合恰含一条时才可使用 changeSet[0]；批量联动需覆盖完整集合。
     * 典型用途: 字段联动、级联更新、计算字段。
     * 建议: 简单联动优先用公式；复杂逻辑才在此处理；保持轻量以避免重查询。
     */
    @Override
    public void propertyChanged(PropertyChangedArgs e) {
        super.propertyChanged(e);
        // 字段联动：值改变后触发（保持轻量，避免重查询）。
        // 下例保留项目 helper 用法；适配批量联动前核对 helper 合同，并逐条处理完整变更集合。
        // 当前分录与父分录行号按实体结构选择，不能相互替代。
        String name = e.getProperty().getName();
        int changedRowIndex = getChangedRowIndex(e);
        // 父分录变更行 index。
        int parentChangedRowIndex = getParentChangedRowIndex(e);
        // 变更后值（按需使用）。
        Object changedNewValue = getChangedNewValue(e);
        // 变更前值（按需使用）。
        Object changedOldValue = getChangedOldValue(e);
        if (KEY_1.equals(name)) {
            Object value = getValue(KEY_1, changedRowIndex);
            getModel().setValue(KEY_2, value, parentChangedRowIndex);
        } else if (KEY_2.equals(name)) {
            getView().showTipNotification(String.format(
                    ResManager.loadKDString("字段 %1$s 已变更，新值=%2$s, 旧值=%3$s", "FormPluginTemplate_6", RES_APP_ID),
                    KEY_2,
                    changedNewValue,
                    changedOldValue
            ));
        }
    }

    // ===== 回调/弹框事件 =====

    /**
     * 触发时机: 用户在确认框（showConfirm）中选择 Yes 或 No 时。
     * - MessageBoxClosedEvent evt: 消息框关闭事件参数。
     * - evt.getCallBackId(): 获取回调 ID。
     * - evt.getResult(): 获取用户选择结果（Yes/No）。
     * 典型用途: 处理确认框的用户选择结果。
     */
    @Override
    public void confirmCallBack(MessageBoxClosedEvent evt) {
        super.confirmCallBack(evt);
        String callBackId = evt.getCallBackId();
        if (CONFIRM_CALLBACK_ID.equals(callBackId)) {
            if (MessageBoxResult.Yes.equals(evt.getResult())) {
                getView().showSuccessNotification(ResManager.loadKDString("用户已确认执行后续逻辑", "FormPluginTemplate_7", RES_APP_ID));
            }
        }
    }

    /**
     * 触发时机: 子表单/列表页面关闭时（被 showForm 打开的页面关闭）。
     * - ClosedCallBackEvent e: 关闭回调事件参数。
     * - e.getActionId(): 获取回调 ID。
     * - e.getReturnData(): 获取子页面返回的数据。
     * 典型用途: 处理子页面关闭后的逻辑，获取子页面返回的数据。
     */
    @Override
    public void closedCallBack(ClosedCallBackEvent e) {
        super.closedCallBack(e);
        // 子页面关闭回调。
        String actionId = e.getActionId();
        if (CLOSE_ACTION_ID.equals(actionId)) {
            this.getView().getPageCache().put(PAGE_CACHE_SUBMIT_FLAG, "false");
            String returnData = (String) e.getReturnData();
            // 字符串判空
            if (CharSequenceUtils.equals(RETURN_DATA_CONTINUE, returnData)) {
                this.getView().getPageCache().put(PAGE_CACHE_SUBMIT_FLAG, "true");
                String operateKey = this.getView().getPageCache().get(PAGE_CACHE_OPERATE_KEY);
                this.getView().invokeOperation(operateKey);
            }
        }
    }

    // ===== F7 过滤事件 =====

    /**
     * 触发时机: 用户点击基础资料 F7（基础资料/引用数据选择控件）下拉选择前。
     * - BeforeF7SelectEvent e: F7（基础资料/引用数据选择控件）选择前事件参数。
     * - e.getProperty().getName(): 获取字段标识。
     * - e.getCustomQFilters(): 获取自定义过滤条件列表，可添加新的过滤。
     * 典型用途: 为 F7（基础资料/引用数据选择控件）下拉添加过滤条件（如按部门、组织过滤）。
     */
    @Override
    public void beforeF7Select(BeforeF7SelectEvent e) {
        super.beforeF7Select(e);
        // F7（基础资料/引用数据选择控件）打开前设置过滤条件。
        String name = e.getProperty().getName();
        if (KEY_1.equals(name)) {
            List<QFilter> customQFilters = e.getCustomQFilters();
            QFilter newFilter = new QFilter(KEY_1, QCP.equals, FILTER_VALUE_A);
            customQFilters.add(newFilter);
        } else if (KEY_2.equals(name)) {
            e.getCustomQFilters().add(new QFilter(KEY_2, QCP.not_equals, "forbid"));
        }
    }

    // ===== 分录增删改事件 =====

    /**
     * 触发时机: 用户新增分录行后。
     * - AfterAddRowEventArgs e: 新增行后事件参数。
     * - e.getEntryProp(): 获取分录属性对象。
     * - e.getRowDataEntities(): 获取本次实际新增行集合，逐行用 getRowIndex() 初始化。
     * - e.getInsertRow(): 插入位置上下文，普通追加/批量事件可为 -1，不作为新增行号。
     * 典型用途: 新增行后的初始化逻辑（如设置默认值）。
     */
    @Override
    public void afterAddRow(AfterAddRowEventArgs e) {
        super.afterAddRow(e);
        for (RowDataEntity row : e.getRowDataEntities()) {
            int rowIndex = row.getRowIndex();
            getModel().setValue(KEY_1, 1, rowIndex);
            getModel().setValue(KEY_2, FILTER_VALUE_A, rowIndex);
        }
    }

    /**
     * 触发时机: 用户删除分录行后。
     * - AfterDeleteRowEventArgs e: 删除行后事件参数。
     * - e.getRowIndexs(): 获取被删分录行的索引集合（int[]）。
     * 典型用途: 删除行后的清理逻辑（如重新计算合计）。
     */
    @Override
    public void afterDeleteRow(AfterDeleteRowEventArgs e) {
        super.afterDeleteRow(e);
        int[] rowIndexs = e.getRowIndexs();
        getView().showTipNotification(String.format(
                ResManager.loadKDString("已删除了：%s行分录", "FormPluginTemplate_8", RES_APP_ID),
                rowIndexs.length
        ));
    }

    /**
     * 触发时机: 用户清空分录所有行后。
     * - AfterDeleteEntryEventArgs e: 清空分录后事件参数。
     * - e.getEntryKey(): 获取分录标识。
     * 典型用途: 清空分录后的处理逻辑。
     */
    @Override
    public void afterDeleteEntry(AfterDeleteEntryEventArgs e) {
        super.afterDeleteEntry(e);
        getModel().setValue(KEY_3, 0);
    }

}