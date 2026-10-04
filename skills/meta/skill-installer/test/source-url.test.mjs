import test from "node:test";
import assert from "node:assert/strict";
import path from "node:path";
import { parseSourceUrl } from "../src/meta.mjs";

const repoUrl = "https://github.com/offline/fixture";
const gitSource = (branch = "main", skillPath = null) => ({
  type: "git", url: repoUrl, path: skillPath, branch,
});

test("raw SKILL.md source resolves to its repository and containing directory", () => {
  assert.deepEqual(
    parseSourceUrl("https://raw.githubusercontent.com/offline/fixture/main/packs/demo/SKILL.md"),
    gitSource("main", "packs/demo"),
  );
});

test("raw source preserves an explicit single-segment branch", () => {
  assert.deepEqual(
    parseSourceUrl("https://raw.githubusercontent.com/offline/fixture/release-v2/demo/SKILL.md"),
    gitSource("release-v2", "demo"),
  );
});

test("repository and tree sources retain their established result shapes", () => {
  assert.deepEqual(parseSourceUrl(repoUrl), gitSource());
  assert.deepEqual(parseSourceUrl(`${repoUrl}/`), gitSource());
  assert.deepEqual(parseSourceUrl(`${repoUrl}/tree/release-v2/packs/demo`),
    gitSource("release-v2", "packs/demo"));
});

test("queries and fragments are excluded from repository, ref and directory", () => {
  assert.deepEqual(parseSourceUrl(`${repoUrl}?tab=readme#overview`), gitSource());
  assert.deepEqual(parseSourceUrl(`${repoUrl}/tree/main/packs/demo?plain=1#readme`),
    gitSource("main", "packs/demo"));
  assert.deepEqual(
    parseSourceUrl("https://raw.githubusercontent.com/offline/fixture/main/demo/SKILL.md?token=synthetic#example"),
    gitSource("main", "demo"),
  );
});

test("local source paths remain local even when they contain GitHub-looking text", () => {
  for (const input of ["/tmp/skill", "./fixture", "../fixture", "./github.com/offline/fixture"]) {
    assert.deepEqual(parseSourceUrl(input), { type: "local", url: path.resolve(input) });
  }
});

test("non-string and unsupported sources return null", () => {
  for (const input of [null, undefined, "", 42, {}, [], "fixture", "not a URL"]) {
    assert.equal(parseSourceUrl(input), null);
  }
});

test("only documented HTTPS GitHub hosts without credentials are remote sources", () => {
  for (const input of [
    "http://github.com/offline/fixture",
    "ssh://github.com/offline/fixture",
    "https://evilgithub.com/offline/fixture",
    "https://github.com.example/offline/fixture",
    "https://example.test/github.com/offline/fixture",
    "https://github.com@other.test/offline/fixture",
    "https://user:synthetic@github.com/offline/fixture",
    "https://github.com:8443/offline/fixture",
    "https://raw.githubusercontent.com.example/offline/fixture/main/demo/SKILL.md",
    "http://raw.githubusercontent.com/offline/fixture/main/demo/SKILL.md",
    "https://user:synthetic@raw.githubusercontent.com/offline/fixture/main/demo/SKILL.md",
  ]) {
    assert.equal(parseSourceUrl(input), null, input);
  }
});

test("malformed and unconfirmed remote path forms do not become fallback repositories", () => {
  for (const input of [
    "https://github.com/offline",
    `${repoUrl}/blob/main/demo/SKILL.md`,
    `${repoUrl}/tree/`,
    `${repoUrl}/tree/main/`,
    `${repoUrl}/tree/main//demo`,
    `${repoUrl}/tree/release%2Fv2/demo`,
    "https://raw.githubusercontent.com/offline/fixture/main/SKILL.md",
    "https://raw.githubusercontent.com/offline/fixture/main/demo/README.md",
    "https://raw.githubusercontent.com/offline/fixture/main//SKILL.md",
    "https://raw.githubusercontent.com/offline/fixture/release%2Fv2/demo/SKILL.md",
  ]) {
    assert.equal(parseSourceUrl(input), null, input);
  }
});
