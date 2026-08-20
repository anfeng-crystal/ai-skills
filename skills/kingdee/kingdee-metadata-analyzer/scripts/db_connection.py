"""Bounded retry support for metadata PostgreSQL connections."""

import time
from typing import Any, Callable, Dict, Optional


DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_INITIAL_DELAY_SECONDS = 0.25

_RETRYABLE_SQLSTATES = {
    "53300",  # too_many_connections
    "57P01",  # admin_shutdown
    "57P02",  # crash_shutdown
    "57P03",  # cannot_connect_now
}

_RETRYABLE_MESSAGE_MARKERS = (
    "server closed the connection unexpectedly",
    "connection timed out",
    "timeout expired",
    "could not connect to server",
    "connection refused",
    "connection reset",
    "network is unreachable",
    "temporary failure in name resolution",
    "could not translate host name",
    "ssl syscall error",
    "eof detected",
    "the database system is starting up",
    "cannot connect now",
    "terminating connection due to administrator command",
)


class MetadataDbConnectionError(RuntimeError):
    """A sanitized metadata database connection failure."""


def is_retryable_connection_error(exc: BaseException) -> bool:
    """Return true only for connection-level failures that can be transient."""
    sqlstate = str(getattr(exc, "pgcode", "") or "").upper()
    if sqlstate:
        return sqlstate.startswith("08") or sqlstate in _RETRYABLE_SQLSTATES

    message = str(exc).lower()
    return any(marker in message for marker in _RETRYABLE_MESSAGE_MARKERS)


def connect_with_retry(
    connect: Callable[..., Any],
    connection_kwargs: Dict[str, Any],
    *,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    initial_delay_seconds: float = DEFAULT_INITIAL_DELAY_SECONDS,
    warn: Optional[Callable[[str], None]] = None,
):
    """Connect with short exponential backoff for transient failures only."""
    attempts = max(1, int(max_attempts))
    delay = max(0.0, float(initial_delay_seconds))

    for attempt in range(1, attempts + 1):
        try:
            return connect(**connection_kwargs)
        except Exception as exc:
            retryable = is_retryable_connection_error(exc)
            if not retryable or attempt == attempts:
                if retryable:
                    message = f"元数据数据库连接连续失败，已尝试 {attempts} 次；请检查目标元数据库或网络状态。"
                else:
                    message = "元数据数据库连接失败；请检查数据库配置、凭据、网络或服务状态。"
                raise MetadataDbConnectionError(message) from None

            if warn is not None:
                warn(
                    f"元数据数据库连接瞬时中断（第 {attempt}/{attempts} 次尝试），"
                    f"{delay:g} 秒后重试。"
                )
            time.sleep(delay)
            delay *= 2

    raise AssertionError("unreachable")
