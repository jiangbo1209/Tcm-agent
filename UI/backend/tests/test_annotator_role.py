"""HTTP-level tests for annotator-role wiring (data-annotation plan, task 3).

Design rule (CRITICAL): every HTTP test exercises REAL dependency chains —
only ``get_db`` is overridden (see tests/utils.build_test_client).
``require_annotator`` / ``require_admin`` / ``get_current_user`` are never
overridden, so role checks read committed DB rows through production JWTs.
"""

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.dependencies.auth import require_annotator
from app.models.user import User
from tests.utils import auth_header, build_test_client, make_db, make_user

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture()
def db():
    with make_db() as session:
        yield session


# ---------------------------------------------------------------------------
# (a) require_annotator unit behaviour + real-chain HTTP plumbing sanity
# ---------------------------------------------------------------------------


def test_require_annotator_passes_for_annotator_only(db):
    annotator = make_user(db, "unit_ann", "annotator")
    normal = make_user(db, "unit_normal", "normal")
    professional = make_user(db, "unit_prof", "professional")
    admin = make_user(db, "unit_admin", "admin")

    # annotator passes, identity preserved
    assert require_annotator(annotator) is annotator

    # everyone else fails with strict 403 (admins included — they use
    # require_admin, never this dependency)
    for user in (normal, professional, admin):
        with pytest.raises(HTTPException) as exc_info:
            require_annotator(user)
        assert exc_info.value.status_code == 403


def test_users_list_real_chain_admin_ok_annotator_403(db):
    """End-to-end proof that utils drive the REAL require_admin chain."""
    admin = make_user(db, "chain_admin", "admin")
    annotator = make_user(db, "chain_annotator", "annotator")

    with build_test_client(db) as client:
        resp_admin = client.get("/api/users", headers=auth_header(admin))
        assert resp_admin.status_code == 200
        usernames = {u["username"] for u in resp_admin.json()["users"]}
        assert {"chain_admin", "chain_annotator"} <= usernames

        resp_ann = client.get("/api/users", headers=auth_header(annotator))
        assert resp_ann.status_code == 403
        assert resp_ann.json()["detail"] == "需要管理员权限才能访问此功能"


# ---------------------------------------------------------------------------
# (b) provisioning: POST /api/users accepts role="annotator"
# ---------------------------------------------------------------------------


def test_create_user_with_annotator_role(db):
    admin = make_user(db, "provision_admin", "admin")

    with build_test_client(db) as client:
        resp = client.post(
            "/api/users",
            headers=auth_header(admin),
            json={
                "username": "new_annotator",
                "email": "new_annotator@test.local",
                "password": "secret123",
                "role": "annotator",
            },
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["user"]["role"] == "annotator"

    row = db.query(User).filter(User.username == "new_annotator").first()
    assert row is not None
    assert row.role == "annotator"
    assert row.is_active is True


# ---------------------------------------------------------------------------
# (c) PUT /{user_id}/active toggling + immediate JWT kill via real chain
# ---------------------------------------------------------------------------


def test_toggle_active_disables_and_kills_existing_jwt(db):
    admin = make_user(db, "toggle_admin", "admin")
    victim = make_user(db, "toggle_victim", "normal")
    stale_auth = auth_header(victim)

    with build_test_client(db) as client:
        resp = client.put(
            f"/api/users/{victim.id}/active",
            headers=auth_header(admin),
            json={"is_active": False},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["user"]["is_active"] is False

        db.refresh(victim)
        assert victim.is_active is False

        # old token must be rejected immediately by the real get_current_user
        killed = client.get("/api/users", headers=stale_auth)
        assert killed.status_code == 401
        assert killed.json()["detail"] == "用户不存在或已禁用"


def test_reenable_restores_access(db):
    admin = make_user(db, "re_admin", "admin")
    target = make_user(db, "re_target", "normal")

    with build_test_client(db) as client:
        disable = client.put(
            f"/api/users/{target.id}/active",
            headers=auth_header(admin),
            json={"is_active": False},
        )
        assert disable.status_code == 200

        enable = client.put(
            f"/api/users/{target.id}/active",
            headers=auth_header(admin),
            json={"is_active": True},
        )
        assert enable.status_code == 200

        db.refresh(target)
        assert target.is_active is True
        assert client.get("/api/users", headers=auth_header(target)).status_code in (
            200,
            403,
        )  # normal role may still be forbidden by require_admin, but NOT 401


# ---------------------------------------------------------------------------
# (d) guards: admin target 403 / self-toggle 400
# ---------------------------------------------------------------------------


def test_toggle_active_rejects_admin_target_and_self(db):
    admin = make_user(db, "guard_admin", "admin")
    other_admin = make_user(db, "guard_other_admin", "admin")

    with build_test_client(db) as client:
        # targeting an admin account -> _guard_admin_target 403
        resp_admin_target = client.put(
            f"/api/users/{other_admin.id}/active",
            headers=auth_header(admin),
            json={"is_active": False},
        )
        assert resp_admin_target.status_code == 403
        assert resp_admin_target.json()["detail"] == "无法修改管理员账号"

        # self-toggle -> 400
        resp_self = client.put(
            f"/api/users/{admin.id}/active",
            headers=auth_header(admin),
            json={"is_active": True},
        )
        assert resp_self.status_code == 400
        assert resp_self.json()["detail"] == "不能修改自己的启用状态"


def test_toggle_active_missing_user_404(db):
    admin = make_user(db, "missing_admin", "admin")
    with build_test_client(db) as client:
        resp = client.put(
            "/api/users/99999/active",
            headers=auth_header(admin),
            json={"is_active": False},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# (e) unauthenticated access rejected
# ---------------------------------------------------------------------------


def test_no_token_rejected(db):
    make_user(db, "anon_admin", "admin")
    with build_test_client(db) as client:
        resp = client.get("/api/users")  # no Authorization header at all
        # HTTPBearer(auto_error=True) answers a MISSING header with its own
        # 401/403 before any handler runs; assert exact framework behaviour.
        assert resp.status_code in (401, 403)
        assert resp.json() != {"users": []}


# ---------------------------------------------------------------------------
# (f) F4-V2/A2: annotator delete guard (active task / pending rework -> 409)
# ---------------------------------------------------------------------------


def _seed_task(db, annotator_id: int, *, status: str):
    from app.models import AnnotationTask

    task = AnnotationTask(pool_id=None, claimed_by=annotator_id, status=status)
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _seed_rework_item(db, task_id: int):
    from app.models import AnnotationTaskItem

    item = AnnotationTaskItem(
        task_id=task_id,
        table_name="lit",
        record_id=1,
        status="rejected",
        rejected_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(item)
    db.commit()
    return item


def test_delete_annotator_with_active_task_conflicts(db):
    admin = make_user(db, "del_guard_admin", "admin")
    busy = make_user(db, "del_guard_busy", "annotator")
    _seed_task(db, busy.id, status="in_progress")

    with build_test_client(db) as client:
        resp = client.delete(f"/api/users/{busy.id}", headers=auth_header(admin))

    assert resp.status_code == 409
    assert resp.json()["detail"] == "该标注员仍有进行中的任务或待返工条目，请先回收后再删除"
    assert db.query(User).filter(User.id == busy.id).first() is not None


def test_delete_annotator_with_pending_rework_item_conflicts(db):
    admin = make_user(db, "del_rework_admin", "admin")
    reworker = make_user(db, "del_guard_rework", "annotator")
    task = _seed_task(db, reworker.id, status="completed")
    _seed_rework_item(db, task.id)

    with build_test_client(db) as client:
        resp = client.delete(f"/api/users/{reworker.id}", headers=auth_header(admin))

    assert resp.status_code == 409
    assert db.query(User).filter(User.id == reworker.id).first() is not None


def test_delete_annotator_without_tasks_succeeds(db):
    admin = make_user(db, "del_ok_admin", "admin")
    free = make_user(db, "del_guard_free", "annotator")

    with build_test_client(db) as client:
        resp = client.delete(f"/api/users/{free.id}", headers=auth_header(admin))

    assert resp.status_code == 200
    assert resp.json() == {"detail": "用户已删除"}
    assert db.query(User).filter(User.id == free.id).first() is None


# ---------------------------------------------------------------------------
# misleading-success guard: production main.py must really mount users_router
# ---------------------------------------------------------------------------


def test_main_py_mounts_users_router():
    source = (BACKEND_DIR / "main.py").read_text(encoding="utf-8")
    match = re.search(r"include_router\(\s*users_router\b", source)
    assert match, "main.py no longer mounts users_router — test replica would be masking it"
