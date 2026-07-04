"""PlumberBot Multi-Agent — Gradio web UI.

Persistence:
  - Conversation checkpoints: SqliteSaver at CHECKPOINT_DB_PATH
    (default /tmp/plumberbot_checkpoints.db — ephemeral on HF free tier)
  - Business DB: BUSINESS_DB_PATH (default db/plumberbot.db, committed to git)
  - Long-term memory: customer_profile table in business DB
"""

import os
import sqlite3
import uuid

import gradio as gr
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

load_dotenv()

from plumberbot.graph import build_graph  # noqa: E402

# ── Checkpoint DB (short-term, per-thread conversation state) ─────────────────

CHECKPOINT_DB = os.getenv("CHECKPOINT_DB_PATH", "/tmp/plumberbot_checkpoints.db")
_checkpoint_dir = os.path.dirname(CHECKPOINT_DB)
if _checkpoint_dir and not os.path.isdir(_checkpoint_dir):
    print(f"WARNING: {_checkpoint_dir} does not exist, falling back to /tmp")
    CHECKPOINT_DB = "/tmp/plumberbot_checkpoints.db"

_conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
_checkpointer = SqliteSaver(_conn)
graph = build_graph(checkpointer=_checkpointer)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _last_ai_message(result: dict) -> str:
    for msg in reversed(result.get("messages", [])):
        if hasattr(msg, "content") and getattr(msg, "type", "") == "ai":
            return msg.content
    return ""


# ── Gradio event handlers ─────────────────────────────────────────────────────

def send_message(user_message: str, history: list, thread_state: dict):
    user_message = user_message.strip()
    if not user_message:
        return "", history, thread_state

    waiting = thread_state.get("waiting_for_interrupt", False)
    thread_id = thread_state.get("thread_id")
    config = {"configurable": {"thread_id": thread_id}}

    history.append({"role": "user", "content": user_message})

    try:
        if waiting and thread_id:
            result = graph.invoke(Command(resume=user_message), config=config)
        else:
            thread_id = str(uuid.uuid4())
            thread_state["thread_id"] = thread_id
            config = {"configurable": {"thread_id": thread_id}}
            result = graph.invoke(
                {"messages": [HumanMessage(content=user_message)]},
                config=config,
            )

        if result.get("__interrupt__"):
            thread_state["waiting_for_interrupt"] = True
            bot_message = _last_ai_message(result) or "Please provide your phone number."
        else:
            thread_state["waiting_for_interrupt"] = False
            bot_message = _last_ai_message(result) or "(No response)"

    except Exception as exc:
        thread_state["waiting_for_interrupt"] = False
        bot_message = f"⚠️ Error: {exc}"

    history.append({"role": "assistant", "content": bot_message})
    return "", history, thread_state


def new_conversation(_history: list, _thread_state: dict):
    return [], {"thread_id": None, "waiting_for_interrupt": False}


# ── Gradio UI ─────────────────────────────────────────────────────────────────

DESCRIPTION = """\
**PlumberBot Multi-Agent** — AI-powered plumbing service assistant.

Three specialist subagents, routed by a supervisor:
- **Scheduling** — book appointments, check services & pricing
- **Dispatch** — create tickets, handle emergencies, on-call plumber
- **Knowledge** — DIY how-to tips from the plumbing knowledge base

*Your account is verified by phone number. Say your phone to get started.*
"""

with gr.Blocks(title="PlumberBot Multi-Agent 🔧") as demo:
    gr.Markdown("# 🔧 PlumberBot Multi-Agent")
    gr.Markdown(DESCRIPTION)

    thread_state = gr.State({"thread_id": None, "waiting_for_interrupt": False})

    chatbot = gr.Chatbot(
        height=480,
        placeholder="Tell us your phone number and how we can help...",
        show_label=False,
    )

    with gr.Row():
        msg_box = gr.Textbox(
            placeholder="Type your message and press Enter...",
            scale=5,
            show_label=False,
            autofocus=True,
        )
        send_btn = gr.Button("Send", scale=1, variant="primary")

    new_btn = gr.Button("🔄 New Conversation", variant="secondary", size="sm")

    gr.Examples(
        examples=[
            "My phone is (555) 111-2222. I need to book a drain cleaning.",
            "My number is (555) 333-4444. Do I have any open tickets?",
            "My phone is (555) 111-2222. How do I fix a running toilet?",
            "My number is (555) 555-6666. What services do you offer and what are the prices?",
            "My phone is (555) 111-2222. I have a burst pipe at home — what should I do?",
        ],
        inputs=msg_box,
        label="Try these examples:",
    )

    gr.Markdown(
        "_Conversation state persists within the container session. "
        "Long-term memory (preferences, history) is saved to the business database._",
        elem_classes=["footer-note"],
    )

    send_btn.click(
        send_message,
        inputs=[msg_box, chatbot, thread_state],
        outputs=[msg_box, chatbot, thread_state],
    )
    msg_box.submit(
        send_message,
        inputs=[msg_box, chatbot, thread_state],
        outputs=[msg_box, chatbot, thread_state],
    )
    new_btn.click(
        new_conversation,
        inputs=[chatbot, thread_state],
        outputs=[chatbot, thread_state],
    )

if __name__ == "__main__":
    demo.launch(server_name="0.0.0.0", server_port=7860, theme=gr.themes.Soft())
