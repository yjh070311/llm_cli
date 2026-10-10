from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

console = Console()

response="""
#AI Assistant
你好，我是你的**AI助手**

## 我能做什么

- python
- asyncio
- fastapi
```
python
async def hello():
    await asyncio.sleep(1)
```
"""
console.print(
    Panel(Markdown(response),title="AI",border_style="red")
)