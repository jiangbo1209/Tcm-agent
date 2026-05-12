from __future__ import annotations

import httpx


def is_retryable_status(status_code: int) -> bool:
    return 500 <= status_code < 600


def is_retryable_exception(exc: Exception) -> bool:
    return isinstance(
        exc,
        (
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.ReadError,
            httpx.RemoteProtocolError,
            httpx.NetworkError,
        ),
    )
