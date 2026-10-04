/** Validate discovery metadata, not WebSocket reachability or browser identity. */
export async function readCdpVersion(response) {
  try {
    const payload = await response.json();
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)
      || typeof payload.webSocketDebuggerUrl !== 'string') throw new Error();
    const ws = payload.webSocketDebuggerUrl;
    const url = new URL(ws);
    // WebSocket URLs cannot contain a fragment, including an empty '#'.
    if (!['ws:', 'wss:'].includes(url.protocol) || url.href.includes('#')) throw new Error();
    return { ok: true, ws, browser: payload.Browser || null };
  } catch {
    // JSON parser messages may include response content; never echo that body.
    return { ok: false, reason: 'invalid_cdp_response' };
  }
}
