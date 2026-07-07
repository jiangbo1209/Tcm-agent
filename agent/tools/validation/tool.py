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

    def run(self, question: str, answer: str, evidence: list[Evidence]) -> ValidationResult:
        base_result = ValidationResult(
            grounded=bool(evidence),
            message=(
                "回答基于知识库检索结果生成。"
                if evidence
                else "当前知识库没有检索到足够相关资料，本回答基于普通医学知识生成，请结合医生判断。"
            ),
        )
        if not self._enabled:
            return base_result
        guidelines = self._guideline_retriever.retrieve(question, answer=answer)
        checked = self._guideline_checker.check(
            question=question,
            answer=answer,
            guidelines=guidelines,
            evidence=evidence,
        )
        checked.grounded = base_result.grounded
        if checked.issues:
            checked.message = f"{base_result.message} 但指南核对发现需要谨慎表述的内容。"
        else:
            checked.message = base_result.message
        return checked
