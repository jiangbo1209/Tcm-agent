"""Small startup schema adjustments for deployments without Alembic."""

from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Engine

LOGGER = logging.getLogger(__name__)


MESSAGE_AGENT_COLUMNS = {
    "intent": "VARCHAR(80)",
    "retrieval_query": "TEXT",
    "retrieval_used": "BOOLEAN NOT NULL DEFAULT FALSE",
    "retrieval_total": "INTEGER",
    "query_plan": "JSON",
    "references": "JSON",
    "validation_result": "JSON",
    "warnings": "JSON",
}

CONVERSATION_MEMORY_COLUMNS = {
    "covered_message_id": "INTEGER",
}


def ensure_agent_message_columns(engine: Engine) -> None:
    """Add Agent metadata columns to existing messages tables."""

    with engine.begin() as connection:
        has_messages = connection.execute(
            text("SELECT to_regclass('public.messages') IS NOT NULL")
        ).scalar()
        if not has_messages:
            return

        for name, column_type in MESSAGE_AGENT_COLUMNS.items():
            connection.execute(
                text(f'ALTER TABLE messages ADD COLUMN IF NOT EXISTS "{name}" {column_type}')
            )

    LOGGER.info("Ensured Agent metadata columns on messages table")


def ensure_conversation_memory_columns(engine: Engine) -> None:
    """Add rolling-summary metadata to existing conversation memory tables."""

    with engine.begin() as connection:
        has_memories = connection.execute(
            text("SELECT to_regclass('public.conversation_memories') IS NOT NULL")
        ).scalar()
        if not has_memories:
            return

        for name, column_type in CONVERSATION_MEMORY_COLUMNS.items():
            connection.execute(
                text(
                    f'ALTER TABLE conversation_memories ADD COLUMN IF NOT EXISTS "{name}" {column_type}'
                )
            )

    LOGGER.info("Ensured rolling-summary columns on conversation_memories table")


def ensure_core_file_uploader_column(engine: Engine) -> None:
    """Add upload audit metadata to existing core_file tables."""

    with engine.begin() as connection:
        has_core_file = connection.execute(
            text("SELECT to_regclass('public.core_file') IS NOT NULL")
        ).scalar()
        if not has_core_file:
            return

        connection.execute(
            text("ALTER TABLE core_file ADD COLUMN IF NOT EXISTS uploader_id INTEGER")
        )
        connection.execute(
            text("CREATE INDEX IF NOT EXISTS idx_core_file_uploader ON core_file (uploader_id)")
        )
        connection.execute(
            text(
                "CREATE INDEX IF NOT EXISTS idx_core_file_status_ragflow "
                "ON core_file (status_ragflow) WHERE status_ragflow = FALSE"
            )
        )

    LOGGER.info("Ensured upload metadata on core_file table")
