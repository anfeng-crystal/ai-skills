package kd.cd.common.snippets;

import kd.bos.dataentity.OperateOption;
import kd.bos.dataentity.entity.DynamicObject;
import kd.bos.dlock.DLock;
import kd.bos.entity.operate.result.OperationResult;
import kd.bos.logging.Log;
import kd.bos.logging.LogFactory;
import kd.bos.mq.MessageAcker;
import kd.bos.mq.MessageConsumer;
import kd.bos.servicehelper.BusinessDataServiceHelper;
import kd.bos.servicehelper.operation.OperationServiceHelper;
import kd.bos.servicehelper.operation.SaveServiceHelper;
import kd.cd.common.operate.OpUtils;

/**
 * MQ 消费模板：A 为 String[]{固定单据标识, 正整数Long主键}，B 为消息池Long主键或十进制字符串。
 * 两种载荷用于演示两个场景；实际队列应固定一种消息合同。
 *
 * 部署前核对实体/字段/操作和 XML，补齐 businessScope、isOperationCompleted、callExternalApi。
 * 未实现的业务钩子会失败并进入重试决策，不会伪造业务成功；未补齐前不要启用消费者。
 * OpUtils 是项目 commons 封装，不属于标品 SDK。
 *
 * DLock 只控制并发；持久状态和远端幂等键处理重投。示例每个主键只执行一次业务动作；
 * 同一单据需多次执行时改用发送方持久事件ID，并同步调整幂等台账和远端协议。
 * 重试次数、退避、最终失败记录和恢复入口由目标队列/业务方案提供，不能从 deny 推定。
 */
public class SampleMQConsumer implements MessageConsumer {
    private static final Log log = LogFactory.getLog(SampleMQConsumer.class);
    // 均为示例元数据，使用前替换为已经核验的固定业务合同，不能任意接受消息传入的实体。
    private static final String OPERATION_ENTITY = "kdcd_sample_bill";
    private static final String POOL_ENTITY = "kdcd_api_message_pool";

    private enum Decision { ACK, RETRY, DISCARD }

    @Override
    public void onMessage(Object message, String messageId, boolean resend, MessageAcker acker) {
        Decision decision;
        try {
            if (message instanceof String[]) {
                String[] fields = (String[]) message;
                if (fields.length != 2 || !OPERATION_ENTITY.equals(fields[0])) {
                    throw new InvalidMessageException("operation-contract-mismatch");
                }
                decision = consumeOperationMessage(parsePk(fields[1]));
            } else {
                decision = consumeWithDLock(parsePk(message));
            }
        } catch (InvalidMessageException e) {
            // 仅本地载荷校验生成此异常；不把业务层的 IllegalArgumentException 当成永久无效。
            log.warn("MQ 永久无效：messageId={}, reason={}", messageId, e.getMessage());
            decision = Decision.DISCARD;
        } catch (RuntimeException e) {
            // 读取/锁/远端/保存失败均未证明业务永久失败。日志不输出原始消息或远端异常正文。
            log.warn("MQ 处理未完成：messageId={}, type={}", messageId, e.getClass().getName());
            decision = Decision.RETRY;
        }

        // 应答在业务异常边界外：ack 失败不能反写失败状态，也不能再调用同一 acker 的 deny。
        // 应答异常向上传播；是否重投需以目标 MQ 实现和运行证据确认。
        if (decision == Decision.ACK) {
            acker.ack(messageId);
        } else if (decision == Decision.DISCARD) {
            acker.discard(messageId);
        } else {
            acker.deny(messageId);
        }
    }

    private static Long parsePk(Object value) {
        String text;
        if (value instanceof Long) {
            text = value.toString();
        } else if (value instanceof String) {
            text = (String) value;
        } else {
            throw new InvalidMessageException("unsupported-pk-type");
        }
        if (!text.matches("[1-9][0-9]{0,18}")) {
            throw new InvalidMessageException("invalid-positive-long-pk");
        }
        try {
            return Long.valueOf(text);
        } catch (NumberFormatException e) {
            throw new InvalidMessageException("pk-out-of-range");
        }
    }

    /** 场景 A：串行检查持久完成状态，再执行固定 audit 操作。 */
    private Decision consumeOperationMessage(Long pk) {
        String key = scopedKey("audit:" + OPERATION_ENTITY, pk);
        try (DLock lock = DLock.create(key)) {
            if (!lock.tryLock()) {
                return Decision.RETRY;
            }
            if (isOperationCompleted(pk)) {
                return Decision.ACK;
            }
            OperationResult result = OperationServiceHelper.executeOperate(
                    "audit", OPERATION_ENTITY, new Long[]{pk}, OperateOption.create());
            if (result.isSuccess()) {
                return Decision.ACK;
            }

            // 先记录失败，再按经确认的业务错误分类决定去向；isSuccess()==false 本身不支持 discard。
            DynamicObject bill = BusinessDataServiceHelper.loadSingle(pk, "kdcd_errmsg", OPERATION_ENTITY);
            if (bill == null) {
                throw new IllegalStateException("operation-bill-not-found");
            }
            bill.set("kdcd_errmsg", OpUtils.getCompleteFailMsg(result));
            SaveServiceHelper.update(bill);
            if (isPermanentOperationFailure(result)) {
                log.warn("MQ 操作永久失败已记录：key={}", key);
                return Decision.DISCARD;
            }
            return Decision.RETRY;
        }
    }

    /** 场景 B：消息池完成状态防止已落库成功的业务再次执行。 */
    private Decision consumeWithDLock(Long pk) {
        String key = scopedKey("external:" + POOL_ENTITY, pk);
        try (DLock lock = DLock.create(key)) {
            if (!lock.tryLock()) {
                return Decision.RETRY;
            }
            DynamicObject bill = BusinessDataServiceHelper.loadSingle(pk, "kdcd_status", POOL_ENTITY);
            if (bill == null) {
                // 未找到可能是可见性/路由/时序问题，没有永久失败依据时保留消息。
                throw new IllegalStateException("message-pool-bill-not-found");
            }
            if ("1".equals(bill.getString("kdcd_status"))) {
                return Decision.ACK;
            }
            // 远端成功但本地保存失败会重投；远端须按同一 key 去重或提供可查询的最终结果。
            boolean success = callExternalApi(bill, key);
            bill.set("kdcd_status", success ? "1" : "-1");
            SaveServiceHelper.update(bill);
            return success ? Decision.ACK : Decision.RETRY;
        }
    }

    private String scopedKey(String businessType, Long pk) {
        String scope = businessScope();
        if (scope == null || scope.trim().isEmpty()) {
            throw new IllegalStateException("missing-business-scope");
        }
        return scope + ":" + businessType + ":" + pk;
    }

    /** 返回已核验的稳定环境/租户/账套标识组合；不能使用投递 messageId 或用户输入作为作用域。 */
    protected String businessScope() {
        throw new UnsupportedOperationException("configure-business-scope");
    }

    /**
     * 读取 audit 操作持久化的最终状态。返回 true 表示该业务动作已完成；
     * 返回 false 前须保证操作成功会持久化可供下次检查的结果，或操作本身具备已核验幂等性。
     */
    protected boolean isOperationCompleted(Long pk) {
        throw new UnsupportedOperationException("implement-operation-completion-check");
    }

    /** 只按目标业务的结构化错误码分类；未知结果默认重试，不凭错误文本或异常类名猜测。 */
    protected boolean isPermanentOperationFailure(OperationResult result) {
        return false;
    }

    /**
     * 对接实际外部接口：传递稳定 idempotencyKey，只在确认远端最终成功时返回 true。
     * false 代表当前可重试失败；超时结果不明须查询或使用同一幂等键恢复，不能直接当失败重做。
     * 本方法是明确未实现的占位，不进行真实外部调用。
     */
    protected boolean callExternalApi(DynamicObject bill, String idempotencyKey) {
        throw new UnsupportedOperationException("implement-idempotent-external-call");
    }

    private static final class InvalidMessageException extends RuntimeException {
        private static final long serialVersionUID = 1L;
        private InvalidMessageException(String reason) {
            super(reason);
        }
    }

    // 配套资源：sample_mq.xml；本地配置示例为 mqConfigFiles.config=sample_mq.xml。
    // 环境上按已确认的 MC 配置和打包路径加载，不覆盖已有配置；消费者类须与实际实现一致。
    // getRouteKey 默认不重写；若发送数据库事务消息且跨库，按消费方真实数据库路由重写 public 方法。
    // 发布时 region/queue 与 XML 一致，选择一种发布方式，最后必须关闭：
    // MessagePublisher publisher = MQFactory.get().createSimplePublisher(region, queue);
    // try {
    //     publisher.publish(message); // 普通消息
    //     // 或 publisher.publishDelay(message, seconds); // 延迟，SDK文档范围5..7200秒
    //     // 或 publisher.publishInDbTranscation(routeKey, message); // 已建立业务数据库事务，核对routeKey
    // } finally {
    //     publisher.close();
    // }
}
