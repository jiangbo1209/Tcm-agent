"""Core service: query pending lit_metadata, download PDF, generate AI summary, update DB."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from data_process.lit_metadata.app.models.orm import LitMetadata
from data_process.pdf_upload.config import get_minio_config, get_postgres_config
from data_process.pdf_upload.minio_client import MinioClient

from .llm_client import build_payload, call_llm_stream, MAX_RETRIES, RETRY_DELAY

LOGGER = logging.getLogger("ai_summary")

_MODULE_DIR = Path(__file__).resolve().parent
_PROMPT_PATH = _MODULE_DIR / "prompt.md"


_PAPER_TYPE_CN: dict[str, str] = {
    "journal": "期刊",
    "master": "硕士学位论文",
    "phd": "博士学位论文",
    "conference": "会议论文",
    "newspaper": "报纸",
    "guideline": "指南/报告",
}

_METADATA_CONTEXT_BASE = (
    "【重要定位信息】\n"
    "当前 PDF 文件类型为「{paper_type_cn}」。\n"
    "以下是你需要摘要的目标论文的准确元数据，请仅针对这一篇论文进行摘要，忽略 PDF 中其他无关论文或栏目：\n"
    "- 论文标题: {title}\n"
    "- 作者: {authors}\n"
    "- 来源: {journal}\n"
    "- 发表年份: {pub_year}\n\n"
    "请严格聚焦于上述论文内容：若 PDF 为期刊排版（一页含多篇不同论文），务必根据上述标题和作者识"
    "别出正确论文所在位置，仅对目标论文做摘要，切勿将其他论文内容混入。\n"
    "若 PDF 为学位论文或报告（全文即单一论文），则将上述元数据作为内容验证参考，确保摘要与论文匹配。"
)


class AiSummaryService:
    def __init__(self) -> None:
        pg_config = get_postgres_config()
        self._engine = create_async_engine(pg_config.dsn, echo=False, pool_size=5)
        self._session_factory = async_sessionmaker(self._engine, expire_on_commit=False)
        self._minio = MinioClient(get_minio_config())
        self._prompt_template = _PROMPT_PATH.read_text(encoding="utf-8").strip()

    def _build_prompt(self, record: LitMetadata) -> str:
        paper_type_cn = _PAPER_TYPE_CN.get(record.paper_type or "", "文献")
        authors_str = ", ".join(record.authors) if record.authors else "未知"
        journal_str = record.journal or "未知"
        pub_year_str = record.pub_year or "未知"
        title_str = record.title or record.cleaned_title or record.original_name

        metadata_context = _METADATA_CONTEXT_BASE.format(
            paper_type_cn=paper_type_cn,
            title=title_str,
            authors=authors_str,
            journal=journal_str,
            pub_year=pub_year_str,
        )
        return self._prompt_template.format(metadata_context=metadata_context)

    async def process_pending(self, limit: int | None = None) -> dict[str, int]:
        summary = {"total": 0, "success": 0, "failed": 0, "skipped": 0}

        async with self._session_factory() as session:
            stmt = (
                select(LitMetadata)
                .where(LitMetadata.ai_summary_status == "pending")
                .order_by(LitMetadata.id.asc())
            )
            if limit is not None:
                stmt = stmt.limit(limit)
            result = await session.execute(stmt)
            records = result.scalars().all()

            summary["total"] = len(records)
            if not records:
                LOGGER.info("No pending lit_metadata records for AI summary")
                return summary

            LOGGER.info(
                "Found %d pending records%s",
                len(records),
                f" (limit={limit})" if limit is not None else "",
            )

            for record in records:
                try:
                    success = await self._process_one(session, record)
                except Exception as exc:
                    await session.rollback()
                    LOGGER.exception("Unexpected failure for %s", record.original_name)
                    try:
                        await session.execute(
                            update(LitMetadata)
                            .where(LitMetadata.id == record.id)
                            .values(
                                ai_summary_status="failed",
                                error_message=f"Unexpected error: {exc}",
                            )
                        )
                        await session.commit()
                    except Exception:
                        await session.rollback()
                    summary["failed"] += 1
                    continue

                if success:
                    summary["success"] += 1
                else:
                    summary["failed"] += 1

        return summary

    async def _process_one(self, session: AsyncSession, record: LitMetadata) -> bool:
        t_start = time.monotonic()
        LOGGER.info("Processing: %s", record.original_name)

        if not record.storage_path:
            elapsed = time.monotonic() - t_start
            LOGGER.warning("No storage_path for %s, marking as failed", record.original_name)
            await session.execute(
                update(LitMetadata)
                .where(LitMetadata.id == record.id)
                .values(
                    ai_summary_status="failed",
                    error_message="Missing storage_path",
                )
            )
            await session.commit()
            LOGGER.info("RESULT | FAIL | %s | reason=no_storage_path | elapsed=%.1fs", record.original_name, elapsed)
            return False

        try:
            pdf_bytes = self._minio.get_object(record.storage_path)
        except Exception as exc:
            elapsed = time.monotonic() - t_start
            LOGGER.exception("MinIO download failed for %s", record.storage_path)
            await session.execute(
                update(LitMetadata)
                .where(LitMetadata.id == record.id)
                .values(
                    ai_summary_status="failed",
                    error_message=f"MinIO download failed: {exc}",
                )
            )
            await session.commit()
            LOGGER.info(
                "RESULT | FAIL | %s | phase=download | elapsed=%.1fs | error=%s",
                record.original_name, elapsed, exc,
            )
            return False

        LOGGER.info("Downloaded %s (%d bytes)", record.original_name, len(pdf_bytes))

        raw_text: str | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                prompt = self._build_prompt(record)
                payload = build_payload(prompt, pdf_bytes)
                raw_text = call_llm_stream(payload)
                break
            except Exception as exc:
                LOGGER.warning(
                    "Attempt %d/%d failed for %s: %s",
                    attempt, MAX_RETRIES, record.original_name, exc,
                )
                if attempt >= MAX_RETRIES:
                    elapsed = time.monotonic() - t_start
                    await session.execute(
                        update(LitMetadata)
                        .where(LitMetadata.id == record.id)
                        .values(
                            ai_summary_status="failed",
                            error_message=f"LLM call failed after {MAX_RETRIES} retries: {exc}",
                        )
                    )
                    await session.commit()
                    LOGGER.info(
                        "RESULT | FAIL | %s | phase=llm | elapsed=%.1fs | retries=%d | error=%s",
                        record.original_name, elapsed, MAX_RETRIES, exc,
                    )
                    return False
                await asyncio.sleep(RETRY_DELAY)

        if not raw_text:
            elapsed = time.monotonic() - t_start
            await session.execute(
                update(LitMetadata)
                .where(LitMetadata.id == record.id)
                .values(
                    ai_summary_status="failed",
                    error_message="LLM returned empty text",
                )
            )
            await session.commit()
            LOGGER.info("RESULT | FAIL | %s | phase=llm | elapsed=%.1fs | error=empty_output", record.original_name, elapsed)
            return False

        await session.execute(
            update(LitMetadata)
            .where(LitMetadata.id == record.id)
            .values(
                ai_summary=raw_text,
                ai_summary_status="completed",
            )
        )
        await session.commit()

        elapsed = time.monotonic() - t_start
        summary_len = len(raw_text)
        LOGGER.info(
            "RESULT | OK | %s | elapsed=%.1fs | summary_length=%d",
            record.original_name, elapsed, summary_len,
        )
        return True

    async def dispose(self) -> None:
        await self._engine.dispose()
