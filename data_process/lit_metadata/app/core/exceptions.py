from __future__ import annotations


class ConfigError(Exception):
    """Raised when application configuration is invalid."""


class CrawlerError(Exception):
    """Base crawler exception."""

    failure_reason = "unknown_error"

    def __init__(self, message: str = "Crawler error") -> None:
        super().__init__(message)


class SearchNoResultError(CrawlerError):
    """Raised when a search returns no usable result."""

    failure_reason = "no_result"


class DetailPageParseError(CrawlerError):
    """Raised when a detail page cannot be parsed."""

    failure_reason = "page_parse_failed"


class CaptchaDetectedError(CrawlerError):
    """Raised when a captcha or security verification page is detected."""

    failure_reason = "captcha_detected"


class LoginRequiredError(CrawlerError):
    """Raised when the page requires login."""

    failure_reason = "login_required"


class AccessLimitedError(CrawlerError):
    """Raised when access is forbidden, rate limited, or restricted."""

    failure_reason = "access_limited"


class TitleNotMatchedError(CrawlerError):
    """Raised when no search result exactly matches the expected title."""

    failure_reason = "title_not_exact_match"


class TimeoutCrawlerError(CrawlerError):
    """Raised when a crawler request times out."""

    failure_reason = "timeout"


class NetworkCrawlerError(CrawlerError):
    """Raised when a temporary network or server-side error occurs."""

    failure_reason = "network_error"


class DatabaseError(Exception):
    """Raised when a database operation fails."""


class ExportError(Exception):
    """Raised when exporting failed records fails."""
