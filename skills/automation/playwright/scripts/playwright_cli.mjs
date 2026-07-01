#!/usr/bin/env node

/**
 * Cross-platform wrapper around the Playwright CLI package.
 */

import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const args = process.argv.slice(2);
const hasSessionFlag = args.some((arg) => arg === "--session" || arg.startsWith("--session="));
const isShortLivedCommand = args.some((arg) => arg === "--help" || arg === "-h" || arg === "help");
const timeoutMs = Number(process.env.PLAYWRIGHT_CLI_TIMEOUT_MS || (isShortLivedCommand ? 30_000 : 0));
const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPT_DIR, "../../../..");
const localCliScript = path.join(REPO_ROOT, "node_modules", "@playwright", "cli", "playwright-cli.js");
const hasLocalCli = fs.existsSync(localCliScript);
const npxCommand = process.platform === "win32" ? "npx.cmd" : "npx";
const npxArgs = ["--yes", "--package", "@playwright/cli", "playwright-cli"];
const localArgs = hasLocalCli ? [localCliScript] : [];
const childEnv = {
  ...process.env,
  npm_config_cache: process.env.npm_config_cache || path.join(REPO_ROOT, ".npm-cache"),
  npm_config_update_notifier: process.env.npm_config_update_notifier || "false",
};

if (!hasSessionFlag && process.env.PLAYWRIGHT_CLI_SESSION) {
  npxArgs.push("--session", process.env.PLAYWRIGHT_CLI_SESSION);
  localArgs.push("--session", process.env.PLAYWRIGHT_CLI_SESSION);
}
npxArgs.push(...args);
localArgs.push(...args);

const npxResult = await runCli(npxCommand, npxArgs, { captureStderr: hasLocalCli, timeoutMs });
if (npxResult.ok) {
  process.exit(npxResult.code ?? 0);
}

if (hasLocalCli && shouldFallbackToLocal(npxResult)) {
  console.error("Warning: npx failed to resolve Playwright CLI; falling back to local node_modules.");
  const localResult = await runCli(process.execPath, localArgs, { captureStderr: false, timeoutMs });
  process.exit(localResult.code ?? (localResult.ok ? 0 : 1));
}

if (!hasLocalCli && shouldFallbackToLocal(npxResult)) {
  console.error('Error: no local Playwright CLI found. Run "node scripts/npm-deps.mjs install" while online, then retry.');
}

process.exit(npxResult.code ?? 1);

function runCli(command, cliArgs, options) {
  return new Promise((resolve) => {
    const child = spawn(command, cliArgs, {
      env: childEnv,
      stdio: ["inherit", "inherit", options.captureStderr ? "pipe" : "inherit"],
    });
    let timedOut = false;
    let stderr = "";
    const timeout = options.timeoutMs > 0
      ? setTimeout(() => {
          timedOut = true;
          child.kill(process.platform === "win32" ? undefined : "SIGTERM");
        }, options.timeoutMs)
      : null;

    if (child.stderr) {
      child.stderr.on("data", (chunk) => {
        const text = chunk.toString();
        stderr += text;
        process.stderr.write(chunk);
      });
    }

    child.on("error", (error) => {
      if (timeout) {
        clearTimeout(timeout);
      }
      resolve({ ok: false, code: 1, signal: null, stderr, error, timedOut });
    });

    child.on("exit", (code, signal) => {
      if (timeout) {
        clearTimeout(timeout);
      }
      if (timedOut) {
        resolve({ ok: false, code: 124, signal, stderr, timedOut: true });
        return;
      }
      if (signal) {
        process.kill(process.pid, signal);
        return;
      }
      resolve({ ok: code === 0, code: code ?? 0, signal, stderr, timedOut: false });
    });
  });
}

function shouldFallbackToLocal(result) {
  if (result.timedOut && isShortLivedCommand) {
    return true;
  }
  if (result.error) {
    return true;
  }
  return /\bnpm error\b|ECONNRESET|ETIMEDOUT|ENOTFOUND|EAI_AGAIN|EACCES|EPERM|network|registry\.npmjs\.org|cache folder|could not determine executable/i.test(result.stderr || "");
}
