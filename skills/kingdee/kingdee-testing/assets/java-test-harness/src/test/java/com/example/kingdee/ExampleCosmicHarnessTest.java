package com.example.kingdee;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

class ExampleCosmicHarnessTest {
    @Test
    void defaultContextHasDevTenant() {
        FakeRequestContext context = CosmicTestHarness.defaultContext();

        assertEquals("dev", context.getTenantId());
    }

    @Test
    void productionLikeUrlIsRejected() {
        assertThrows(IllegalArgumentException.class,
                () -> CosmicTestHarness.assertNonProductionUrl("https://prod.example.com/ierp"));
    }
}
