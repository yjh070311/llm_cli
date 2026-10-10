# Day 6 自我验收题

## 1. 重构和重写的区别

重构是在不改变外部行为的前提下，改善内部结构，例如抽取重复逻辑、拆分职责和统一异常来源。重写通常是推倒原实现后重新设计，可能改变接口、行为和边界情况。

本项目中，把同步和异步请求共用的 `_build_request()`、`_handle_error_status()` 和 `_parse_response()` 抽出来，属于重构，因为 CLI 的命令、LLM 调用接口和返回结果保持不变。新增统一的 `exceptions.py` 也是结构重构。若直接替换整个客户端并改变调用方接口，则更接近重写。

## 2. `should_retry(error) -> bool`

实现位于 [app/exceptions.py](./app/exceptions.py)：

- `NetworkError`：返回 `True`，网络抖动可能是暂时性的。
- `RateLimitError`：返回 `True`，等待后可以再次请求。
- `HTTPStatusError` 且状态码为 5xx：返回 `True`，服务端故障可能恢复。
- `AuthenticationError`：返回 `False`，API Key 错误不会因重试而修复。
- `ModelError`：返回 `False`，模型或端点配置错误需要修改配置。
- 其他异常：返回 `False`，未知错误不应盲目重试。

## 3. `.gitignore` 隐蔽 Bug

常见错误是先写了一个会匹配所有 `.env*` 文件的规则，例如：

```gitignore
.env*
```

这样 `.env.example` 也会被忽略。修复方式是在后面增加否定规则：

```gitignore
.env*
!.env.example
```

本项目当前使用更窄的规则：

```gitignore
.env
```

因此 `.env` 会被忽略，而 `.env.example` 不会被忽略。与此同时，Python 缓存目录必须写成 `__pycache__/`，不能写成 `_pycache__/`。

## Day 6 验证记录

- Python 语法检查：通过
- CLI `/help` 和 `/exit`：通过
- 真实异步 API 调用：请求已发出，但服务端返回 `HTTP 402 Insufficient Balance`
- 本地模拟异步并发：应验证请求编排和结果顺序，不依赖 API 余额
