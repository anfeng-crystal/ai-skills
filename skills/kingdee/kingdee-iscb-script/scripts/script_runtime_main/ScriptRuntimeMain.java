package local.iscb.runtime;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.HashMap;
import java.util.Map;

import kd.isc.iscb.util.misc.Json;
import kd.isc.iscb.util.script.LifeScriptEngine;
import kd.isc.iscb.util.script.Script;

public final class ScriptRuntimeMain {
	private ScriptRuntimeMain() {
	}

	public static void main(String[] args) throws Exception {
		if (args.length < 2) {
			throw new IllegalArgumentException("Usage: <compile|eval> <script-file> [bindings-json-file]");
		}

		String command = args[0];
		String scriptText = Files.readString(Path.of(args[1]), StandardCharsets.UTF_8);
		Map<String, Object> bindings = args.length >= 3 ? readBindings(Path.of(args[2])) : new HashMap<String, Object>();

		if ("compile".equals(command)) {
			LifeScriptEngine.setNow();
			Script.compile(scriptText, new HashMap<String, Object>(bindings));
			System.out.println("status=pass phase=runtime-compile");
			return;
		}

		if ("eval".equals(command)) {
			LifeScriptEngine.setNow();
			Script compiled = Script.compile(scriptText, new HashMap<String, Object>(bindings));
			LifeScriptEngine.setNow();
			Object result = compiled.eval(new HashMap<String, Object>(bindings));
			System.out.println(Json.toString(result, true));
			return;
		}

		throw new IllegalArgumentException("Unknown command: " + command);
	}

	@SuppressWarnings("unchecked")
	private static Map<String, Object> readBindings(Path path) throws Exception {
		String text = Files.readString(path, StandardCharsets.UTF_8);
		if (text.trim().isEmpty()) {
			return new HashMap<String, Object>();
		}

		Object parsed = Script.parseJson(text);
		if (parsed == null) {
			return new HashMap<String, Object>();
		}
		if (parsed instanceof Map) {
			return new HashMap<String, Object>((Map<String, Object>) parsed);
		}
		throw new IllegalArgumentException("Bindings JSON must be an object.");
	}
}
