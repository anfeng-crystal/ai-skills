import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { stripTypeScriptTypes } from "node:module";
import { isSubstantive } from "./title-core.mjs";

// Execute the adapter source with in-memory host/schema stubs, never a live Pi session.
const source = process.env.CONVERSATION_TITLE_PI_TEST_SOURCE || new URL("./pi-extension.ts", import.meta.url);
const compiled = stripTypeScriptTypes(readFileSync(source, "utf8"));
const typeImport = 'import { Type } from "typebox";';
assert.equal(compiled.split(typeImport).length, 2, "Typebox stub must replace exactly one import");
const stubbed = compiled.replace(typeImport, "const Type = { Object: (value) => value, String: (value) => value };");
const { default: install } = await import(`data:text/javascript;base64,${Buffer.from(stubbed).toString("base64")}`);

async function fixture({ name, entries = [] } = {}) {
	const events = new Map();
	const tools = new Map();
	const names = [];
	install({
		on: (event, handler) => events.set(event, handler),
		registerTool: (tool) => tools.set(tool.name, tool),
		getSessionName: () => name,
		setSessionName: (title) => { name = title; names.push(title); },
	});
	await events.get("session_start")({}, { sessionManager: { getEntries: () => entries } });
	return {
		names,
		setExistingName: (title) => { name = title; },
		before: (prompt) => events.get("before_agent_start")({ prompt, systemPrompt: "original instructions" }),
		setTitle: (title) => tools.get("set_conversation_title").execute("fixture-call", { title }),
	};
}

for (const [label, prompt] of [
	["image", "[image]"],
	["file", "[file report.pdf]"],
	["attachment", "[attachment diagram.png]"],
	["multiple attachments", "  [image first.png]\n[file report.pdf] [attachment other.png]  "],
	["normalized attachment", "［IMAGE screenshot.png］"],
	["hooks command", "/hooks"],
	["hooks command argument", "/hooks status"],
]) {
	test(`does not request a title for ${label}`, async () => {
		assert.equal(isSubstantive(prompt), false, "shared core already excludes this input");
		const host = await fixture();
		assert.equal(await host.before(prompt), undefined);
		assert.deepEqual(host.names, []);
	});
}

test("skips greetings, acknowledgements, blank input, and existing native commands", async () => {
	for (const prompt of ["", "  ", "你好！", "hello", "谢谢", "okay.", "/help", "/resume", "/clear", "/config", "/status", "/model", "/permissions"]) {
		const host = await fixture();
		assert.equal(await host.before(prompt), undefined, prompt);
		assert.deepEqual(host.names, []);
	}
});

test("attachments accompanied by a substantive request still trigger naming", async () => {
	for (const prompt of ["[image]\n请修复登录错误", "请分析这张图 [image]", "[file report.pdf] Summarize the report", "Explain the /hooks command"]) {
		const host = await fixture();
		const result = await host.before(prompt);
		assert.match(result.systemPrompt, /^original instructions\n\n/u);
		assert.match(result.systemPrompt, /set_conversation_title exactly once/u);
		assert.deepEqual(host.names, []);
	}
});

test("ordinary Chinese and English requests keep their current trigger", async () => {
	for (const prompt of ["请修复登录页面报错", "Build a small report viewer", "/hooksCustom command details"]) {
		const host = await fixture();
		assert.match((await host.before(prompt)).systemPrompt, /set_conversation_title exactly once/u);
	}
});

test("ignored turns preserve eligibility for the next substantive request", async () => {
	const host = await fixture();
	for (const prompt of ["[image]", "/hooks", "你好"]) assert.equal(await host.before(prompt), undefined);
	assert.match((await host.before("请修复上传错误")).systemPrompt, /set_conversation_title exactly once/u);
	const title = "1005 | 修复 | 上传错误";
	const result = await host.setTitle(title);
	assert.deepEqual(result.details, { title });
	assert.deepEqual(host.names, [title]);
});

test("already named and resumed sessions remain ineligible", async () => {
	for (const options of [{ name: "Existing user title" }, { entries: [{ type: "message" }] }]) {
		const host = await fixture(options);
		assert.equal(await host.before("请修复上传错误"), undefined);
		assert.deepEqual((await host.setTitle("1005 | 修复 | 上传错误")).details, {});
		assert.deepEqual(host.names, []);
	}
});

test("a name assigned after session start also blocks mutation", async () => {
	const host = await fixture();
	host.setExistingName("User chosen title");
	assert.equal(await host.before("请修复上传错误"), undefined);
	assert.deepEqual((await host.setTitle("1005 | 修复 | 上传错误")).details, {});
	assert.deepEqual(host.names, []);
});

test("invalid title can be corrected but valid title is applied only once", async () => {
	const host = await fixture();
	await host.before("请修复上传错误");
	assert.equal((await host.setTitle("invalid title")).isError, true);
	assert.deepEqual(host.names, []);
	const title = "1005 | 修复 | 上传错误";
	assert.deepEqual((await host.setTitle(` ${title} `)).details, { title });
	assert.equal(await host.before("增加支持格式"), undefined);
	assert.deepEqual((await host.setTitle("1005 | 功能 | 支持格式")).details, {});
	assert.deepEqual(host.names, [title]);
});
