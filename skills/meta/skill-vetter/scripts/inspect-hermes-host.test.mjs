import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const inspector = process.env.SKILL_VETTER_SCRIPT || fileURLToPath(new URL("./inspect-skill.mjs", import.meta.url));

function fixture(t, source, { entry = false } = {}) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "vetter-hermes-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  fs.writeFileSync(path.join(root, "SKILL.md"), "---\nname: demo\ndescription: Demo\n---\n" + (entry ? source : ""));
  if (!entry) fs.writeFileSync(path.join(root, "setup.sh"), source);
  return root;
}

function inspect(root, { json = true, strict = true } = {}) {
  const run = spawnSync(process.execPath, [inspector, "--path", root, ...(json ? ["--json"] : []), ...(strict ? ["--strict"] : [])], {
    encoding: "utf8", timeout: 5000,
  });
  assert.equal(run.error, undefined);
  assert.ok([0, 2].includes(run.status), run.stdout + run.stderr);
  return { ...run, report: json ? JSON.parse(run.stdout) : null };
}

for (const [name, source] of [
  ["home variable", 'mkdir -p "$HOME/.hermes/skills/demo"\n'],
  ["tilde", "mkdir -p ~/.hermes/skills/demo\n"],
  ["absolute POSIX path", "mkdir -p /opt/agent/.hermes/skills/demo\n"],
  ["relative path", "mkdir -p .hermes/skills/demo\n"],
  ["host skills directory itself", "mkdir -p .hermes/skills\n"],
  ["Windows separators", 'New-Item -ItemType Directory "$env:USERPROFILE\\.hermes\\skills\\demo"\n'],
  ["escaped Windows separators", 'const destination = "C:\\\\agent\\\\.hermes\\\\skills\\\\demo";\n'],
]) {
  test(`Hermes ${name} is a host integration requiring review`, (t) => {
    const root = fixture(t, source);
    const { status, report } = inspect(root);
    assert.equal(status, 2);
    assert.equal(report.recommendation, "review_needed");
    assert.deepEqual(report.hostTargetsDetected, ["hermes"]);
    assert.deepEqual(report.filesystemWrites, ["setup.sh:1"]);
    assert.ok(report.findings.some(f => f.category === "host_integration" && f.severity === "high" && f.line === 1));
    assert.ok(report.manualReview.some(item => item.includes("hermes")));
  });
}

test("Hermes instructions retain their SKILL.md location in JSON and human output", (t) => {
  const root = fixture(t, 'mkdir -p "$HOME/.hermes/skills/demo"\n', { entry: true });
  const { status, report } = inspect(root, { strict: false });
  assert.equal(status, 0);
  assert.equal(report.recommendation, "review_needed");
  assert.deepEqual(report.filesystemWrites, ["SKILL.md:5"]);
  const human = inspect(root, { json: false });
  assert.equal(human.status, 2);
  assert.match(human.stdout, /Recommendation: review_needed/);
  assert.match(human.stdout, /Host targets: hermes/);
  assert.match(human.stdout, /host_integration SKILL\.md:5/);
});

test("Hermes host evidence retains destructive severity and credential redaction", (t) => {
  const root = fixture(t, 'rm -rf "$HOME/.hermes/skills/api_key=FAKE_HERMES_SENTINEL"\n');
  const { status, report, stdout, stderr } = inspect(root);
  assert.equal(status, 2);
  assert.equal(report.recommendation, "block");
  assert.deepEqual(report.hostTargetsDetected, ["hermes"]);
  assert.deepEqual(report.filesystemWrites, ["setup.sh:1"]);
  assert.deepEqual(report.destructiveOps, ["setup.sh:1"]);
  assert.deepEqual(report.secretHits, ["setup.sh:1"]);
  assert.doesNotMatch(stdout + stderr, /FAKE_HERMES_SENTINEL/);
});

test("existing named host detection remains intact in a multi-host script", (t) => {
  const root = fixture(t, ["codex", "claude", "agents", "junie", "hermes"].map(host => `mkdir -p "$HOME/.${host}/skills/demo"`).join("\n"));
  const { report } = inspect(root);
  assert.equal(report.recommendation, "review_needed");
  assert.deepEqual(report.hostTargetsDetected, ["codex", "claude", "agents", "junie", "hermes"]);
  assert.deepEqual(report.filesystemWrites, [1, 2, 3, 4, 5].map(line => `setup.sh:${line}`));
});

for (const name of ["skills-cache", "skills_backup", "skills.json", "skillset", "config.yaml"]) {
  test(`Hermes ${name} is not the host skills directory`, (t) => {
    const root = fixture(t, `mkdir -p .hermes/${name}\n`);
    const { status, report } = inspect(root);
    assert.equal(status, 0);
    assert.equal(report.recommendation, "allow");
    assert.deepEqual(report.hostTargetsDetected, []);
    assert.deepEqual(report.filesystemWrites, []);
  });
}
