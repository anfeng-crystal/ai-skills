#!/usr/bin/env python3
"""Write CLI output without exposing filesystem exception details."""

import errno
import os
from pathlib import Path
import sys
import tempfile
from typing import Optional

from errors import CliRuntimeError


def write_output(content: str, output_path: Optional[str]) -> None:
    if not output_path:
        print(content)
        return

    temporary = None
    write_error = None
    try:
        target = Path(output_path)
        if not target.is_absolute():
            target = Path.cwd() / target
        target.parent.mkdir(parents=True, exist_ok=True)
        # Own a unique file in the destination directory for atomic replacement.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=target.parent,
            prefix=".union-search-", suffix=".tmp", delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, target)
        temporary = None
    except OSError as exc:
        write_error = CliRuntimeError(
            "Could not write output file.",
            detail=f"errno={errno.errorcode.get(exc.errno, 'UNKNOWN')}",
        )
        raise write_error from None
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except OSError as exc:
                # Keep the write failure primary and report cleanup without paths.
                if write_error is not None:
                    write_error.detail += f"; cleanup_errno={errno.errorcode.get(exc.errno, 'UNKNOWN')}"

    print(str(target), file=sys.stderr)
