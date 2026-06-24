import assert from "node:assert/strict";
import test from "node:test";

import { KeyPool } from "../src/key-pool.js";

test("rotates provider keys independently in round-robin order", () => {
  const pool = new KeyPool("brave", ["k1", "k2"], () => 1_000);

  assert.equal(pool.next()?.value, "k1");
  assert.equal(pool.next()?.value, "k2");
  assert.equal(pool.next()?.value, "k1");
});

test("cools down a rate-limited key and disables unauthorized keys", () => {
  let now = 1_000;
  const pool = new KeyPool("exa", ["k1", "k2"], () => now);

  const first = pool.next();
  assert.equal(first?.value, "k1");
  pool.cooldown(first!, 5_000);

  assert.equal(pool.next()?.value, "k2");
  now = 6_001;
  assert.equal(pool.next()?.value, "k1");

  const disabled = pool.next();
  assert.equal(disabled?.value, "k2");
  pool.disable(disabled!, "unauthorized");
  assert.equal(pool.status().disabledCount, 1);
  assert.equal(pool.next()?.value, "k1");
});

test("recovers disabled keys at the next calendar month", () => {
  let now = new Date(2026, 5, 17).getTime();
  const pool = new KeyPool("tavily", ["k1"], () => now);

  const lease = pool.next();
  assert.equal(lease?.value, "k1");
  pool.disable(lease!, "unauthorized");

  assert.equal(pool.status().disabledCount, 1);
  assert.equal(pool.next(), undefined);

  now = new Date(2026, 6, 1).getTime();
  assert.equal(pool.status().disabledCount, 0);
  assert.equal(pool.next()?.value, "k1");
});
