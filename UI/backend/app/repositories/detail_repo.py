"""Paper/record detail and file reference queries."""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, or_

from app.models import CoreFile, LitMetadata, MedCase, Node


class DetailRepoMixin:
    def fetch_paper_detail_by_title(self, title: str) -> dict[str, Any] | None:
        with self._get_session() as session:
            order_case = case(
                (LitMetadata.title == title, 0),
                (LitMetadata.matched_title == title, 1),
                (LitMetadata.cleaned_title == title, 2),
                (LitMetadata.original_name == title, 3),
                else_=4,
            )

            row = (
                session.query(LitMetadata)
                .filter(
                    or_(
                        LitMetadata.title == title,
                        LitMetadata.matched_title == title,
                        LitMetadata.cleaned_title == title,
                        LitMetadata.original_name == title,
                    )
                )
                .order_by(order_case, LitMetadata.updated_at.desc())
                .first()
            )
            if row:
                return self._lit_to_dict(row)

            like_pattern = f"%{title}%"
            row = (
                session.query(LitMetadata)
                .filter(
                    or_(
                        LitMetadata.title.ilike(like_pattern),
                        LitMetadata.matched_title.ilike(like_pattern),
                        LitMetadata.cleaned_title.ilike(like_pattern),
                        LitMetadata.original_name.ilike(like_pattern),
                    )
                )
                .order_by(LitMetadata.updated_at.desc())
                .first()
            )
            return self._lit_to_dict(row) if row else None

    def get_file_reference_by_node_id(self, node_id: str) -> dict[str, Any] | None:
        with self._get_session() as session:
            node = session.query(Node).filter(Node.id == node_id).first()
            if not node:
                return None

            title = node.title
            order_case = case(
                (LitMetadata.title == title, 0),
                (LitMetadata.matched_title == title, 1),
                (LitMetadata.cleaned_title == title, 2),
                (LitMetadata.original_name == title, 3),
                else_=4,
            )

            lm = (
                session.query(LitMetadata)
                .filter(
                    or_(
                        LitMetadata.title == title,
                        LitMetadata.matched_title == title,
                        LitMetadata.cleaned_title == title,
                        LitMetadata.original_name == title,
                    )
                )
                .order_by(order_case, LitMetadata.updated_at.desc())
                .first()
            )

            file_name = None
            file_key = None
            if lm:
                cf = session.query(CoreFile).filter(CoreFile.file_uuid == lm.file_uuid).first()
                if cf:
                    file_name = cf.original_name
                    file_key = cf.storage_path

            return {
                "node_id": node.id,
                "node_type": node.node_type,
                "node_title": node.title,
                "file_name": file_name,
                "file_key": file_key,
            }

    def get_file_reference_by_file_uuid(self, file_uuid: str) -> dict[str, Any] | None:
        with self._get_session() as session:
            cf = session.query(CoreFile).filter(CoreFile.file_uuid == file_uuid).first()
            if not cf:
                return None
            return {
                "node_id": file_uuid,
                "node_type": "paper",
                "node_title": cf.original_name,
                "file_name": cf.original_name,
                "file_key": cf.storage_path,
            }

    def fetch_record_detail_by_title(self, title: str) -> dict[str, Any] | None:
        with self._get_session() as session:
            order_case = case(
                (LitMetadata.title == title, 0),
                (LitMetadata.matched_title == title, 1),
                (LitMetadata.cleaned_title == title, 2),
                (LitMetadata.original_name == title, 3),
                else_=4,
            )

            row = (
                session.query(MedCase, LitMetadata.title.label("literature_title"))
                .join(LitMetadata, MedCase.file_uuid == LitMetadata.file_uuid)
                .filter(
                    or_(
                        LitMetadata.title == title,
                        LitMetadata.matched_title == title,
                        LitMetadata.cleaned_title == title,
                        LitMetadata.original_name == title,
                    )
                )
                .order_by(order_case, MedCase.updated_at.desc())
                .first()
            )
            if row:
                return self._record_to_dict(row)

            like_pattern = f"%{title}%"
            row = (
                session.query(MedCase, LitMetadata.title.label("literature_title"))
                .join(LitMetadata, MedCase.file_uuid == LitMetadata.file_uuid)
                .filter(
                    or_(
                        LitMetadata.title.ilike(like_pattern),
                        LitMetadata.matched_title.ilike(like_pattern),
                        LitMetadata.cleaned_title.ilike(like_pattern),
                        LitMetadata.original_name.ilike(like_pattern),
                    )
                )
                .order_by(MedCase.updated_at.desc())
                .first()
            )
            return self._record_to_dict(row) if row else None

    def fetch_paper_detail_by_file_uuid(self, file_uuid: str) -> dict[str, Any] | None:
        with self._get_session() as session:
            row = session.query(LitMetadata).filter(LitMetadata.file_uuid == file_uuid).first()
            return self._lit_to_dict(row) if row else None

    def fetch_record_detail_by_file_uuid(self, file_uuid: str) -> dict[str, Any] | None:
        with self._get_session() as session:
            row = (
                session.query(MedCase, LitMetadata.title.label("literature_title"))
                .join(LitMetadata, MedCase.file_uuid == LitMetadata.file_uuid)
                .filter(MedCase.file_uuid == file_uuid)
                .first()
            )
            if row:
                return self._record_to_dict(row)
            mc = session.query(MedCase).filter(MedCase.file_uuid == file_uuid).first()
            if mc:
                return self._record_to_dict((mc, None))
            return None
