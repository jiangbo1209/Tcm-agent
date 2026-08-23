"""数据标注管理后台路由（/api/annotation/admin）。

与业务路由共用同一 :func:`annotation_gate` 总闸；后续任务在此挂载
任务分配 / 返工管理等管理员端点。导入期零副作用。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.routers.annotation import annotation_gate

router = APIRouter(
    prefix="/api/annotation/admin", dependencies=[Depends(annotation_gate)]
)
