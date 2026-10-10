import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.exceptions import (
    AuthenticationError,
    ContentFilterError,
    JSONParseError,
    LLMError,
    NetworkError,
    RateLimitError,
)
from app.llm_client import LLMClient


@pytest.fixture
def client(sample_config) -> LLMClient:
    instance = LLMClient(sample_config)
    yield instance
    instance.close()


def _response(status_code: int, body: dict) -> httpx.Response:
    return httpx.Response(status_code, json=body)


def _success_body(
    content: str, finish_reason: str = "stop"
) -> dict[str, object]:
    return {
        "choices": [
            {
                "message": {"role": "assistant", "content": content},
                "finish_reason": finish_reason,
            }
        ]
    }


def test_chat_builds_authorized_request_and_extracts_content(
    client: LLMClient,
) -> None:
    fake_response = _response(200, _success_body("mocked answer"))

    with patch.object(client._client, "post", return_value=fake_response) as post:
        result = client.chat("test prompt")

    assert result == "mocked answer"
    request = post.call_args.kwargs
    assert request["headers"]["Authorization"] == "Bearer sk-test-key-123456"
    assert request["url"] == "https://api.example.com/v1/chat/completions"
    assert request["json"]["messages"][-1]["content"] == "test prompt"


def test_chat_401_raises_authentication_error(client: LLMClient) -> None:
    response = _response(
        401,
        {"error": {"message": "Invalid API key", "type": "authentication_error"}},
    )

    with patch.object(client._client, "post", return_value=response):
        with pytest.raises(AuthenticationError, match="认证失败"):
            client.chat("test")


def test_chat_429_raises_rate_limit_error(client: LLMClient) -> None:
    response = _response(
        429,
        {"error": {"message": "Rate limit exceeded", "type": "rate_limit_error"}},
    )

    with patch.object(client._client, "post", return_value=response):
        with pytest.raises(RateLimitError):
            client.chat("test")


def test_chat_adds_warning_when_response_is_truncated(client: LLMClient) -> None:
    response = _response(200, _success_body("partial answer", "length"))

    with patch.object(client._client, "post", return_value=response):
        result = client.chat("test")

    assert result.startswith("partial answer")
    assert "截断" in result
    assert "max_tokens" in result


def test_parse_response_rejects_invalid_json(client: LLMClient) -> None:
    response = httpx.Response(200, text="not json")

    with pytest.raises(JSONParseError):
        client._parse_response(response)


def test_parse_response_rejects_invalid_shape(client: LLMClient) -> None:
    response = _response(200, {"choices": []})

    with pytest.raises(LLMError, match="choices"):
        client._parse_response(response)


def test_parse_response_rejects_content_filter(client: LLMClient) -> None:
    response = _response(200, _success_body("filtered", "content_filter"))

    with pytest.raises(ContentFilterError):
        client._parse_response(response)


def test_async_chat_uses_async_http_client(
    client: LLMClient, sample_messages: list[dict[str, str]]
) -> None:
    fake_response = _response(200, _success_body("async answer"))
    async_http = MagicMock()
    async_http.post = AsyncMock(return_value=fake_response)
    async_context = MagicMock()
    async_context.__aenter__ = AsyncMock(return_value=async_http)
    async_context.__aexit__ = AsyncMock(return_value=None)

    with patch("llm_client.httpx.AsyncClient", return_value=async_context):
        result = asyncio.run(client.async_chat_with_history(sample_messages))

    assert result == "async answer"
    async_http.post.assert_awaited_once()
