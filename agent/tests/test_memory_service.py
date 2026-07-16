from dataclasses import dataclass

from agent.memory.service import MemoryService


@dataclass
class FakeMessage:
    id: int
    role: str
    content: str
    references: list[dict] | None = None


@dataclass
class FakeSummary:
    content: str
    referenced_sources_summary: list[dict] | None = None
    covered_message_id: int | None = None


class FakeSummaryService:
    def __init__(self):
        self.calls = []

    def summarize(self, previous_summary, archived_messages):
        self.calls.append((previous_summary, archived_messages))
        return "已压缩的会话摘要"


class FakeRepository:
    def __init__(self, summary=None, recent_messages=None, archived_messages=None):
        self.summary = summary
        self.recent_messages = recent_messages or []
        self.archived_messages = archived_messages or []
        self.saved = None

    def get_active_summary_record(self, conversation_id: int):
        assert conversation_id == 1
        return self.summary

    def get_recent_messages(self, conversation_id: int, limit: int):
        assert conversation_id == 1
        assert limit == 8
        return self.recent_messages

    def get_messages_outside_recent_window(self, conversation_id, recent_message_limit, after_message_id):
        assert conversation_id == 1
        assert recent_message_limit == 8
        return [message for message in self.archived_messages if message.id > after_message_id]

    def save_active_summary(self, **payload):
        self.saved = payload


def test_memory_service_builds_context_from_summary_and_recent_messages():
    repository = FakeRepository(
        summary=FakeSummary(
            content="前文主要讨论多囊促排方案。",
            referenced_sources_summary=[
                {"title": "历史文献", "file_uuid": "old-file", "source_type": "paper"}
            ],
            covered_message_id=2,
        ),
        recent_messages=[
            FakeMessage(id=3, role="user", content="多囊患者促排方案怎么选？"),
            FakeMessage(
                id=4,
                role="assistant",
                content="可以结合病案经验讨论。",
                references=[
                    {
                        "index": 1,
                        "source_type": "record",
                        "title": "case_多囊促排病案.md",
                        "file_uuid": "file-1",
                        "snippet": "病案片段",
                    }
                ],
            ),
        ],
    )

    context = MemoryService(repository=repository).build_context(1)

    assert context.summary == "前文主要讨论多囊促排方案。"
    assert len(context.recent_messages) == 2
    assert context.recent_messages[1].references[0]["file_uuid"] == "file-1"
    assert [reference["file_uuid"] for reference in context.referenced_sources] == ["file-1", "old-file"]


def test_memory_service_rolls_only_messages_outside_recent_window():
    summary_service = FakeSummaryService()
    repository = FakeRepository(
        summary=FakeSummary(content="旧摘要", covered_message_id=2),
        archived_messages=[
            FakeMessage(id=3, role="user", content="旧问题"),
            FakeMessage(
                id=4,
                role="assistant",
                content="旧回答",
                references=[
                    {"title": "归档来源", "file_uuid": "archive-file", "source_type": "paper"}
                ],
            ),
        ],
    )
    service = MemoryService(repository=repository, summary_service=summary_service)

    changed = service.refresh_summary(1)

    assert changed is True
    assert summary_service.calls[0][0] == "旧摘要"
    assert [message.content for message in summary_service.calls[0][1]] == ["旧问题", "旧回答"]
    assert repository.saved["content"] == "已压缩的会话摘要"
    assert repository.saved["covered_message_id"] == 4
    assert repository.saved["referenced_sources_summary"][0]["file_uuid"] == "archive-file"


def test_memory_service_skips_summary_when_no_messages_leave_the_window():
    summary_service = FakeSummaryService()
    repository = FakeRepository()
    service = MemoryService(repository=repository, summary_service=summary_service)

    assert service.refresh_summary(1) is False
    assert summary_service.calls == []
    assert repository.saved is None
