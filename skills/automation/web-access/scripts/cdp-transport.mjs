import { assertAllowedHost, assertAllowedWsUrl } from "./cdp-cli-options.mjs";

export async function getBrowserEndpoint(endpoint, wsUrlOverride) {
  if (wsUrlOverride) {
    assertAllowedWsUrl(wsUrlOverride);
    return {
      browserWSEndpoint: wsUrlOverride,
      source: "explicit_ws_url",
    };
  }

  assertAllowedHost(endpoint.host);
  let response;
  try {
    response = await fetch(`${endpoint.base}/json/version`, {
      signal: AbortSignal.timeout(2000),
    });
  } catch (error) {
    throw new Error(
      `Failed to reach CDP version endpoint at ${endpoint.base}/json/version: ${
        error instanceof Error ? error.message : "unknown_error"
      }`,
    );
  }

  if (!response.ok) {
    throw new Error(`Failed to reach /json/version: HTTP ${response.status}`);
  }

  const payload = await response.json();
  return {
    browserWSEndpoint: payload.webSocketDebuggerUrl || null,
    browser: payload.Browser || null,
    protocolVersion: payload["Protocol-Version"] || null,
    source: "http_version_endpoint",
  };
}

export async function listTargets(endpoint) {
  assertAllowedHost(endpoint.host);
  let response;
  try {
    response = await fetch(`${endpoint.base}/json/list`, {
      signal: AbortSignal.timeout(2000),
    });
  } catch (error) {
    throw new Error(
      `Failed to reach CDP list endpoint at ${endpoint.base}/json/list: ${
        error instanceof Error ? error.message : "unknown_error"
      }`,
    );
  }

  if (!response.ok) {
    throw new Error(`Failed to reach /json/list: HTTP ${response.status}`);
  }

  return response.json();
}

function resolveTarget(targets, query) {
  const normalized = String(query || "").trim();
  if (!normalized) {
    throw new Error("Target is required.");
  }

  return (
    targets.find((target) => String(target.id).startsWith(normalized)) ||
    targets.find((target) => target.url === normalized) ||
    targets.find(
      (target) =>
        String(target.url || "").includes(normalized) ||
        String(target.title || "").includes(normalized),
    ) ||
    null
  );
}

let cdpRequestCounter = 1;
export function nextCdpRequestId() {
  const id = cdpRequestCounter;
  cdpRequestCounter += 1;
  if (cdpRequestCounter > 2_000_000_000) {
    cdpRequestCounter = 1;
  }
  return id;
}

export async function sendCdpCommand(webSocketUrl, method, params = {}, timeout = 5000, id = nextCdpRequestId()) {
  assertAllowedWsUrl(webSocketUrl);

  return new Promise((resolve, reject) => {
    const socket = new WebSocket(webSocketUrl);
    let settled = false;
    const finish = (error, result) => {
      if (settled) return;
      // Settle before close(): it can synchronously emit another terminal event.
      settled = true;
      clearTimeout(timer);
      try {
        socket.close();
      } catch {}
      if (error) reject(error);
      else resolve(result);
    };
    const timer = setTimeout(() => {
      finish(new Error(`CDP request timed out after ${timeout}ms`));
    }, timeout);

    socket.addEventListener("open", () => {
      if (settled) return;
      try {
        socket.send(JSON.stringify({ id, method, params }));
      } catch (error) {
        finish(error);
      }
    });

    socket.addEventListener("message", (event) => {
      if (settled) return;
      try {
        const payload = JSON.parse(String(event.data));
        if (payload.id !== id) {
          return;
        }
        if (payload.error) {
          finish(new Error(JSON.stringify(payload.error)));
          return;
        }
        finish(null, payload.result ?? null);
      } catch (error) {
        finish(error);
      }
    });

    socket.addEventListener("error", () => {
      finish(new Error("WebSocket connection failed."));
    });

    socket.addEventListener("close", () => {
      finish(new Error("WebSocket closed before CDP response."));
    });
  });
}

export async function resolveTargetSession(endpoint, targetQuery) {
  const targets = await listTargets(endpoint);
  const target = resolveTarget(targets, targetQuery);
  if (!target?.webSocketDebuggerUrl) {
    throw new Error(`Target not found or not attachable: ${targetQuery}`);
  }
  return { target, wsUrl: target.webSocketDebuggerUrl };
}

export async function openTarget(endpoint, url) {
  assertAllowedHost(endpoint.host);
  let response;
  try {
    response = await fetch(`${endpoint.base}/json/new?${encodeURIComponent(url)}`, {
      method: "PUT",
      signal: AbortSignal.timeout(2000),
    });
  } catch (error) {
    throw new Error(
      `Failed to reach CDP open endpoint at ${endpoint.base}/json/new: ${
        error instanceof Error ? error.message : "unknown_error"
      }`,
    );
  }

  if (!response.ok) {
    throw new Error(`Failed to open new target: HTTP ${response.status}`);
  }

  return response.json();
}

export async function closeTarget(endpoint, targetId) {
  assertAllowedHost(endpoint.host);
  const response = await fetch(`${endpoint.base}/json/close/${targetId}`, {
    signal: AbortSignal.timeout(2000),
  });
  if (!response.ok) {
    throw new Error(`Failed to close target: HTTP ${response.status}`);
  }
  return response.text();
}
