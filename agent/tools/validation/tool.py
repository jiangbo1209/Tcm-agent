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
        if not self._enabled:
            return ValidationResult(passed=True, risk_level="low", issues=[])
        guidelines = self._guideline_retriever.retrieve(question, answer=answer)
        return self._guideline_checker.check(
            question=question,
            answer=answer,
            guidelines=guidelines,
            evidence=evidence,
        )
