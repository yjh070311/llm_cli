"""OpenAI-compatible LLM API 客户端。"""

from typing import Any

import httpx

from config import AppConfig
from exceptions import (
    AuthenticationError,
    ContentFilterError,
    HTTPStatusError,
    JSONParseError,
    LLMError,
    ModelError,
    NetworkError,
    RateLimitError,
    TimeoutError,
)


VALID_ROLES = {"system", "user", "assistant"}


class LLMClient:
    """封装同步和异步 LLM 对话请求。"""

    CHAT_ENDPOINT = "/v1/chat/completions"
    _TIMEOUT = httpx.Timeout(90.0, connect=10.0)

    def __init__(self, config: AppConfig):
        self._base_url = config.base_url.rstrip("/")
        self._api_key = config.api_key
        self._model = config.model
        self._client = httpx.Client(timeout=self._TIMEOUT)

    def close(self) -> None:
        """释放同步 HTTP 客户端资源。"""
        self._client.close()

    def __enter__(self) -> "LLMClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """发送单轮对话请求。"""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat_with_history(
            messages, temperature=temperature, max_tokens=max_tokens
        )

    def chat_with_history(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """发送包含完整上下文的同步对话请求。"""
        self._validate_messages(messages)
        request = self._build_request(messages, temperature, max_tokens)

        try:
            response = self._client.post(**request)
        except httpx.ConnectError as error:
            raise NetworkError(self._connection_error_message()) from error
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as error:
            raise TimeoutError(
                f"LLM API 请求超时: {self._base_url}\n"
                "建议: 缩短 prompt 或换更快的模型"
            ) from error
        except httpx.RequestError as error:
            raise NetworkError(f"LLM API 请求失败: {error}") from error

        self._handle_error_status(response)
        return self._parse_response(response)

    async def async_chat(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """发送单轮异步对话请求。"""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.async_chat_with_history(
            messages, temperature=temperature, max_tokens=max_tokens
        )

    async def async_chat_with_history(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> str:
        """发送包含完整上下文的异步对话请求。"""
        self._validate_messages(messages)
        request = self._build_request(messages, temperature, max_tokens)

        try:
            async with httpx.AsyncClient(timeout=self._TIMEOUT) as client:
                response = await client.post(**request)
        except httpx.ConnectError as error:
            raise NetworkError(self._connection_error_message()) from error
        except (httpx.ConnectTimeout, httpx.ReadTimeout) as error:
            raise TimeoutError(
                f"LLM API 请求超时: {self._base_url}\n"
                "建议: 缩短 prompt 或换更快的模型"
            ) from error
        except httpx.RequestError as error:
            raise NetworkError(f"LLM API 请求失败: {error}") from error

        self._handle_error_status(response)
        return self._parse_response(response)

    def _build_request(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
    ) -> dict[str, Any]:
        """构建同步和异步请求共用的参数。"""
        return {
            "url": f"{self._base_url}{self.CHAT_ENDPOINT}",
            "headers": {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            "json": {
                "model": self._model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        }

    def _validate_messages(self, messages: list[dict[str, str]]) -> None:
        """校验消息列表的基本结构。"""
        if not isinstance(messages, list):
            raise ValueError(f"messages 必须是 list，不能是 {type(messages).__name__}")
        if not messages:
            raise ValueError("messages 不能为空——至少需要一条 user 消息")

        for index, message in enumerate(messages):
            if not isinstance(message, dict):
                raise ValueError(
                    f"messages[{index}] 必须是 dict，不能是 "
                    f"{type(message).__name__}"
                )
            if "role" not in message:
                raise ValueError(f"messages[{index}] 缺少 'role' 字段")
            if "content" not in message:
                raise ValueError(f"messages[{index}] 缺少 'content' 字段")
            if message["role"] not in VALID_ROLES:
                roles = ", ".join(sorted(VALID_ROLES))
                raise ValueError(
                    f"messages[{index}] 的 role={message['role']!r} 不合法。"
                    f"合法值: {roles}"
                )
            if not isinstance(message["content"], str):
                raise ValueError(f"messages[{index}]['content'] 必须是 str")

    def _handle_error_status(self, response: httpx.Response) -> None:
        """将 HTTP 错误状态转换为项目异常。"""
        if response.is_success:
            return

        status = response.status_code
        detail = self._extract_error_detail(response)
        if status == 401:
            raise AuthenticationError(
                "认证失败（401）：API Key 无效或已过期。\n"
                f"当前 Base URL: {self._base_url}\n"
                f"当前 API Key 前缀: {self._api_key[:8]}****\n"
                f"服务端信息: {detail}"
            )
        if status == 403:
            raise AuthenticationError(
                f"访问被拒绝（403）：API Key 无权访问该资源。\n服务端信息: {detail}"
            )
        if status == 429:
            raise RateLimitError(
                "速率限制（429）：请求太频繁或 Token 额度用完。\n"
                f"建议: 等 3-5 秒后重试；服务端信息: {detail}"
            )
        if status == 404:
            raise ModelError(
                f"端点或模型不存在（404）。\n当前 Base URL: {self._base_url}\n"
                f"当前 Model: {self._model}\n服务端信息: {detail}"
            )
        if 400 <= status < 500:
            raise HTTPStatusError(
                f"请求参数错误（{status}）：{detail}",
                status_code=status,
                response_body=response.text,
            )
        if status >= 500:
            raise HTTPStatusError(
                f"LLM 服务端错误（{status}）：{detail}",
                status_code=status,
                response_body=response.text,
            )
        raise HTTPStatusError(
            f"未知 HTTP 错误（{status}）：{detail}",
            status_code=status,
            response_body=response.text,
        )

    def _parse_response(self, response: httpx.Response) -> str:
        """解析成功响应中的模型文本，并处理完成原因。"""
        try:
            body = response.json()
        except (ValueError, TypeError) as error:
            raise JSONParseError(
                "LLM API 返回的不是有效 JSON。\n"
                f"原始响应前 200 字符: {response.text[:200]}"
            ) from error

        if not isinstance(body, dict):
            raise LLMError(f"LLM 响应格式不正确，响应体: {body}")
        choices = body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMError(f"LLM 响应中缺少有效的 'choices' 字段。响应体: {body}")
        first_choice = choices[0]
        if not isinstance(first_choice, dict):
            raise LLMError(f"LLM 响应中的 choices[0] 格式不正确。响应体: {body}")
        message = first_choice.get("message")
        if not isinstance(message, dict):
            raise LLMError(
                "LLM 响应中缺少有效的 'choices[0].message' 字段。"
                f"响应体: {body}"
            )

        content = message.get("content", "")
        if not isinstance(content, str):
            raise LLMError("LLM 响应中的 message.content 必须是字符串")

        finish_reason = first_choice.get("finish_reason")
        if finish_reason == "length":
            content += (
                "\n\n⚠️ [警告] 输出被截断（finish_reason=length）。"
                "当前 max_tokens 不足以容纳完整回答，建议增大后重试。"
            )
        elif finish_reason == "content_filter":
            raise ContentFilterError(
                "输出被内容安全策略拦截（finish_reason=content_filter）。"
                "建议: 检查提示词中是否有敏感内容"
            )
        return content

    def _extract_error_detail(self, response: httpx.Response) -> str:
        """提取错误响应中的服务端描述。"""
        try:
            body = response.json()
        except (ValueError, TypeError):
            return response.text[:300]

        if isinstance(body, dict) and "error" in body:
            error = body["error"]
            if isinstance(error, dict):
                message = error.get("message", "")
                error_type = error.get("type", "")
                return f"{error_type}: {message}" if error_type else str(message)
            return str(error)
        return response.text[:300]

    def _connection_error_message(self) -> str:
        return (
            f"无法连接到 LLM API: {self._base_url}\n"
            "检查: 1) 网络是否正常 2) LLM_BASE_URL 是否正确 3) 是否需要代理"
        )
