from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

from loguru import logger
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings, settings
from core.exceptions import (
    AccessLimitedError,
    CaptchaDetectedError,
    CrawlerError,
    DetailPageParseError,
    LoginRequiredError,
    TitleNotMatchedError,
)
from database import AsyncSessionLocal
from models.schemas import (
    FailedRecordCreate,
    LitMetadataCreate,
    PaperMetadata,
    PendingFile,
    ProcessingSummary,
    SearchResult,
)
from repositories.core_file_repository import CoreFileRepository
from repositories.failed_record_repository import FailedRecordRepository
from repositories.lit_metadata_repository import LitMetadataRepository
from services.crawlers.base import BaseCrawler
from services.filename_cleaner import FilenameCleaner
from services.title_matcher import ExactTitleMatcher

ProcessingStatus = Literal["success", "partial", "failed", "skipped"]
ADVISORY_LOCK_NAMESPACE = 177832766


FAILURE_ACTIONS = {
    "missing_metadata_fields": "complete_metadata",
    "title_not_exact_match": "manual_check",
    "no_result": "check_site_manually",
    "page_parse_failed": "manual_check",
    "network_error": "retry_later",
    "timeout": "retry_later",
    "captcha_detected": "retry_later",
    "login_required": "check_site_manually",
    "access_limited": "retry_later",
    "unknown_error": "manual_check",
}


@dataclass
class SiteAttemptOutcome:
    success: bool
    site: str
    metadata: PaperMetadata | None = None
    match_result: SearchResult | None = None
    failure_reason: str | None = None
    error_message: str | None = None
    stop_processing: bool = False


class ExtractionService:
    """Coordinate scanning results, crawlers, strict matching, and persistence."""

    def __init__(
        self,
        yidu_crawler: BaseCrawler,
        nstl_crawler: BaseCrawler | None = None,
        cnki_crawler: BaseCrawler | None = None,
        app_settings: Settings = settings,
        session_factory: async_sessionmaker[AsyncSession] = AsyncSessionLocal,
        cleaner: FilenameCleaner | None = None,
        matcher: ExactTitleMatcher | None = None,
    ) -> None:
        self.yidu_crawler = yidu_crawler
        self.nstl_crawler = nstl_crawler
        self.cnki_crawler = cnki_crawler
        self.settings = app_settings
        self.session_factory = session_factory
        self.cleaner = cleaner or FilenameCleaner()
        self.matcher = matcher or ExactTitleMatcher()

    async def process_all(self, files: list[PendingFile]) -> ProcessingSummary:
        semaphore = asyncio.Semaphore(self.settings.CRAWLER_CONCURRENCY)
        lock = asyncio.Lock()
        counts: dict[ProcessingStatus, int] = {
            "success": 0,
            "partial": 0,
            "failed": 0,
            "skipped": 0,
        }

        async def bounded_process(file: PendingFile) -> None:
            async with semaphore:
                status = await self._process_one(file)
                async with lock:
                    counts[status] += 1

        await asyncio.gather(*(bounded_process(file) for file in files))

        summary = ProcessingSummary(
            total_files=len(files),
            success_count=counts["success"],
            partial_count=counts["partial"],
            failed_count=counts["failed"],
            skipped_count=counts["skipped"],
        )
        logger.info("Processing summary: {}", summary.model_dump())
        return summary

    async def process_one(self, file: PendingFile) -> None:
        await self._process_one(file)

    async def _process_one(self, file: PendingFile) -> ProcessingStatus:
        async with self.session_factory() as lock_session:
            lock_acquired = await self._try_acquire_file_lock(lock_session, file.file_uuid)
            if not lock_acquired:
                logger.info("Skipping locked file_uuid={}", file.file_uuid)
                return "skipped"
            try:
                return await self._process_one_locked(file)
            finally:
                await self._release_file_lock(lock_session, file.file_uuid)

    async def _process_one_locked(self, file: PendingFile) -> ProcessingStatus:
        file_name = file.file_name
        file_path = file.file_path
        cleaned_title = ""
        attempted_sites: list[str] = []

        try:
            cleaned_title = self.cleaner.clean(file_name)
            logger.info(
                "Processing file: file_name={}, file_path={}, cleaned_title={}",
                file_name,
                file_path,
                cleaned_title,
            )

            async with self.session_factory() as session:
                if self.settings.SKIP_EXISTING_RECORDS:
                    lit_repo = LitMetadataRepository(session)
                    existing_status = await lit_repo.get_crawl_status_by_file_uuid(file.file_uuid)
                    if existing_status == "success":
                        core_file_repo = CoreFileRepository(session)
                        await core_file_repo.mark_metadata_found(file.file_uuid)
                        await session.commit()
                        logger.info("Skipping existing file_uuid={}", file.file_uuid)
                        return "skipped"
                    if existing_status is not None:
                        logger.info(
                            "Reprocessing incomplete existing metadata: file_uuid={}, crawl_status={}",
                            file.file_uuid,
                            existing_status,
                        )

            yidu_outcome = await self._attempt_site("yidu", self.yidu_crawler, cleaned_title)
            attempted_sites.append("yidu")
            if yidu_outcome.success and yidu_outcome.metadata and yidu_outcome.match_result:
                missing_message = self._missing_metadata_message(yidu_outcome.metadata)
                if missing_message is None:
                    return await self._save_success(file, cleaned_title, yidu_outcome)
                last_reason = "missing_metadata_fields"
                last_message = missing_message
                logger.warning(
                    "Metadata incomplete: site={}, file_name={}, message={}",
                    yidu_outcome.site,
                    file.file_name,
                    missing_message,
                )
            else:
                last_reason = yidu_outcome.failure_reason or "unknown_error"
                last_message = yidu_outcome.error_message
            if yidu_outcome.stop_processing:
                await self._write_failed_record(file, cleaned_title, attempted_sites, last_reason, last_message)
                return "failed"

            if self.settings.ENABLE_NSTL and self.nstl_crawler is not None:
                nstl_outcome = await self._attempt_site("nstl", self.nstl_crawler, cleaned_title)
                attempted_sites.append("nstl")
                if nstl_outcome.success and nstl_outcome.metadata and nstl_outcome.match_result:
                    missing_message = self._missing_metadata_message(nstl_outcome.metadata)
                    if missing_message is None:
                        return await self._save_success(file, cleaned_title, nstl_outcome)
                    last_reason = "missing_metadata_fields"
                    last_message = missing_message
                    logger.warning(
                        "Metadata incomplete: site={}, file_name={}, message={}",
                        nstl_outcome.site,
                        file.file_name,
                        missing_message,
                    )

                last_reason, last_message = self._choose_failure(
                    last_reason,
                    last_message,
                    nstl_outcome.failure_reason,
                    nstl_outcome.error_message,
                )
                if nstl_outcome.stop_processing:
                    await self._write_failed_record(file, cleaned_title, attempted_sites, last_reason, last_message)
                    return "failed"

            if self.settings.ENABLE_CNKI and self.cnki_crawler is not None:
                cnki_outcome = await self._attempt_site("cnki", self.cnki_crawler, cleaned_title)
                attempted_sites.append("cnki")
                if cnki_outcome.success and cnki_outcome.metadata and cnki_outcome.match_result:
                    missing_message = self._missing_metadata_message(cnki_outcome.metadata)
                    if missing_message is None:
                        return await self._save_success(file, cleaned_title, cnki_outcome)
                    last_reason = "missing_metadata_fields"
                    last_message = missing_message
                    logger.warning(
                        "Metadata incomplete: site={}, file_name={}, message={}",
                        cnki_outcome.site,
                        file.file_name,
                        missing_message,
                    )

                last_reason, last_message = self._choose_failure(
                    last_reason,
                    last_message,
                    cnki_outcome.failure_reason,
                    cnki_outcome.error_message,
                )
                if cnki_outcome.stop_processing:
                    await self._write_failed_record(file, cleaned_title, attempted_sites, last_reason, last_message)
                    return "failed"

            await self._write_failed_record(file, cleaned_title, attempted_sites, last_reason, last_message)
            return "failed"

        except Exception as exc:
            reason = self._failure_reason_from_exception(exc)
            logger.exception(
                "Failed to process file: file_name={}, file_path={}, cleaned_title={}, reason={}",
                file_name,
                file_path,
                cleaned_title,
                reason,
            )
            await self._write_failed_record(file, cleaned_title, attempted_sites, reason, str(exc))
            return "failed"

    async def _attempt_site(self, site: str, crawler: BaseCrawler, cleaned_title: str) -> SiteAttemptOutcome:
        logger.info("Trying site: site={}, cleaned_title={}", site, cleaned_title)
        try:
            results = await crawler.search(cleaned_title)
            logger.info("Search results: site={}, count={}", site, len(results))
            for index, result in enumerate(results, start=1):
                logger.info("Search result title: site={}, index={}, title={}", site, index, result.title)

            if not results:
                return SiteAttemptOutcome(
                    success=False,
                    site=site,
                    failure_reason="no_result",
                    error_message=f"{site} returned no search results",
                )

            match_result = self.matcher.find_exact_match(cleaned_title, results)
            if match_result is None:
                logger.info("No exact title match: site={}, cleaned_title={}", site, cleaned_title)
                return SiteAttemptOutcome(
                    success=False,
                    site=site,
                    failure_reason="title_not_exact_match",
                    error_message=f"{site} returned results but no exact title match",
                )

            logger.info(
                "Exact title match found: site={}, expected_title={}, matched_title={}, detail_url={}",
                site,
                cleaned_title,
                match_result.title,
                match_result.detail_url,
            )
            metadata = await crawler.fetch_detail(match_result)
            return SiteAttemptOutcome(
                success=True,
                site=site,
                metadata=metadata,
                match_result=match_result,
            )
        except (CaptchaDetectedError, LoginRequiredError, AccessLimitedError) as exc:
            reason = self._failure_reason_from_exception(exc)
            logger.warning("Access issue on site: site={}, reason={}, message={}", site, reason, exc)
            return SiteAttemptOutcome(
                success=False,
                site=site,
                failure_reason=reason,
                error_message=str(exc),
                stop_processing=True,
            )
        except DetailPageParseError as exc:
            logger.warning("Detail parse failed: site={}, message={}", site, exc)
            return SiteAttemptOutcome(
                success=False,
                site=site,
                failure_reason="page_parse_failed",
                error_message=str(exc),
            )
        except TitleNotMatchedError as exc:
            logger.warning("Title not matched: site={}, message={}", site, exc)
            return SiteAttemptOutcome(
                success=False,
                site=site,
                failure_reason="title_not_exact_match",
                error_message=str(exc),
            )
        except CrawlerError as exc:
            reason = self._failure_reason_from_exception(exc)
            logger.warning("Crawler failed: site={}, reason={}, message={}", site, reason, exc)
            return SiteAttemptOutcome(
                success=False,
                site=site,
                failure_reason=reason,
                error_message=str(exc),
            )
        except Exception as exc:
            logger.exception("Unexpected crawler error: site={}, title={}", site, cleaned_title)
            return SiteAttemptOutcome(
                success=False,
                site=site,
                failure_reason="unknown_error",
                error_message=str(exc),
            )

    async def _save_success(
        self,
        file: PendingFile,
        cleaned_title: str,
        outcome: SiteAttemptOutcome,
    ) -> ProcessingStatus:
        if outcome.metadata is None or outcome.match_result is None:
            raise ValueError("Successful site outcome requires metadata and match_result")

        async with self.session_factory() as session:
            lit_repo = LitMetadataRepository(session)
            core_file_repo = CoreFileRepository(session)
            await lit_repo.upsert(
                LitMetadataCreate(
                    file_uuid=file.file_uuid,
                    original_name=file.file_name,
                    storage_path=file.file_path,
                    cleaned_title=cleaned_title,
                    title=outcome.metadata.title,
                    authors=outcome.metadata.authors,
                    abstract=outcome.metadata.abstract,
                    keywords=outcome.metadata.keywords,
                    paper_type=outcome.metadata.paper_type,
                    source_site=outcome.metadata.source_site,
                    source_url=outcome.metadata.source_url,
                    journal=outcome.metadata.journal,
                    pub_year=outcome.metadata.pub_year,
                    matched_title=outcome.match_result.title,
                    is_exact_match=True,
                    crawl_status="success",
                    error_message=None,
                )
            )
            await core_file_repo.mark_metadata_found(file.file_uuid)
            await session.commit()

        logger.info(
            "Saved metadata record: file_name={}, file_uuid={}, source_site={}, crawl_status={}",
            file.file_name,
            file.file_uuid,
            outcome.site,
            "success",
        )
        return "success"

    async def _write_failed_record(
        self,
        file: PendingFile,
        cleaned_title: str,
        attempted_sites: list[str],
        failure_reason: str,
        error_message: str | None,
    ) -> None:
        suggested_action = FAILURE_ACTIONS.get(failure_reason, "manual_check")
        data = FailedRecordCreate(
            file_uuid=file.file_uuid,
            file_name=file.file_name,
            file_path=file.file_path,
            cleaned_title=cleaned_title,
            attempted_sites=attempted_sites,
            failure_reason=failure_reason,
            error_message=error_message,
            suggested_action=suggested_action,
        )
        async with self.session_factory() as session:
            repo = FailedRecordRepository(session)
            await repo.upsert(data)
        logger.info(
            "Saved failed record: file_name={}, attempted_sites={}, failure_reason={}, suggested_action={}",
            file.file_name,
            attempted_sites,
            failure_reason,
            suggested_action,
        )

    @staticmethod
    def _missing_metadata_fields(metadata: PaperMetadata) -> list[str]:
        missing_fields: list[str] = []
        if not metadata.title:
            missing_fields.append("title")
        if not metadata.authors:
            missing_fields.append("authors")
        if not metadata.abstract:
            missing_fields.append("abstract")
        if not metadata.keywords:
            missing_fields.append("keywords")
        if not metadata.paper_type or metadata.paper_type == "unknown":
            missing_fields.append("paper_type")

        return missing_fields

    @classmethod
    def _missing_metadata_message(cls, metadata: PaperMetadata) -> str | None:
        missing_fields = cls._missing_metadata_fields(metadata)
        if not missing_fields:
            return None
        return f"Missing metadata fields: {', '.join(missing_fields)}"

    @staticmethod
    def _choose_failure(
        current_reason: str,
        current_message: str | None,
        new_reason: str | None,
        new_message: str | None,
    ) -> tuple[str, str | None]:
        if current_reason == "missing_metadata_fields":
            return current_reason, current_message
        return new_reason or current_reason, new_message or current_message

    @staticmethod
    async def _try_acquire_file_lock(session: AsyncSession, file_uuid: str) -> bool:
        result = await session.execute(
            text(
                "select pg_try_advisory_lock("
                ":namespace, hashtext(cast(:file_uuid as text))"
                ")"
            ),
            {"namespace": ADVISORY_LOCK_NAMESPACE, "file_uuid": file_uuid},
        )
        return bool(result.scalar())

    @staticmethod
    async def _release_file_lock(session: AsyncSession, file_uuid: str) -> None:
        result = await session.execute(
            text(
                "select pg_advisory_unlock("
                ":namespace, hashtext(cast(:file_uuid as text))"
                ")"
            ),
            {"namespace": ADVISORY_LOCK_NAMESPACE, "file_uuid": file_uuid},
        )
        if not bool(result.scalar()):
            logger.warning("File advisory lock was not held: file_uuid={}", file_uuid)

    @staticmethod
    def _failure_reason_from_exception(exc: Exception) -> str:
        return getattr(exc, "failure_reason", "unknown_error")
