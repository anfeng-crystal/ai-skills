#!/usr/bin/env node

import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { pathToFileURL } from "node:url";

const TYPE_RULES = [
	["修复", /修复|排查|解决.{0,8}(?:错误|异常|故障|问题)|报错|故障|回归|崩溃|卡顿|不生效|\b(?:fix|debug|bug|error|failure|crash|regression)\b/iu],
	["发布", /发布|上线|部署|打包|构建发布|版本发布|\b(?:release|deploy|publish|ship)\b/iu],
	["优化", /优化|改善|提升|重构|精简|性能|体验|\b(?:optimi[sz]e|improve|refactor|performance)\b/iu],
	["设计", /设计|架构|方案|数据模型|接口设计|规划|\b(?:design|architecture|architect|plan)\b/iu],
	["探索", /探索|实验|原型|可行性|概念验证|\bPOC\b|\b(?:experiment|prototype|feasibility)\b/iu],
	["文档", /文档|说明书|使用说明|指南|教程|\bREADME\b|\b(?:docs?|documentation|guide)\b/iu],
	["研究", /研究|调研|对比|比较|评估|选型|分析|为什么|如何|怎么|用来做什么|\b(?:research|compare|evaluate|assess|investigate)\b/iu],
	["功能", /新增|添加|实现|开发|创建|支持|接入|增加|做成|\b(?:add|build|create|implement|support|integrate)\b/iu],
];

export function isSubstantive(prompt) {
	const text = String(prompt ?? "").normalize("NFKC").trim();
	if (!text || /^(?:你好|您好|嗨|hi|hello|hey|谢谢|好的|收到|ok|okay)[!！,.，。\s]*$/iu.test(text)) return false;
	if (/^\/(?:help|resume|clear|config|hooks|status|model|permissions)\b/iu.test(text)) return false;
	if (/^(?:\[(?:image|file|attachment)[^\]]*\]\s*)+$/iu.test(text)) return false;
	return [...text].length >= 4;
}

export function classify(prompt) {
	for (const [type, pattern] of TYPE_RULES) if (pattern.test(prompt)) return type;
	return null;
}

function compactTopic(prompt, type) {
	let text = String(prompt)
		.normalize("NFKC")
		.replace(/\[([^\]]+)\]\([^)]+\)/gu, "$1")
		.replace(/https?:\/\/\S+/giu, " ")
		.split(/\r?\n/gu)
		.map((line) => line.replace(/^\s*(?:[-*#>]|\d+[.)、])\s*/u, "").trim())
		.find((line) => line && !/^\[(?:image|file|attachment)/iu.test(line));
	if (!text) return null;

	text = text
		.replace(/^(?:目前|现在|这个项目|根据(?:这个|上述)?对话|请|麻烦|帮我|帮忙|需要|我想|我要|能否|可以)\s*/u, "")
		.replace(/^(?:新增|添加|实现|开发|创建|支持|接入|修复|排查|解决|优化|改善|提升|重构|精简|设计|规划|发布|上线|部署|探索|实验|验证|编写|整理|更新|研究|调研|对比|比较|评估|分析)\s*/u, "")
		.split(/[。！？!?；;：:\n]/u)[0]
		.replace(/^(?:当前|所有|一下|一个)\s*/u, "")
		.replace(new RegExp(`(?:${type}|功能|需求|问题|相关内容)$`, "u"), "")
		.replace(/[“”"'`<>]/gu, "")
		.replace(/\s+/gu, " ")
		.trim();

	if ([...text].length < 2) return null;
	if (/\p{Script=Han}/u.test(text)) text = [...text].slice(0, 14).join("");
	else text = text.split(/\s+/u).slice(0, 8).join(" ");
	return text.replace(/[，,。.!！?？;；:：]+$/u, "").trim() || null;
}

export function shanghaiDate(value) {
	const parts = new Intl.DateTimeFormat("en-US", {
		timeZone: "Asia/Shanghai",
		month: "2-digit",
		day: "2-digit",
	}).formatToParts(new Date(value));
	return `${parts.find((part) => part.type === "month").value}${parts.find((part) => part.type === "day").value}`;
}

export function buildTitle(prompt, createdAt = new Date()) {
	if (!isSubstantive(prompt)) return null;
	const type = classify(prompt);
	if (!type) return null;
	const topic = compactTopic(prompt, type);
	return topic ? `${shanghaiDate(createdAt)} | ${type} | ${topic}` : null;
}

function stateFile(sessionId) {
	const root = process.env.XDG_STATE_HOME || (process.platform === "win32"
		? process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local")
		: path.join(os.homedir(), ".local", "state"));
	const key = createHash("sha256").update(sessionId).digest("hex");
	return path.join(root, "conversation-title", "claude", `${key}.json`);
}

export function handleClaudeHook(input, now = new Date()) {
	const sessionId = typeof input?.session_id === "string" ? input.session_id : "";
	if (!sessionId || input.agent_id || input.agent_type) return {};
	const file = stateFile(sessionId);

	if (input.hook_event_name === "SessionStart") {
		if (input.source === "startup" && !input.session_title) {
			mkdirSync(path.dirname(file), { recursive: true });
			writeFileSync(file, JSON.stringify({ createdAt: now.toISOString() }), "utf8");
		} else if (existsSync(file)) {
			rmSync(file);
		}
		return {};
	}

	if (input.hook_event_name !== "UserPromptSubmit" || !existsSync(file)) return {};
	const state = JSON.parse(readFileSync(file, "utf8"));
	const title = buildTitle(input.prompt, state.createdAt);
	if (!title) return {};
	rmSync(file);
	return { hookSpecificOutput: { hookEventName: "UserPromptSubmit", sessionTitle: title } };
}

async function main() {
	if (process.argv.includes("--self-test")) {
		assert.equal(buildTitle("你好", "2026-09-03T00:00:00Z"), null);
		assert.equal(buildTitle("请修复登录页面报错", "2026-09-03T00:00:00Z"), "0903 | 修复 | 登录页面报错");
		assert.equal(buildTitle("调研多个插件并给出选型建议", "2026-09-03T00:00:00Z"), "0903 | 研究 | 多个插件并给出选型建议");
		console.log("ok");
		return;
	}
	const chunks = [];
	for await (const chunk of process.stdin) chunks.push(chunk);
	const input = JSON.parse(Buffer.concat(chunks).toString("utf8"));
	process.stdout.write(JSON.stringify(handleClaudeHook(input)));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
	main().catch((error) => {
		console.error(error instanceof Error ? error.message : String(error));
		process.exitCode = 1;
	});
}
