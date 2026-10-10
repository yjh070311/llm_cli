"""
  对话历史持久化模块：把和 LLM 的对话保存为 JSON 文件，支持追加和读取。

  设计决策：
      Week 1 用 JSON 文件而不是数据库——项目规模小，一条对话就两条记录，
      引入数据库反而增加学习负担。Week 2-3 会迁移到数据库。
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HistoryError(Exception):
    """历史记录操作失败——通常是文件权限 JSON 格式问题。"""
    pass


def _ensure_data_dir(filepath: Path) -> None:
    """确保目标文件的父目录存在。

    如果 data/ 目录不存在，自动创建。不需要使用者手动 mkdir。

    Args:
        filepath: 目标 JSON 文件的完整路径。
    """
    parent = filepath.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)   #已存在父目录，不报错


def _build_message(role: str, content: str) -> dict[str, str]: 
    """构建一条符合 OpenAI messages 格式的消息记录。

    Args:
        role: 消息角色，取值为 "system"、"user" 或 "assistant"。
        content: 消息正文。

    Returns:
        包含 role、content 和 timestamp 的字典。
    """
    return {
        "role": role,
        "content": content,
        "timestamp": datetime.now(timezone.utc).isoformat(),    #标准化时间
    }


def save_message(filepath: Path, role: str, content: str) -> None:
    """向对话历史文件追加一条消息。

    如果文件不存在，自动创建新文件并写入第一条记录。
    如果文件已存在，读取现有记录后追加新消息。

    Args:
        filepath: 历史文件路径，例如 Path("data/history.json")。
        role: 消息角色。
        content: 消息内容。

    Raises:
        HistoryError: JSON 文件损坏或写入权限不足时抛出。
    """
    _ensure_data_dir(filepath)

    message = _build_message(role, content)

    # 读取现有历史——文件可能不存在，也可能存在但内容损坏
    history: list[dict[str, Any]] = []
    if filepath.exists():
        try:
            raw = filepath.read_text(encoding="utf-8")
            if raw.strip():  # 文件不为空才解析，strip()移除空白字符
                history = json.loads(raw)
                if not isinstance(history, list):   #检查对象是否属于某个类型
                    raise HistoryError(
                        f"历史文件格式错误：期望 JSON 数组，实际是 {type(history).__name__}。\n"
                        f"请检查文件：{filepath}"
                    )
        except json.JSONDecodeError as e:
            raise HistoryError(
                f"历史文件 JSON 解析失败：{e.msg}（第 {e.lineno} 行，第 {e.colno} 列）。\n"
                f"文件路径：{filepath}\n"
                f"建议：手动检查文件末尾是否多了逗号，或者文件是否被截断。"
            ) from e    #保留异常链，通过e.__cause__可以追溯到原始异常

    history.append(message)

    # ensure_ascii=False 让中文字符正常显示，indent=2 让文件可读
    try:
        filepath.write_text(
            json.dumps(history, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )   #直接写入文件，先将json序列化，不能直接用py格式
    except OSError as e:
        raise HistoryError(
            f"无法写入历史文件：{e.strerror if hasattr(e, 'strerror') else str(e)}\n"
            f"文件路径：{filepath}"
        ) from e

def clear_history(filepath: Path) -> None:
    """清空历史记录，并保留历史文件本身。"""
    _ensure_data_dir(filepath)
    try:
        filepath.write_text("[]", encoding="utf-8")
    except OSError as e:
        raise HistoryError(
            f"无法清空历史文件：{e.strerror if hasattr(e, 'strerror') else str(e)}\n"
            f"文件路径：{filepath}"
        ) from e


def save_message_with_limit(
    filepath: Path,
    role: str,
    content: str,
    max_entries: int = 100,
) -> None:
    """保存消息，并只保留最新的 ``max_entries`` 条记录。"""
    if max_entries <= 0:
        raise ValueError("max_entries 必须大于 0")

    messages = load_messages(filepath)
    messages.append(_build_message(role, content))

    if len(messages) > max_entries:
        messages = messages[-max_entries:]

    _ensure_data_dir(filepath)
    try:
        filepath.write_text(
            json.dumps(messages, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        raise HistoryError(
            f"无法写入历史文件：{e.strerror if hasattr(e, 'strerror') else str(e)}\n"
            f"文件路径：{filepath}"
        ) from e



def load_messages(filepath: Path) -> list[dict[str, Any]]:
    """读取对话历史文件中的所有消息。

    Args:
        filepath: 历史文件路径。

    Returns:
        消息列表。如果文件不存在或为空，返回空列表而不是报错——
        这是有意设计：首次使用时没有历史是正常状态。

    Raises:
        HistoryError: JSON 格式损坏时抛出。
    """
    if not filepath.exists():
        return []

    try:
        raw = filepath.read_text(encoding="utf-8")
    except OSError as e:
        raise HistoryError(
            f"无法读取历史文件：{e.strerror if hasattr(e, 'strerror') else str(e)}\n"
            f"文件路径：{filepath}"
        ) from e

    if not raw.strip():
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HistoryError(
            f"历史文件 JSON 解析失败：{e.msg}（第 {e.lineno} 行，第 {e.colno} 列）。\n"
            f"文件路径：{filepath}"
        ) from e

    if not isinstance(data, list):
        raise HistoryError(
            f"历史文件格式错误：期望 JSON 数组，实际是 {type(data).__name__}。\n"
            f"文件路径：{filepath}"
        )

    return data
