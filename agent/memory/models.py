"""Memory domain constants.

The physical SQLAlchemy ORM models live in the UI backend because that process
owns database sessions. Agent memory services depend on these stable domain
values instead of duplicating ORM definitions.
"""

from __future__ import annotations


SESSION_SUMMARY = "session_summary"
ACTIVE = "active"
