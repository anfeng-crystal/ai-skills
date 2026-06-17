package com.example.kingdee;

public final class FakeRequestContext {
    private final long userId;
    private final long orgId;
    private final String tenantId;

    public FakeRequestContext(long userId, long orgId, String tenantId) {
        this.userId = userId;
        this.orgId = orgId;
        this.tenantId = tenantId;
    }

    public long getUserId() {
        return userId;
    }

    public long getOrgId() {
        return orgId;
    }

    public String getTenantId() {
        return tenantId;
    }
}
