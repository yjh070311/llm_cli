"""
Day 3 多轮对话演示：验证 LLMClient 的 chat_with_history 方法。

运行方式：
    python test_llm.py

这个脚本模拟一个真实的对话场景：
    1. 设定角色（system prompt）→ AI 扮演 Python 导师
    2. 用户问一个问题 → AI 回答
    3. 用户追问一个细节 → AI 基于上文回答（这是关键——需要 history）
    4. 打印完整对话历史
"""

from app.config import get_config, ConfigError
from app.llm_client import LLMClient, LLMError


def demo_multi_turn() -> None:
    """演示多轮对话：验证 history 是否生效。"""
    print("=" * 60)
    print("  多轮对话演示 — 验证上下文保持能力")
    print("=" * 60)

    # 加载配置
    try:
        cfg = get_config()
    except ConfigError as e:
        print(f"配置错误: {e}")
        return

    # 初始化 messages——第一轮只有 system + user
    messages: list[dict[str, str]] = [
        {
            "role": "system",
            "content": (
                "你是一个 Python 后端导师，语气专业但友好。"
                "用中文回答，代码示例保持英文。"
                "每次回答先给出结论，再给代码示例，最后提醒一个常见错误。"
            ),
        },
        {"role": "user", "content": "Python 的 @dataclass 装饰器有什么用？"},
    ]

    with LLMClient(cfg) as client:
        # ---- 第一轮 ----
        print("\n💬 第一轮对话")
        print(f"   User: {messages[-1]['content']}")
        try:
            answer1 = client.chat_with_history(messages)
            print(f"   Assistant: {answer1[:200]}..." if len(answer1) > 200 else f"   Assistant: {answer1}")

            # 把 AI 的回答追加到 messages——这是多轮对话的关键步骤
            messages.append({"role": "assistant", "content": answer1})
        except LLMError as e:
            print(f"   ❌ 第一轮失败: {e}")
            return

        # ---- 第二轮：追问（依赖第一轮上下文） ----
        messages.append({
            "role": "user",
            "content": "那和 Pydantic 的 BaseModel 比，什么时候用哪个？",
        })

        print(f"\n💬 第二轮对话（追问）")
        print(f"   User: {messages[-1]['content']}")
        try:
            answer2 = client.chat_with_history(messages)
            print(f"   Assistant: {answer2[:200]}..." if len(answer2) > 200 else f"   Assistant: {answer2}")

            messages.append({"role": "assistant", "content": answer2})
        except LLMError as e:
            print(f"   ❌ 第二轮失败: {e}")
            return

    # ---- 打印完整对话历史 ----
    print(f"\n{'=' * 60}")
    print(f"  完整对话历史（共 {len(messages)} 条消息）")
    print(f"{'=' * 60}")
    for i, msg in enumerate(messages):
        role = msg["role"]
        content_preview = msg["content"][:80]
        icon = {"system": "⚙️", "user": "👤", "assistant": "🤖"}.get(role, "❓")
        print(f"  {icon} [{i}] {role}: {content_preview}...")

    print(f"\n  ✅ 多轮对话演示完成")
    print(f"  👆 观察第二轮的答案——它应该提到了 dataclass 和 Pydantic 的对比")
    print(f"     如果它不知道上下文，说明 history 没传进去")


if __name__ == "__main__":
    demo_multi_turn()

