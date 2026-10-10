"""统一的项目异常定义。

集中定义所有 API 层和 LLM 层需要的异常，避免同一类错误在多个模块中重复声明。
"""


class APIError(Exception):
    """所有 API 相关异常的基类。"""


class NetworkError(APIError):
    """网络错误：连接失败、DNS 解析失败、超出网络访问范围等。"""


class TimeoutError(APIError):
    """超时错误：连接超时或读取响应超时。"""


class HTTPStatusError(APIError):
    """HTTP 状态码错误。"""

    def __init__(self, message: str, status_code: int, response_body: str = ""):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        parts = [f"HTTP {self.status_code}: {super().__str__()}"]
        if self.response_body:
            parts.append(f"响应内容: {self.response_body[:200]}")
        return "\n".join(parts)


class JSONParseError(APIError):
    """响应不是有效 JSON。"""


class LLMError(APIError):
    """LLM API 特有的错误基类。"""


class AuthenticationError(LLMError):
    """认证失败：API Key 错误、过期或无权限。"""


class RateLimitError(LLMError):
    """请求速率限制。"""


class ModelError(LLMError):
    """模型或端点错误。"""


class ContentFilterError(LLMError):
    """输出被内容安全策略拦截。"""


def should_retry(error: BaseException) -> bool:
    """判断一个异常是否适合自动重试。

    网络抖动、限流和服务端 5xx 通常是暂时性的；
    认证、模型配置和未知错误重试无法解决根因，因此保守地不重试。
    """
    if isinstance(error, (NetworkError, RateLimitError)):
        return True
    if isinstance(error, HTTPStatusError):
        return error.status_code >= 500
    if isinstance(error, (AuthenticationError, ModelError)):
        return False
    return False


__all__ = [
    "APIError",
    "NetworkError",
    "TimeoutError",
    "HTTPStatusError",
    "JSONParseError",
    "LLMError",
    "AuthenticationError",
    "RateLimitError",
    "ModelError",
    "ContentFilterError",
    "should_retry",
]
