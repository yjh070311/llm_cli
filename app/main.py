"""
week1_llm_cli 程序入口 — Day 3 版本：接入 LLM 调用。

进化记录：
    Day 1: 配置读取 + 历史记录验证
    Day 2: HTTP API Client（app/api_client.py）
    Day 3: LLM Client 接入，实现「输入提示词 → 调 LLM → 输出回答」
    Day 4:异步+计时
    Day 5：完整交互式CLI

支持命令：
    /exit    退出程序
    /history 查看对话历史
    /clear   清空对话历史
    /help    显示帮助
    /retry   重试上一次失败的请求
架构原则：
    main.py只负责组织io流程
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.text import Text

from config import get_config, ConfigError,AppConfig
from llm_client import (
    LLMClient,
    AuthenticationError,
    RateLimitError,
    ModelError,
    LLMError,
)
from exceptions import NetworkError, TimeoutError
from history import(
    save_message_with_limit,
    load_messages,
    clear_history,
    HistoryError,
)

#全局console，所有输出走这个实例
console=Console()

HISTORY_FILE=PROJECT_ROOT/"data"/"history.json"

#system prompt
SYSTEM_PROMPT=(
    "你是一个专业的 AI 助手，用中文回答。"
    "回答使用 Markdown 格式：重要结论加粗，代码用代码块，分点用列表。"
    "如果用户的问题涉及代码，给出可运行的示例。"    
)

#历史最大条数
MAX_HISTORY_ENTRIES=100

#命令处理

def handle_command(command:str,cfg:AppConfig,client:LLMClient)->bool:
    """
    处理以/开头的内置命令

    returns：
        true表示继续循环，false表示退出程序
    """
    cmd=command.lower().strip()

    if cmd in ("/exit","/quit","/q"):
        console.print("\n[bold yellow] 再见！[/bold yellow]\n")
        return False
    if cmd in ("/help","/?"):
        show_help()
        return True
    if cmd in ("/history","/h"):
        show_history()
        return True
    if cmd in ("/clear","/c"):
        clear_chat()
        return True

    #未知命令
    console.print(f"[red]未知命令：{command}[/red]")
    console.print("[dim]输入/help查看可用命令[/dim]")
    return True

def show_help()->None:
    """显示帮助信息"""
    help_table=Table(title="可用命令",show_header=True,header_style="bold cyan")
    help_table = Table(title="可用命令", show_header=True, header_style="bold cyan")
    help_table.add_column("命令", style="cyan")
    help_table.add_column("说明", style="white")
    help_table.add_row("/exit", "退出程序")
    help_table.add_row("/history", "查看最近对话历史")
    help_table.add_row("/clear", "清空对话历史")
    help_table.add_row("/help", "显示本帮助")
    help_table.add_row("/retry", "重试上一次失败的请求")
    console.print(help_table)

def show_history()-> None:
    """显示最近10条对话"""
    try:
        messages=load_messages(HISTORY_FILE)
    except HistoryError as e:
        console.print(f"[red]读取历史失败：{e}[/red]")
        return

    if not messages:
        console.print("[dim]暂无对话历史[/dim]")
        return
    recent=messages[-10:]
    console.print("\n[bold]最近对话，共{}条：[/bold]".format(len(messages)))
    for msg in recent:
        role=msg.get("role","?")
        content=msg.get("content","")
        #只显示前80个，避免刷屏
        preview=content[:80]+("..." if len(content)>80 else "")

        if role=="user":
            console.print(f"[cyan]你：[/cyan]{preview}")
        elif role=="assistant":
            console.print(f"[green]AI:[/green]{preview}")
        else:
            console.print(f"[dim]{role}:{preview}[/dim]")
    console.print()

def clear_chat()->None:
    """清空对话历史"""
    try:
        clear_history(HISTORY_FILE)
        console.print("[bold green]对话历史已被清空[/bold green\n]")
    except HistoryError as e:
        console.print(f"[red]清空失败:{e}[/red]")

#主流程
def print_welcome(cfg:AppConfig)->None:
    """打印欢迎面板，展示配置和可用命令"""
    welcome_text=Text()
    welcome_text.append("🤖 LLM CLI 调用工具\n", style="bold white")
    welcome_text.append(f"  模型: {cfg.model}\n", style="cyan")
    welcome_text.append(f"  API: {cfg.base_url}\n", style="cyan")
    welcome_text.append("\n  输入 /help 查看命令，输入问题直接对话\n", style="dim")

    panel=Panel(
        welcome_text,
        title="[bold]Welcome[/bold]",
        border_style="green" ,
    )
    console.print(panel)

def build_messages_from_history()->list[dict[str,str]]:
    """
    从历史文件构建完整的messages

    return:
    [system...历史消息]结构的列表
    为空返回[system]
    """
    messages:list[dict[str,str]]=[{"role":"system","content":SYSTEM_PROMPT}]

    try:
        history=load_messages(HISTORY_FILE)
    except HistoryError as e:
        console.print(f"[yellow]警告：读取历史失败{e},开始新对话[/yellow]")
        return messages

    # 历史文件里存的是 {"role", "content", "timestamp"}，
    # 转成 LLM API 需要的 {"role", "content"} 格式

    for msg in history:
        role =msg.get("role")
        content=msg.get("content","")
        #只保留合法角色，过滤意外数据
        if role in ("user","assistant","system"):
            messages.append({"role":role,"content":content})
    return messages

def chat_loop(cfg:AppConfig,client:LLMClient)->None:
    """主交互循环--用户输入，调LLM，存历史，输出"""
    print_welcome(cfg)
    last_failed_messages: list[dict[str, str]] | None = None

    while True:
        try:
            #输入提示
            user_input=console.input("[bold cyan]你：[/bold cyan]").strip()
        except (EOFError,KeyboardInterrupt):
            #ctrl+c,ctrl+d--退出
            console.print("\n[bold yellow]再见！[/bold yellow]\n")
            break

        #空输入跳过
        if not user_input:
            continue

        if user_input.lower() in ("/retry", "/r"):
            if last_failed_messages is None:
                console.print("[dim]没有可重试的请求[/dim]")
                continue

            try:
                answer = client.chat_with_history(
                    last_failed_messages,
                    temperature=0.2,
                )
            except AuthenticationError as e:
                console.print(f"\n[bold red]认证失败[/bold red]\n{e}\n")
                break
            except ModelError as e:
                console.print(f"\n[bold red]❌ 模型配置错误[/bold red]\n{e}\n")
                break
            except RateLimitError as e:
                console.print(f"\n[bold yellow]请求太快，请稍后再试[/bold yellow]\n{e}\n")
                continue
            except NetworkError as e:
                console.print(f"\n[bold red]❌ 网络错误[/bold red]\n{e}\n")
                continue
            except TimeoutError as e:
                console.print(f"\n[bold yellow]⚠️ 响应超时[/bold yellow]\n{e}\n")
                continue
            except LLMError as e:
                console.print(f"\n[bold red]❌ LLM 错误[/bold red]\n{e}\n")
                continue

            try:
                save_message_with_limit(
                    HISTORY_FILE,
                    "assistant",
                    answer,
                    MAX_HISTORY_ENTRIES,
                )
            except HistoryError as e:
                console.print(f"[yellow]警告：历史保存失败{e}[/yellow]")

            last_failed_messages = None
            console.print("\n[bold green] AI:[/bold green]")
            console.print(Markdown(answer))
            console.print()
            continue

        #内置命令处理
        if user_input.startswith("/"):
            should_continue=handle_command(user_input,cfg,client)
            if not should_continue:
                break
            continue

        #正常对话
        #1.保存用户消息到历史
        try:
            save_message_with_limit(HISTORY_FILE,"user",user_input,MAX_HISTORY_ENTRIES)
        except HistoryError as e:
            console.print(f"[yellow]警告：历史保存失败{e}，本次对话仍继续[/yellow]")

        #2.构建完整messages并调用LLM
        messages=build_messages_from_history()    

        try:
            answer=client.chat_with_history(messages)
        except AuthenticationError as e:
            console.print(f"\n[bold red]认证失败[/bold red]\n{e}\n")
            break
        except RateLimitError as e:
            last_failed_messages = messages
            console.print(f"\n[bold yellow]请求太快，稍等再试[/bold yellow]\n{e}\n")
            continue
        except ModelError as e:
            console.print(f"\n[bold red]❌ 模型配置错误[/bold red]\n{e}\n")
            break
        except NetworkError as e:
            last_failed_messages = messages
            console.print(f"\n[bold red]❌ 网络错误[/bold red]\n{e}\n")
            continue
        except TimeoutError as e:
            last_failed_messages = messages
            console.print(f"\n[bold yellow]⚠️ 响应超时[/bold yellow]\n{e}\n")
            continue
        except LLMError as e:
            console.print(f"\n[bold red]❌ LLM 错误[/bold red]\n{e}\n")
            continue     

        #3.保存AI回答到历史
        try:
            save_message_with_limit(HISTORY_FILE,"assistant",answer,MAX_HISTORY_ENTRIES)
        except HistoryError as e:
            console.print(f"[yellow]警告：历史保存失败{e}[/yellow]")

        #4.Rich渲染Markdown输出  
        console.print("\n[bold green] AI:[/bold green]")
        console.print(Markdown(answer)) 
        console.print()#空行分隔             

def main() -> None:
    """程序入口：加载配置->初始化客户端->进入交互循环"""
    #1.加载配置
    try:
        cfg=get_config()
    except ConfigError as e:
        console.print(
            Panel(
                f"配置加载失败:\n{e}",
                title="[bold red]配置错误[/bold red]",
                border_style="red"
            )
        )
        console.print("[dim]提示：参考.env.example创建.env文件[/dim]")
        return

    #2.初始化LLM客户端
    client=LLMClient(cfg)

    #3.进入交互循环
    try:
        chat_loop(cfg,client)
    finally:
        #无论正常还是异常，都要关闭链接
        client.close()


if __name__ == "__main__":
    main()