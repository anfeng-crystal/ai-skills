package com.example.kingdee;

import java.net.URI;
import java.util.Locale;

public final class CosmicTestHarness {
    private CosmicTestHarness() {
    }

    public static FakeRequestContext defaultContext() {
        return new FakeRequestContext(10001L, 20001L, "dev");
    }

    public static void assertNonProductionUrl(String url) {
        URI uri = URI.create(url);
        String host = uri.getHost() == null ? "" : uri.getHost().toLowerCase(Locale.ROOT);
        if (host.contains("prod") || host.contains("production")) {
            throw new IllegalArgumentException("Production-like URL is not allowed in the test harness: " + host);
        }
    }
}
