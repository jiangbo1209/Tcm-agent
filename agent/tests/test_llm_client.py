from agent.config import AgentSettings
from agent.services.llm_client import LLMClient


def test_llm_client_posts_openai_compatible_chat_completion(monkeypatch):
    captured = {}

    class FakeResponse:
        ok = True
        status_code = 200
        text = ""

        def json(self):
            return {
                "choices": [
                    {
                        "message": {"content": "模型回答"}
                    }
                ]
            }

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
            llm_base_url="https://relay.example",
            llm_api_key="secret",
            llm_model="qwen-plus",
            llm_timeout_seconds=7,
        )
    )

    text = client.generate("你好", system_prompt="系统提示")

    assert text == "模型回答"
    assert captured["url"] == "https://relay.example/v1/chat/completions"
    assert captured["headers"]["Authorization"] == "Bearer secret"
    assert captured["json"]["model"] == "qwen-plus"
    assert captured["json"]["messages"][0]["role"] == "system"
    assert captured["json"]["messages"][0]["content"] == "系统提示"
    assert captured["json"]["messages"][1]["role"] == "user"
    assert captured["json"]["messages"][1]["content"] == "你好"
    assert captured["timeout"] == 7
