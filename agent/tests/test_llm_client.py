import json

from agent.config import AgentSettings
from agent.services.llm_client import LLMClient


def test_llm_client_posts_qwen_compatible_chat_completion(monkeypatch):
    captured = {}

    class FakeResponse:
        ok = True
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": "模型回答"}}]}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("agent.services.llm_client.requests.post", fake_post)
    client = LLMClient(
        AgentSettings(
            llm_provider="openai",
            llm_base_url="https://dashscope.aliyuncs.com/compatible-mode",
            llm_api_key="secret",
            llm_model="qwen-plus",
            llm_timeout_seconds=7,
        )
    )

    text = client.generate("你好", system_prompt="系统提示")

    assert text == "模型回答"
    assert captured["url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["json"]["model"] == "qwen-plus"
    assert captured["json"]["messages"][0]["role"] == "system"
    assert captured["json"]["messages"][0]["content"] == "系统提示"
    assert captured["json"]["messages"][1]["role"] == "user"
    assert captured["json"]["messages"][1]["content"] == "你好"
    assert "stream" not in captured["json"]
    assert captured["timeout"] == 7


def test_llm_client_streams_qwen_compatible_deltas(monkeypatch):
    captured = {}

    class FakeResponse:
        ok = True
        status_code = 200
        text = ""

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def iter_lines(self, decode_unicode=True):
            chunks = [
                {"choices": [{"delta": {"content": "你"}}]},
                {"choices": [{"delta": {"content": "好"}}]},
            ]
            for chunk in chunks:
                yield "data: " + json.dumps(chunk, ensure_ascii=False)
            yield "data: [DONE]"

    def fake_post(url, headers, json, timeout, stream):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        captured["stream"] = stream
        return FakeResponse()

    monkeypatch.setattr("agent.services.llm_client.requests.post", fake_post)
    client = LLMClient(
        AgentSettings(
            llm_provider="openai",
            llm_base_url="https://dashscope.aliyuncs.com/compatible-mode",
            llm_api_key="secret",
            llm_model="qwen-plus",
            llm_timeout_seconds=7,
        )
    )

    chunks = list(client.stream_generate("你好", system_prompt="系统提示"))

    assert chunks == ["你", "好"]
    assert captured["json"]["stream"] is True
    assert captured["stream"] is True
    assert captured["headers"]["Accept"] == "text/event-stream"
