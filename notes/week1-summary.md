# Week 1 项目复盘：week1_llm_cli

## 项目产出

完成一个 Python 命令行 LLM 客户端，支持配置读取、同步/异步请求、多轮对话、JSON 历史、Rich 输出、错误分类、重试和 pytest 自动化测试。

## 架构

- `config.py`：从 `.env` 读取配置，以 `AppConfig` 明确配置字段，并隐藏 API Key。
- `api_client.py`：封装通用 HTTP 请求。
- `llm_client.py`：构建 OpenAI-compatible 请求，提供同步与异步调用，并解析响应。
- `exceptions.py`：集中定义网络、HTTP、认证、限流和模型异常，并提供重试判断。
- `history.py`：负责 JSON 历史读写、清空和条数限制。
- `main.py`：组织 CLI 输入、命令、调用、错误反馈和终端渲染。
- `tests/`：通过 pytest、临时目录和 mock 验证逻辑，不依赖网络或 API 余额。

## 关键设计与原因

### 为什么用 httpx

项目既有同步 CLI，也要验证 asyncio 并发。httpx 同时支持 `Client` 和 `AsyncClient`，可以在同一套 HTTP 生态中实现两种调用方式。

### 为什么 mock LLM API

单元测试应验证项目自己的请求构建、异常分类和响应解析，而不是验证第三方服务是否在线。mock 响应可以稳定模拟成功、401、429、损坏 JSON 和截断输出，不联网、不付费、可重复。

### 为什么使用临时目录

历史和配置测试使用 pytest 的 `tmp_path`，避免覆盖真实 `.env` 和 `data/history.json`。测试间互不共享状态，因此可独立、重复运行。

### 异步带来的收益和限制

异步主要重叠网络等 IO 等待。多个互不依赖的请求可以用 `asyncio.gather()` 并发执行；CPU 密集计算不会因为改成 `async` 自动变快。

## 遇到的问题与修复

1. **`httpx.Timeout` 参数不完整**：指定 `connect` 和默认 timeout，确保当前 httpx 版本接受配置。
2. **响应字段路径错误**：按 OpenAI-compatible 响应读取 `choices[0].message.content`。
3. **Authorization 格式错误**：请求头必须是 `Bearer <API_KEY>`。
4. **历史加载提前返回**：把 `return messages` 移出遍历循环，确保完整上下文发送给模型。
5. **测试依赖真实服务的问题**：使用 `httpx.Response` 和 mock 替换网络边界，避免真实 API 调用。
6. **PowerShell 默认编码问题**：运行 Rich CLI 时设置 `PYTHONIOENCODING=utf-8`。
7. **外部 API 余额不足**：真实异步验证曾收到 HTTP 402；单元测试仍可通过 mock 验证客户端逻辑，避免依赖账户余额。

## Day 7 测试结果

在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m pytest .\tests -v
```

结果：26 项测试通过，覆盖配置、历史、LLM 同步/异步调用和重试判断。

## 下一步

- 进入 FastAPI 与服务端应用结构
- 为真实集成测试增加显式开关，避免普通测试误调用收费 API
- 评估数据库持久化和流式响应
- 补充 CI，让每次变更自动运行测试
