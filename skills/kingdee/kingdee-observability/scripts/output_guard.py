"""Preserve source artifacts when CLI output paths alias an input file."""

from __future__ import annotations

from pathlib import Path


def write_output(payload: str, input_path: Path, output_path: str | None) -> None:
    if not output_path:
        print(payload)
        return

    output = Path(output_path).expanduser().resolve()
    if output == input_path.resolve():
        raise ValueError("output must not overwrite input")
    try:
        aliases_input = output.samefile(input_path)
    except FileNotFoundError:
        aliases_input = False
    if aliases_input:
        raise ValueError("output must not overwrite input (same file)")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload, encoding="utf-8")
