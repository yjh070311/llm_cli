import json

import pytest

from app.history import (
    HistoryError,
    clear_history,
    load_messages,
    save_message,
    save_message_with_limit,
)


def test_save_and_load_messages(tmp_path) -> None:
    filepath = tmp_path / "history.json"

    save_message(filepath, "user", "问题一")
    save_message(filepath, "assistant", "回答一")

    messages = load_messages(filepath)
    assert [message["content"] for message in messages] == ["问题一", "回答一"]
    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert all("timestamp" in message for message in messages)


def test_load_empty_file_returns_empty_list(tmp_path) -> None:
    filepath = tmp_path / "history.json"

    assert load_messages(filepath) == []
    filepath.write_text("", encoding="utf-8")
    assert load_messages(filepath) == []


def test_save_message_with_limit_keeps_latest_entries(tmp_path) -> None:
    filepath = tmp_path / "history.json"

    for index in range(4):
        save_message_with_limit(filepath, "user", f"消息{index}", max_entries=2)

    messages = load_messages(filepath)
    assert [message["content"] for message in messages] == ["消息2", "消息3"]


def test_save_message_with_limit_rejects_non_positive_limit(tmp_path) -> None:
    with pytest.raises(ValueError, match="大于 0"):
        save_message_with_limit(tmp_path / "history.json", "user", "test", 0)


def test_clear_history(tmp_path) -> None:
    filepath = tmp_path / "history.json"
    save_message(filepath, "user", "待清空")

    clear_history(filepath)

    assert filepath.exists()
    assert filepath.read_text(encoding="utf-8") == "[]"
    assert load_messages(filepath) == []


def test_corrupted_json_raises_history_error(tmp_path) -> None:
    filepath = tmp_path / "broken.json"
    filepath.write_text('{"role": "user",}', encoding="utf-8")

    with pytest.raises(HistoryError, match="JSON 解析失败"):
        load_messages(filepath)


def test_save_message_creates_parent_dir(tmp_path) -> None:
    filepath = tmp_path / "a" / "b" / "c" / "history.json"

    save_message(filepath, "user", "目录自动创建")

    assert filepath.is_file()
    assert load_messages(filepath)[0]["content"] == "目录自动创建"


def test_save_and_load_assert_saved_content(tmp_path) -> None:
    filepath = tmp_path / "history.json"

    save_message(filepath, "user", "精确内容")
    messages = load_messages(filepath)

    assert messages == [
        {
            "role": "user",
            "content": "精确内容",
            "timestamp": messages[0]["timestamp"],
        }
    ]
    assert json.loads(filepath.read_text(encoding="utf-8"))[0]["content"] == "精确内容"
