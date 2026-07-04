"""PlumberBot Multi-Agent CLI.

Interactive loop that handles:
- Customer identity verification (phone lookup via interrupt)
- Routing to scheduling, dispatch, or knowledge subagents
- Persistent memory across turns via SqliteSaver checkpoints

Usage:
    python cli.py
"""

import sys
import uuid

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command

load_dotenv()

from plumberbot.graph import build_graph  # noqa: E402

graph = build_graph(checkpointer=MemorySaver())


def _last_ai_message(result: dict) -> str:
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "content") and getattr(msg, "type", "") in ("ai",):
            return msg.content
    return "(no response)"


def run() -> None:
    print("=" * 60)
    print("  PlumberBot Multi-Agent System")
    print("  Commands: 'new' — start fresh | 'quit' — exit")
    print("=" * 60)
    print()

    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    waiting_for_interrupt = False

    while True:
        try:
            user_input = input("You: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            sys.exit(0)

        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Goodbye!")
            break
        if user_input.lower() == "new":
            thread_id = str(uuid.uuid4())
            config = {"configurable": {"thread_id": thread_id}}
            waiting_for_interrupt = False
            print("\n[New conversation started]\n")
            continue

        try:
            if waiting_for_interrupt:
                result = graph.invoke(Command(resume=user_input), config=config)
            else:
                result = graph.invoke(
                    {"messages": [HumanMessage(content=user_input)]},
                    config=config,
                )

            if result.get("__interrupt__"):
                waiting_for_interrupt = True
                print(f"\nPlumberBot: {_last_ai_message(result)}\n")
            else:
                waiting_for_interrupt = False
                print(f"\nPlumberBot: {_last_ai_message(result)}\n")

        except Exception as exc:
            waiting_for_interrupt = False
            print(f"\n[Error] {exc}\n")


if __name__ == "__main__":
    run()
