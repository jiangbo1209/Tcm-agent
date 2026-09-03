"""Admin user management routes. Admin accounts are protected — only modifiable via local script."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.service import get_password_hash
from app.dependencies.auth import require_admin
from app.core.database import get_db
from app.models import AnnotationTask, AnnotationTaskItem
from app.models.user import User

router = APIRouter(prefix="/api/users", tags=["users"])

VALID_ROLES = {"professional", "normal", "annotator"}

_DELETE_GUARD_DETAIL = "该标注员仍有进行中的任务或待返工条目，请先回收后再删除"


class UserCreateAdmin(BaseModel):
    username: str
    email: str
    password: str
    role: str = "normal"


class RoleUpdate(BaseModel):
    role: str


class PasswordReset(BaseModel):
    new_password: str


class ActiveUpdate(BaseModel):
    is_active: bool


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def _guard_admin_target(db: Session, user_id: int) -> User:
    """Fetch user and reject if target is admin."""
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == "admin":
        raise HTTPException(status_code=403, detail="无法修改管理员账号")
    return user


@router.get("")
def list_users(
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    users = db.query(User).order_by(User.id.asc()).all()
    return {"users": [_serialize_user(u) for u in users]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreateAdmin,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"不允许创建 admin 账号，角色可选: {', '.join(VALID_ROLES)}")

    if db.query(User).filter(User.username == body.username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="邮箱已被注册")

    user = User(
        username=body.username,
        email=body.email,
        hashed_password=get_password_hash(body.password),
        role=body.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"user": _serialize_user(user)}


@router.put("/{user_id}/role")
def update_role(
    user_id: int,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"不允许修改为 admin 角色，角色可选: {', '.join(VALID_ROLES)}")

    user = _guard_admin_target(db, user_id)
    user.role = body.role
    db.commit()
    db.refresh(user)
    return {"user": _serialize_user(user)}


@router.put("/{user_id}/password")
def reset_password(
    user_id: int,
    body: PasswordReset,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = _guard_admin_target(db, user_id)
    user.hashed_password = get_password_hash(body.new_password)
    db.commit()
    return {"detail": "密码已重置"}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    user = _guard_admin_target(db, user_id)

    # F4-V2/A2：占用中的标注员不可删——进行中任务会变孤儿、rejected 条目失去返工人
    has_active_task = (
        db.query(AnnotationTask.id)
        .filter(
            AnnotationTask.claimed_by == user_id,
            AnnotationTask.status.in_(("open", "in_progress")),
        )
        .first()
    )
    has_rework_item = (
        db.query(AnnotationTaskItem.id)
        .join(AnnotationTask, AnnotationTask.id == AnnotationTaskItem.task_id)
        .filter(
            AnnotationTask.claimed_by == user_id,
            AnnotationTaskItem.status == "rejected",
        )
        .first()
    )
    if has_active_task is not None or has_rework_item is not None:
        raise HTTPException(status_code=409, detail=_DELETE_GUARD_DETAIL)

    db.delete(user)
    db.commit()
    return {"detail": "用户已删除"}


@router.put("/{user_id}/active")
def set_active(
    user_id: int,
    body: ActiveUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能修改自己的启用状态")
    user = _guard_admin_target(db, user_id)
    user.is_active = body.is_active
    db.commit()
    db.refresh(user)
    return {"user": _serialize_user(user)}
