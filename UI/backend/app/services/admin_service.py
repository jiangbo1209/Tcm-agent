"""Admin delete service: cascade delete for literature/case, including S3 object removal."""
from __future__ import annotations

import logging

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.config import get_s3_config
from app.models import CoreFile, LitMetadata, MedCase, Node, Edge
from app.storage import S3Client

LOGGER = logging.getLogger("admin_service")


class AdminDeleteRecordNotFound(Exception): ...


class AdminService:
    def __init__(self, db: Session) -> None:
        self._db = db

    def _remove_s3(self, storage_path: str) -> None:
        try:
            s3_config = get_s3_config()
            if s3_config.access_key and s3_config.secret_key:
                s3 = S3Client(s3_config)
                s3.remove_object(storage_path)
        except Exception:
            LOGGER.exception("S3 deletion failed for %s, proceeding", storage_path)

    def delete_lit(self, record_id: int) -> dict:
        db = self._db
        record = db.query(LitMetadata).filter(LitMetadata.id == record_id).first()
        if record is None:
            raise AdminDeleteRecordNotFound("Literature record not found")

        file_uuid = record.file_uuid

        core_file = db.query(CoreFile).filter(CoreFile.file_uuid == file_uuid).first()
        if core_file:
            self._remove_s3(core_file.storage_path)
            db.delete(core_file)

        related_cases = db.query(MedCase).filter(MedCase.file_uuid == file_uuid).all()
        for case in related_cases:
            db.delete(case)

        node = db.query(Node).filter(Node.title == record.title, Node.node_type == "paper").first()
        if node:
            db.query(Edge).filter(
                or_(Edge.source_id == node.id, Edge.target_id == node.id)
            ).delete()
            db.delete(node)

        db.delete(record)
        db.commit()
        return {"deleted": True, "id": record_id, "file_uuid": file_uuid}

    def delete_case(self, record_id: int) -> dict:
        db = self._db
        record = db.query(MedCase).filter(MedCase.id == record_id).first()
        if record is None:
            raise AdminDeleteRecordNotFound("Case record not found")

        lit = db.query(LitMetadata).filter(LitMetadata.file_uuid == record.file_uuid).first()
        if lit:
            node = db.query(Node).filter(Node.title == lit.title, Node.node_type == "record").first()
            if node:
                db.query(Edge).filter(
                    or_(Edge.source_id == node.id, Edge.target_id == node.id)
                ).delete()
                db.delete(node)

        db.delete(record)
        db.commit()
        return {"deleted": True, "id": record_id}
