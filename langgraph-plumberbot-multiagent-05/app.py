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
from plumberbot.knowledge import rebuild_embeddings_cache, EMBEDDINGS_CACHE_PATH  # noqa: E402

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
        if getattr(msg, "type", "") != "ai":
            continue
        content = getattr(msg, "content", "")
        # Claude API sometimes returns content as a list of typed blocks
        if isinstance(content, list):
            text = " ".join(
                block["text"] for block in content
                if isinstance(block, dict) and block.get("type") == "text" and block.get("text")
            ).strip()
            if text:
                return text
        elif isinstance(content, str) and content:
            # Skip empty-content tool-call-only AI messages (Anthropic prefill artefacts)
            return content
    return ""


# ── Gradio event handlers ─────────────────────────────────────────────────────

def send_message(user_message: str, history: list, thread_state: dict):
    user_message = user_message.strip()
    if not user_message:
        return "", history, thread_state

    waiting = thread_state.get("waiting_for_interrupt", False)
    thread_id = thread_state.get("thread_id")

    # Create thread_id once per session — reuse it for all follow-up messages so
    # customer_id and conversation state persist across turns via the checkpoint.
    if not thread_id:
        thread_id = str(uuid.uuid4())
        thread_state["thread_id"] = thread_id

    config = {"configurable": {"thread_id": thread_id}}
    history = history + [{"role": "user", "content": user_message}]

    try:
        if waiting:
            result = graph.invoke(Command(resume=user_message), config=config)
        else:
            result = graph.invoke(
                {"messages": [HumanMessage(content=user_message)]},
                config=config,
            )

        if result.get("__interrupt__"):
            thread_state["waiting_for_interrupt"] = True
            bot_message = _last_ai_message(result) or "Please provide your phone number to verify your account."
        else:
            thread_state["waiting_for_interrupt"] = False
            bot_message = _last_ai_message(result) or "(No response)"

    except Exception as exc:
        thread_state["waiting_for_interrupt"] = False
        bot_message = f"⚠️ Error: {exc}"

    history = history + [{"role": "assistant", "content": bot_message}]
    return "", history, thread_state


def new_conversation(_history: list, _thread_state: dict):
    """Reset to a clean state — new thread_id means fresh verification."""
    return [], {"thread_id": None, "waiting_for_interrupt": False}


# ── Gradio UI ─────────────────────────────────────────────────────────────────

DESCRIPTION = """\
**PlumberBot Multi-Agent** — AI-powered plumbing service assistant.

Three specialist subagents, routed by a supervisor:
- 🗓️ **Scheduling** — book appointments, check services & pricing
- 🚨 **Dispatch** — create tickets, handle emergencies, on-call plumber
- 📚 **Knowledge** — DIY how-to tips from the plumbing knowledge base

**Getting started:** Provide your phone number in your first message to verify your account.
Once verified, your identity is remembered for the rest of the conversation — no need to repeat it.

**Test accounts** — use any of these phone numbers:
| Name | Phone |
|---|---|
| Jane Doe | (555) 111-2222 |
| Bob Smith | (555) 333-4444 |
| Maria Garcia | (555) 555-6666 |
"""

SEQUENCE_NOTE = """\
**💡 Try these in sequence** — click an example, press Send, then click the next one.
Your identity is verified once and remembered for the whole conversation.
"""

with gr.Blocks(title="PlumberBot Multi-Agent 🔧") as demo:
    gr.Markdown("# 🔧 PlumberBot Multi-Agent")
    gr.Markdown(DESCRIPTION)

    thread_state = gr.State({"thread_id": None, "waiting_for_interrupt": False})

    chatbot = gr.Chatbot(
        height=480,
        placeholder="Provide your phone number and tell us how we can help...",
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

    with gr.Row():
        new_btn = gr.Button("🔄 New Conversation", variant="secondary", size="sm")
        if os.getenv("OPENAI_API_KEY"):
            _cache_exists = os.path.exists(EMBEDDINGS_CACHE_PATH)
            _cache_label = (
                f"🧠 Embeddings cached ({os.path.basename(EMBEDDINGS_CACHE_PATH)})"
                if _cache_exists else "🧠 Build Embeddings Cache"
            )
            rebuild_btn = gr.Button(_cache_label, variant="secondary", size="sm")
            rebuild_status = gr.Textbox(
                value="",
                label="Knowledge base status",
                interactive=False,
                show_label=False,
                scale=3,
            )
            rebuild_btn.click(rebuild_embeddings_cache, outputs=[rebuild_status])

    gr.Markdown(SEQUENCE_NOTE)

    with gr.Tabs():
        with gr.Tab("Returning customer"):
            gr.Markdown("_Use these in sequence — identity is verified once and remembered._")
            gr.Examples(
                examples=[
                    "Hi, my phone number is (555) 111-2222",
                    "What plumbing services do you offer and what are the prices?",
                    "I'd like to book a drain cleaning. Who's available?",
                    "How do I fix a running toilet myself?",
                    "I have a persistent slow drain. Can you raise a service ticket for me?",
                ],
                inputs=msg_box,
                label=None,
            )
        with gr.Tab("New customer registration"):
            gr.Markdown("_Start a New Conversation first, then use these in sequence._")
            gr.Examples(
                examples=[
                    "Hi, my phone is (555) 888-0000 and my name is Alex Rivera",
                    "yes",
                    "What drain cleaning services do you offer?",
                ],
                inputs=msg_box,
                label=None,
            )

    gr.Markdown(
        "_Conversation state persists within the session via SQLite checkpoints. "
        "Long-term preferences are saved to the business database across sessions. "
        "Click **New Conversation** to start fresh._",
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
