"""Initialize all PostgreSQL database tables.

Creates both business tables (users, conversations, messages, core_file,
lit_metadata, med_case, ...) and graph tables (nodes, edges).

Usage:
    python scripts/init_db.py

This is idempotent — safe to run multiple times.
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "UI", "backend"))

from app.core.database import engine
from app.models import (
    AgentToolRun,
    Base,
    ConversationMemory,
    CoreFile,
    Edge,
    GraphBase,
    GuidelineMetadata,
    LitMetadata,
    MedCase,
    Node,
)
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.search_history import SearchHistory
from app.models.user import User


def main() -> int:
    print("Creating business tables...")
    Base.metadata.create_all(bind=engine)
    print("Creating graph tables...")
    GraphBase.metadata.create_all(bind=engine)
    print("All tables created successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
