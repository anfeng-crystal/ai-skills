#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
JAR_PATH = ROOT.parent / "assets" / "isc-iscb-util.jar"
RUNNER_SRC = ROOT / "script_runtime_main" / "ScriptRuntimeMain.java"
CACHE_ROOT = Path(tempfile.gettempdir()) / "kingdee-iscb-script" / "script_runtime_real"
RUNNER_CLASSES = CACHE_ROOT / "classes"
MAIN_CLASS = "local.iscb.runtime.ScriptRuntimeMain"


def ensure_inputs() -> None:
	if not JAR_PATH.exists():
		raise SystemExit(f"missing jar: {JAR_PATH}")
	if not RUNNER_SRC.exists():
		raise SystemExit(f"missing runner source: {RUNNER_SRC}")


def needs_compile() -> bool:
	main_class = RUNNER_CLASSES / "local" / "iscb" / "runtime" / "ScriptRuntimeMain.class"
	if not main_class.exists():
		return True
	class_mtime = main_class.stat().st_mtime
	return RUNNER_SRC.stat().st_mtime > class_mtime or JAR_PATH.stat().st_mtime > class_mtime


def compile_project() -> None:
	RUNNER_CLASSES.mkdir(parents=True, exist_ok=True)
	cmd = [
		"javac",
		"-encoding",
		"UTF-8",
		"-d",
		str(RUNNER_CLASSES),
		"-cp",
		str(JAR_PATH),
		str(RUNNER_SRC),
	]
	run(cmd, cwd=ROOT)


def ensure_compiled() -> None:
	ensure_inputs()
	if needs_compile():
		compile_project()


def run_java(command: str, script_text: str, bindings: dict[str, Any] | None = None) -> str:
	ensure_compiled()
	tmp_dir = CACHE_ROOT / "tmp"
	tmp_dir.mkdir(parents=True, exist_ok=True)
	with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".iscb", dir=tmp_dir, delete=False) as script_handle:
		script_handle.write(script_text)
		script_path = Path(script_handle.name)

	bindings_path: Path | None = None
	try:
		args = [
			"java",
			"-cp",
			f"{RUNNER_CLASSES}:{JAR_PATH}",
			MAIN_CLASS,
			command,
			str(script_path),
		]
		if bindings is not None:
			with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".json", dir=tmp_dir, delete=False) as bindings_handle:
				bindings_handle.write(json.dumps(bindings, ensure_ascii=False))
				bindings_path = Path(bindings_handle.name)
			args.append(str(bindings_path))
		return run(args, cwd=ROOT).stdout.strip()
	finally:
		script_path.unlink(missing_ok=True)
		if bindings_path is not None:
			bindings_path.unlink(missing_ok=True)


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
	return subprocess.run(
		cmd,
		cwd=str(cwd),
		text=True,
		check=True,
		capture_output=True,
	)


def compile_command(args: argparse.Namespace) -> int:
	script_text = Path(args.script_file).read_text(encoding="utf-8")
	bindings = load_bindings(args.bindings_json)
	print(run_java("compile", script_text, bindings))
	return 0


def eval_command(args: argparse.Namespace) -> int:
	script_text = Path(args.script_file).read_text(encoding="utf-8")
	bindings = load_bindings(args.bindings_json)
	print(run_java("eval", script_text, bindings))
	return 0


def selftest_command(_: argparse.Namespace) -> int:
	cases = [
		{
			"name": "arithmetic",
			"script": "1 + 2",
			"expected": 3,
		},
		{
			"name": "base64",
			"script": "Base64Encode(String.getBytes(\"abc\", \"UTF-8\"))",
			"expected": "YWJj",
		},
		{
			"name": "hmac",
			"script": "Base64Encode(Hash.HmacSHA256(String.getBytes(\"data\", \"UTF-8\"), String.getBytes(\"secret\", \"UTF-8\")))",
			"expected": "GywWt1vSqHDBFBU8zaW8/KYzFLxyL6Fg1pDeEzzLuds=",
		},
	]

	for case in cases:
		value = json.loads(run_java("eval", case["script"]))
		if value != case["expected"]:
			raise SystemExit(
				f"selftest failed: {case['name']} actual={value!r} expected={case['expected']!r}"
			)

	print(f"status=pass phase=real-runtime-selftest cases={len(cases)}")
	for case in cases:
		print(f"{case['name']}={case['expected']!r}")
	return 0


def load_bindings(path: str | None) -> dict[str, Any] | None:
	if not path:
		return None
	return json.loads(Path(path).read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
	parser = argparse.ArgumentParser(description="Real Script.compile/eval runtime wrapper backed by isc-iscb-util.jar.")
	sub = parser.add_subparsers(dest="command", required=True)

	compile_parser = sub.add_parser("compile")
	compile_parser.add_argument("script_file")
	compile_parser.add_argument("--bindings-json")
	compile_parser.set_defaults(func=compile_command)

	eval_parser = sub.add_parser("eval")
	eval_parser.add_argument("script_file")
	eval_parser.add_argument("--bindings-json")
	eval_parser.set_defaults(func=eval_command)

	selftest_parser = sub.add_parser("selftest")
	selftest_parser.set_defaults(func=selftest_command)

	return parser


def main() -> int:
	parser = build_parser()
	args = parser.parse_args()
	try:
		return args.func(args)
	except subprocess.CalledProcessError as exc:
		if exc.stdout:
			sys.stderr.write(exc.stdout)
			if not exc.stdout.endswith("\n"):
				sys.stderr.write("\n")
		if exc.stderr:
			sys.stderr.write(exc.stderr)
			if not exc.stderr.endswith("\n"):
				sys.stderr.write("\n")
		return exc.returncode


if __name__ == "__main__":
	raise SystemExit(main())
