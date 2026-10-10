"""
HTTP API 客户端模块：封装 httpx 的同步和异步请求，统一处理超时、异常和错误响应。

设计原则：
    - 所有请求走同一个 Client 实例，复用连接池（httpx 内部管理）
    - 超时设定：连接 10 秒，读取 30 秒（LLM API 推理可能比较慢）
    - 状态码错误和网络异常分开处理，给调用方明确的错误信息
"""

from dataclasses import dataclass
from typing import Any

import httpx

from exceptions import (
    APIError,
    NetworkError,
    TimeoutError,
    HTTPStatusError,
    JSONParseError,
)


# ============================================================
# API 响应封装 — 让调用方不用关心 httpx 的底层细节
# ============================================================

@dataclass
class APIResponse:
    """统一的 API 响应数据结构。

    不直接暴露 httpx.Response，原因：
        1. 调用方代码不依赖 httpx，方便以后换库
        2. 提前解析 JSON，JSON 解析失败在这里统一处理
    """
    status_code: int
    headers: dict[str, str]
    json_data: Any  # 解析后的 JSON（dict / list / None）
    raw_text: str   # 保留原始文本用于 debug

    def json(self):
        """
        隐藏内部结构
        快捷方法，和 httpx 的 response.json() 保持类似 API。
        api可以理解成一个封装好的黑盒程序
        """
        return self.json_data


# ============================================================
# HTTP 客户端
# ============================================================

class APIClient:
    """同步 HTTP 客户端，封装 httpx.Client。

    用法:
        client = APIClient(timeout=30.0)
        resp = client.get("https://httpbin.org/json")
        print(resp.json_data)

        resp = client.post("https://httpbin.org/post", json={"key": "value"})
        print(resp.status_code)

        - 使用 with 语句确保连接正确关闭
        - 不要每次请求都创建新的 APIClient，复用同一个实例
    """

    def __init__(self, connect_timeout: float = 10.0, read_timeout: float = 30.0):
        """初始化客户端。

        Args:
            connect_timeout: 建立 TCP 连接的最大等待秒数
            read_timeout: 等待服务器响应的最大秒数（不包括连接时间）

        为什么不直接使用httpx.Client：1.换库只需要变化内部代码
        2.固定配置
        3.exit强制清理
        4.返回干净的APIResponse
        那client本身已经有1和2的优势了，为什么还要套一层：
        强制做到了，“凡是用我项目的 HTTP 请求，必须用我的 Key，必须返回我的格式”。

        """
        # httpx.Timeout 区分 connect 和 read，比传一个数字更精确
        self._timeout = httpx.Timeout(connect=connect_timeout, read=read_timeout)
        # Client 内部维护连接池，复用 TCP 连接
        self._client = httpx.Client(timeout=self._timeout)

    def close(self) -> None:
        """关闭客户端，释放连接资源。"""
        self._client.close()

    def __enter__(self) -> "APIClient":
        """支持 with 语句：with APIClient() as client:,magic method"""
        return self

    def __exit__(self, *args: Any) -> None:
        """退出 with 块时自动关闭连接。需要和__enter__成对出现"""
        self.close()

    def _request(self, method: str, url: str, **kwargs: Any) -> APIResponse:
        """执行 HTTP 请求的内部方法——所有公开方法最终走这里。

        集中处理异常转换：把 httpx 的异常体系转换为我们自己的 APIError 体系。
        这样调用方只需要 catch 几种 APIError 子类，不需要了解 httpx 的异常类型。
        """
        try:
            #底层通用请求方法，所有方法都会调用它
            response = self._client.request(method, url, **kwargs) 
        except httpx.ConnectError as e:
            # 连接失败：DNS 解析不了、IP 不可达、端口没开
            raise NetworkError(f"无法连接到服务器: {url}\n原因: {e}") from e
        except httpx.ReadTimeout as e:
            raise TimeoutError(
                f"读取响应超时（{self._timeout.read} 秒）: {url}\n"
                f"建议: 如果是 LLM API，可以增大 read_timeout 或换更快模型"
            ) from e
        except httpx.ConnectTimeout as e:
            raise TimeoutError(
                f"连接超时（{self._timeout.connect} 秒）: {url}\n"
                f"建议: 检查网络或服务是否在线"
            ) from e
        except httpx.RequestError as e:
            # 其他所有 httpx 请求异常的兜底
            raise NetworkError(f"网络请求失败: {url}\n原因: {e}") from e

        # 解析 JSON——失败也单独报
        try:
            json_data = response.json()
        except Exception:
            # 响应不是 JSON（可能是 HTML 错误页或纯文本）
            json_data = None

        #response.is_error快速判断响应是否错误
        if response.is_error:
            # 状态码 4xx 或 5xx——让调用方决定怎么处理
            raise HTTPStatusError(
                f"请求失败: {method} {url}",
                status_code=response.status_code,
                response_body=response.text,
            )

        return APIResponse(
            status_code=response.status_code,
            headers=dict(response.headers),
            json_data=json_data,
            raw_text=response.text,
        )

    def get(self, url: str, **kwargs: Any) -> APIResponse:
        """发送 GET 请求。

        Args:
            url: 请求地址（含 Query String 如果需要）
            **kwargs: 透传给 httpx，例如 headers={"Authorization": "Bearer xxx"}

        Returns:
            APIResponse 对象，包含状态码、JSON 数据和原始文本

        Raises:
            NetworkError: 网络不通
            TimeoutError: 超时
            HTTPStatusError: 状态码非 2xx
        """
        return self._request("GET", url, **kwargs)

    def post(self, url: str, *, json: dict[str, Any] | None = None, data: Any = None, **kwargs: Any) -> APIResponse:
        """发送 POST 请求。

        Args:
            url: 请求地址
            json: JSON 请求体（会自动设置 Content-Type: application/json）
            data: 原始请求体（表单数据等，不会自动设 Content-Type）
            **kwargs: 透传给 httpx

        Returns:
            APIResponse 对象
        """
        return self._request("POST", url, json=json, data=data, **kwargs)

    def put(self, url: str, *, json: dict[str, Any] | None = None, **kwargs: Any) -> APIResponse:
        """发送 PUT 请求（用于更新资源）。"""
        return self._request("PUT", url, json=json, **kwargs)

    def delete(self, url: str, **kwargs: Any) -> APIResponse:
        """发送 DELETE 请求（用于删除资源）。"""
        return self._request("DELETE", url, **kwargs)

