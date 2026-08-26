"""Shared HTTP-level test infrastructure for annotation tests.

Design rule (CRITICAL): tests exercise REAL dependency chains.
Only ``get_db`` may be overridden. Never override
``require_annotator`` / ``require_admin`` / ``get_current_user`` —
role checks read the DB user object, so users created via
:func:`make_user` are committed to the overridden session's DB and
JWTs are minted with the real :func:`create_access_token`.

Why not ``from main import app``: this machine has no PostgreSQL and
``main.py`` performs module-level ``ensure_*`` migrations that dial PG
directly (see tests/test_graph_authz.py). We therefore mount the REAL
routers on a bare FastAPI host exactly like main.py does, so every
endpoint keeps its genuine Depends(require_admin)-style chain.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from app.auth.service import create_access_token, get_password_hash
from app.models.user import User

# bcrypt hashing is expensive (~100ms+); compute the hash exactly once
# at module import so every make_user call reuses it.
TEST_PASSWORD_HASH = get_password_hash("x")


@contextmanager
def build_test_client(db_session) -> Iterator:
    """Yield TestClient(app) whose get_db yields *db_session*.

    The app is imported lazily inside the function. Routers are mounted
    exactly as in main.py (e.g. plain ``include_router(users_router)``),
    preserving each endpoint's real dependency chain; only ``get_db``
    points at *db_session*. Overrides are cleared on exit so tests never
    leak state into each other.
    """
    from fastapi.testclient import TestClient

    from app.core.database import get_db
    from app.routers.users import router as users_router

    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(users_router)
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def auth_header(user: User) -> dict:
    """Real Bearer header minted with the production JWT signer."""
    token = create_access_token(data={"sub": str(user.id), "role": user.role})
    return {"Authorization": f"Bearer {token}"}


def make_user(db, username: str, role: str, is_active: bool = True) -> User:
    """Commit a User row into *db* and return the refreshed instance."""
    user = User(
        username=username,
        email=f"{username}@test.local",
        hashed_password=TEST_PASSWORD_HASH,
        role=role,
        is_active=is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@contextmanager
def make_db() -> Iterator:
    """Yield an in-memory SQLite session carrying the full user-domain schema.

    ``app/models/__init__.py`` deliberately re-exports only some models, yet
    ``Base.metadata.create_all`` needs EVERY table of a FK chain registered,
    otherwise resolution fails (e.g. agent_tool_runs.message_id -> messages).
    The explicit module imports below exist purely for that registration.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    import app.models.conversation  # noqa: F401
    import app.models.message  # noqa: F401
    from app.models import Base

    # StaticPool keeps ONE shared in-memory connection across threads:
    # TestClient executes sync endpoints in a worker thread, and plain
    # sqlite:///:memory: would give each thread its own empty database.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for _tbl in Base.metadata.tables.values():
        for _col in _tbl.columns:
            try:
                _sd = _col.server_default
            except Exception:
                continue
            if _sd is not None:
                try:
                    _txt = str(_sd.arg) if hasattr(_sd, "arg") else str(_sd)
                except Exception:
                    continue
                if "NOW()" in _txt:
                    _col.server_default = None
            try:
                _ou = _col.onupdate
            except Exception:
                continue
            if _ou is not None:
                try:
                    _otxt = str(_ou.arg) if hasattr(_ou, "arg") else str(_ou)
                except Exception:
                    continue
                if "NOW()" in _otxt:
                    _col.onupdate = None
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
