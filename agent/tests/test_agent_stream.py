from agent.orchestrator.agent import MedicalAgent
from agent.orchestrator.response_builder import ResponseBuilder
from agent.schemas.answer import AnswerResult
from agent.schemas.chat import ChatRequest
from agent.schemas.query import QueryPlan
from agent.schemas.retrieval import RetrievalResult
from agent.schemas.validation import ValidationResult


class FakeQueryAnalyzer:
    def analyze(self, question: str, top_k=None):
        return QueryPlan(
            intent="literature_question",
            source_type="paper",
            rewritten_query=question,
            search_type="literature",
            top_k=top_k or 3,
        )


class FakeRetrievalTool:
    def run(self, payload):
        return RetrievalResult(evidence=[], total=0)


class FakeAnswerGenerator:
    def generate(self, question, query_plan, evidence, total):
        return AnswerResult(answer="完整回答")

    def stream_generate(self, question, query_plan, evidence, total):
        return iter(["流", "式", "回答"]), [], [], []


class FakeValidationTool:
    def run(self, question, answer, evidence):
        return ValidationResult(grounded=False, message="当前知识库没有检索到足够相关资料，本回答基于普通医学知识生成，请结合医生判断。")


def test_agent_run_stream_emits_workflow_events():
    agent = MedicalAgent(
        query_analyzer=FakeQueryAnalyzer(),
        retrieval_tool=FakeRetrievalTool(),
        answer_generator=FakeAnswerGenerator(),
        validation_tool=FakeValidationTool(),
        response_builder=ResponseBuilder(),
    )

    events = list(agent.run_stream(ChatRequest(question="多囊有哪些文献证据？", top_k=3)))
    names = [event.event for event in events]

    assert names == [
        "started",
        "query_plan",
        "retrieval_done",
        "answer_delta",
        "answer_delta",
        "answer_delta",
        "answer_done",
        "validation_done",
        "done",
    ]
    assert events[-1].data["answer"] == "流式回答"
