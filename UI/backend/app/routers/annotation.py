"""数据标注 API 路由。

所有标注端点统一受 :func:`annotation_gate` 总闸保护：仅当
``ANNOTATION_ENABLED=true`` 时放行，否则返回 503。
路由在导入期零副作用（不连接数据库），配置经 ``get_annotation_config``
的 lru_cache 在请求期读取。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import get_annotation_config


def annotation_gate() -> None:
    """功能总闸：未开启时拒绝一切数据标注端点。"""
    if not get_annotation_config().ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据标注功能未开启",
        )


router = APIRouter(prefix="/api/annotation", dependencies=[Depends(annotation_gate)])


@router.get("/health")
def annotation_health() -> dict[str, bool]:
    """占位探活端点：能到达即代表总闸已放行。"""
    return {"enabled": True}
