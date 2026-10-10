# week1_llm_cli

一个基于 Python 的 OpenAI-compatible LLM 命令行工具。项目从配置读取、HTTP 请求和 JSON 持久化开始，逐步加入同步/异步 LLM 调用、并发请求、Rich 终端渲染和多轮对话。

## 功能

- 支持 OpenAI-compatible API，例如 DeepSeek、OpenAI、Qwen、GLM 等
- 交互式 CLI 对话
- Rich Markdown 渲染
- 多轮对话和 JSON 历史持久化
- `/help`、`/history`、`/clear`、`/retry`、`/exit` 命令
- 同步和异步 LLM 调用
- `asyncio.gather()` 并发调用
- 分层异常处理：认证、限流、网络、超时、模型和响应解析错误
- 历史消息数量限制，避免上下文无限增长

## 技术栈

| 技术 | 用途 |
| --- | --- |
| Python 3.11+ | 运行环境 |
| httpx | 同步/异步 HTTP 客户端 |
| python-dotenv | 读取 `.env` 配置 |
| Rich | 终端面板和 Markdown 渲染 |
| JSON | 本地对话历史持久化 |

## 快速启动

### 1. 创建并激活虚拟环境

Windows PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2. 安装依赖

```powershell
python -m pip install -r requirements.txt
```

### 3. 创建配置文件

```powershell
Copy-Item .env.example .env
```

然后编辑 `.env`：

```dotenv
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.deepseek.com
LLM_MODEL=deepseek-chat
```

客户端会自动请求：

```text
{LLM_BASE_URL}/v1/chat/completions
```

不要提交 `.env` 或真实 API Key。

### 4. 启动 CLI

```powershell
$env:PYTHONIOENCODING="utf-8"
python .\app\main.py
```

如果当前目录已经是 `app`，也可以运行：

```powershell
python .\main.py
```

## CLI 命令

| 命令 | 说明 |
| --- | --- |
| `/help` | 查看命令帮助 |
| `/history` | 查看最近对话 |
| `/clear` | 清空本地历史 |
| `/retry` | 重试上一次网络、超时或限流失败的请求 |
| `/exit` | 退出程序 |

## 异步调用

在项目根目录执行：

```powershell
$env:PYTHONIOENCODING="utf-8"
python .\app\asynctest.py
```

该脚本会并发发送三个互不依赖的问题，并输出总耗时。`asyncio.gather()` 的结果顺序与输入问题顺序一致。

## 项目结构

```text
week1_llm_cli/
├── app/
│   ├── api_client.py      # HTTP 客户端封装
│   ├── config.py          # .env 配置读取
│   ├── exceptions.py      # 统一异常定义
│   ├── history.py         # JSON 历史持久化
│   ├── llm_client.py      # 同步/异步 LLM 客户端
│   ├── main.py            # CLI 编排入口
│   └── asynctest.py       # 异步并发验证脚本
├── data/                  # 本地历史数据，不提交
├── .env.example           # 配置模板
├── .gitignore
├── requirements.txt
└── README.md
```

## 分层设计

```text
main.py
  ├── config.py       读取配置
  ├── history.py      保存和读取对话历史
  └── llm_client.py   构建请求、发送请求、解析响应
        └── exceptions.py 统一异常类型
```

`main.py` 只负责交互流程编排；配置、持久化、HTTP 请求和 LLM 响应解析分别由独立模块负责。同步和异步客户端共用请求构建、状态码处理和响应解析逻辑。

## Day 6 验证

```powershell
python -m py_compile .\app\exceptions.py .\app\api_client.py .\app\llm_client.py .\app\main.py
```

## 测试

安装依赖后，在项目根目录运行：

```powershell
.\.venv\Scripts\python.exe -m pytest .\tests -v
```

测试使用 `tmp_path` 隔离配置与历史文件，并通过 mock 替换 LLM HTTP 响应，不访问真实 API、不消耗额度。

检查敏感文件是否被忽略：

```powershell
git status --short --ignored
```

`.env`、`.venv/`、`__pycache__/` 和 `data/` 不应作为待提交文件出现；`.env.example` 应该可以被跟踪。

## 已知限制

- 当前历史使用 JSON 文件，适合 Week 1 的单用户本地 CLI；后续可迁移到数据库。
- 当前每次异步调用临时创建 `AsyncClient`；后续可以在更大规模服务中统一管理异步客户端生命周期。
- API Key 只从环境变量读取，不写入代码或历史文件。
