import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const inspector = fileURLToPath(new URL("./inspect-skill.mjs", import.meta.url));

test("detects Python standard-library HTTP clients", () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "skill-vetter-network-"));
  fs.writeFileSync(
    path.join(root, "SKILL.md"),
    "---\nname: network-demo\ndescription: \"Network demo.\"\n---\n\n# Network Demo\n",
    "utf8",
  );
  fs.writeFileSync(
    path.join(root, "client.py"),
    "from urllib.request import Request, build_opener\nrequest = Request('https://example.invalid')\n",
    "utf8",
  );

  const result = spawnSync(process.execPath, [inspector, "--path", root, "--json"], { encoding: "utf8" });
  assert.equal(result.status, 0, result.stdout + result.stderr);
  const report = JSON.parse(result.stdout);
  assert.equal(report.recommendation, "review_needed");
  assert.ok(report.findings.some((finding) => finding.category === "network_access"));
  assert.ok(report.networkDbAccess.some((item) => item === "client.py:1"));
});
