import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";

const TITLE = /^\d{4} \| (功能|设计|修复|优化|发布|探索|文档|研究) \| ([^|\r\n]{2,80})$/u;

function isSubstantive(prompt: string): boolean {
	const text = prompt.normalize("NFKC").trim();
	return text.length >= 4 &&
		!/^(?:你好|您好|嗨|hi|hello|hey|谢谢|好的|收到|ok|okay)[!！,.，。\s]*$/iu.test(text) &&
		!/^\/(?:help|resume|clear|config|status|model|permissions)\b/iu.test(text);
}

export default function (pi: ExtensionAPI) {
	let eligible = false;

	pi.on("session_start", async (_event, ctx) => {
		eligible = !pi.getSessionName() && ctx.sessionManager.getEntries().length === 0;
	});

	pi.on("before_agent_start", async (event) => {
		if (!eligible || pi.getSessionName() || !isSubstantive(event.prompt)) return;
		return {
			systemPrompt: `${event.systemPrompt}\n\nThis is the first substantive request in a new root session. Apply the installed conversation-title skill now and call set_conversation_title exactly once with its validated title. Do not delay or mention this metadata action to the user.`,
		};
	});

	pi.registerTool({
		name: "set_conversation_title",
		label: "Set Conversation Title",
		description: "Set the current new root session title once using the conversation-title contract.",
		parameters: Type.Object({
			title: Type.String({ description: "MMDD | 类型 | 主题" }),
		}),
		async execute(_toolCallId, params) {
			if (!eligible || pi.getSessionName()) {
				eligible = false;
				return { content: [{ type: "text", text: "Session title was already set or this is not a new session." }], details: {} };
			}
			const title = params.title.trim();
			if (!TITLE.test(title)) {
				return { content: [{ type: "text", text: "Invalid title. Expected MMDD | 类型 | 主题." }], details: {}, isError: true };
			}
			pi.setSessionName(title);
			eligible = false;
			return { content: [{ type: "text", text: `Session named: ${title}` }], details: { title } };
		},
	});
}
