"""Paper/record detail and file reference queries."""

from __future__ import annotations

from typing import Any

from sqlalchemy import case, or_

from app.models import LitMetadata, MedCase

from app.repositories.base import BaseRepository


class DetailRepository(BaseRepository):
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

    @staticmethod
    def _lit_to_dict(row: LitMetadata) -> dict[str, Any]:
        return {
            "id": row.id,
            "file_uuid": row.file_uuid,
            "original_name": row.original_name,
            "storage_path": row.storage_path,
            "cleaned_title": row.cleaned_title,
            "title": row.title,
            "authors": row.authors,
            "abstract": row.abstract,
            "keywords": row.keywords,
            "paper_type": row.paper_type,
            "source_site": row.source_site,
            "source_url": row.source_url,
            "journal": row.journal,
            "pub_year": row.pub_year,
            "matched_title": row.matched_title,
            "is_exact_match": row.is_exact_match,
            "crawl_status": row.crawl_status,
            "error_message": row.error_message,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }

    @staticmethod
    def _record_to_dict(row) -> dict[str, Any]:
        mc = row[0]
        return {
            "id": mc.id,
            "file_uuid": mc.file_uuid,
            "age": mc.age,
            "bmi": mc.bmi,
            "menstruation": mc.menstruation,
            "infertility": mc.infertility,
            "lifestyle": mc.lifestyle,
            "present_symptoms": mc.present_symptoms,
            "medical_history": mc.medical_history,
            "lab_tests": mc.lab_tests,
            "ultrasound": mc.ultrasound,
            "followup": mc.followup,
            "western_diagnosis": mc.western_diagnosis,
            "tcm_diagnosis": mc.tcm_diagnosis,
            "treatment_principle": mc.treatment_principle,
            "prescription": mc.prescription,
            "acupoints": mc.acupoints,
            "assisted_reproduction": mc.assisted_reproduction,
            "western_medicine": mc.western_medicine,
            "efficacy": mc.efficacy,
            "adverse_reactions": mc.adverse_reactions,
            "commentary": mc.commentary,
            "created_at": mc.created_at,
            "updated_at": mc.updated_at,
            "literature_title": row[1] if len(row) > 1 else None,
        }
