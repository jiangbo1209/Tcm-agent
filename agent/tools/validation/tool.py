"""GuidelineValidationTool entry."""

from __future__ import annotations

from agent.schemas.retrieval import Evidence
from agent.schemas.validation import ValidationResult
from agent.tools.validation.guideline_checker import GuidelineChecker
from agent.tools.validation.guideline_retriever import GuidelineRetriever


class GuidelineValidationTool:
    name = "guideline_validation"

    def __init__(
        self,
        guideline_retriever: GuidelineRetriever | None = None,
        guideline_checker: GuidelineChecker | None = None,
        enabled: bool = False,
    ) -> None:
        self._guideline_retriever = guideline_retriever or GuidelineRetriever()
        self._guideline_checker = guideline_checker or GuidelineChecker()
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def run(
        self,
        question: str,
        answer: str,
        evidence: list[Evidence],
        evidence_status: str = "not_checked",
    ) -> ValidationResult:
        if evidence_status == "source_only":
            return ValidationResult(
                grounded=True,
                message="回答基于上一轮引用来源上下文生成，未重新检索知识库。",
            )

        grounded = evidence_status == "grounded" or (evidence_status == "not_checked" and bool(evidence))
        base_result = ValidationResult(
            grounded=grounded,
            message=(
                "回答基于知识库检索结果生成。"
                if grounded
                else "当前知识库没有检索到能够直接支撑本问题的资料，本回答基于一般医学知识生成，请结合医生判断。"
            ),
        )
        if not self._enabled or not grounded:
            return base_result

        guidelines = self._guideline_retriever.retrieve(question, answer=answer)
        checked = self._guideline_checker.check(
            question=question,
            answer=answer,
            guidelines=guidelines,
            evidence=evidence,
        )
        checked.grounded = base_result.grounded
        checked.message = (
            f"{base_result.message} 但指南核对发现需要谨慎表述的内容。"
            if checked.issues
            else base_result.message
        )
        return checked
