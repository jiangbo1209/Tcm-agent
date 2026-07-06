from agent.schemas.stream import StreamEvent
from agent.services.stream_service import StreamService


def test_stream_service_encodes_sse_events():
    events = [StreamEvent(event="answer_delta", data={"content": "你好"})]

    encoded = list(StreamService().encode(events))

    assert encoded[0].startswith("data: ")
    assert "answer_delta" in encoded[0]
