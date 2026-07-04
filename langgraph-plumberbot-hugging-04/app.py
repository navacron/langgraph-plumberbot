"""PlumberBot — Gradio web UI for the LangGraph plumbing triage bot.

Persistence: SqliteSaver writes to DB_PATH (default /tmp/plumberbot.db).
  - Free HF Spaces: /tmp is ephemeral (resets on cold start)
  - Pro HF Spaces: set DB_PATH=/data/plumberbot.db + enable Persistent Storage
"""

import json
import os
import sqlite3
import uuid

import gradio as gr
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from plumberbot.graph import build_graph

load_dotenv()

# ── SQLite checkpointer (lives for the server process lifetime) ───────────────

DB_PATH = os.getenv("DB_PATH", "/tmp/plumberbot.db")
_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
_checkpointer = SqliteSaver(_conn)
graph = build_graph(checkpointer=_checkpointer)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_initial_state(message: str) -> dict:
    return {
        "customer_message": message,
        "category": "",
        "missing_fields": [],
        "urgency_reason": "",
        "human_decision": "",
        "ticket": {},
        "customer_reply": "",
        "profile": {},
        "final_response": "",
    }


def _format_interrupt(interrupt_val: dict | str) -> str:
    """Turn an interrupt payload into a readable bot message."""
    if isinstance(interrupt_val, dict):
        if "bot_message" in interrupt_val:
            # missing_info interrupt — just show the question
            return interrupt_val["bot_message"]
        else:
            # emergency human_review interrupt
            options = interrupt_val.get("options", ["approve", "reject", "escalate"])
            payload_str = json.dumps(interrupt_val, indent=2)
            return (
                f"🚨 **Emergency Dispatch — Dispatcher Review Required**\n\n"
                f"```json\n{payload_str}\n```\n\n"
                f"**Type your decision:** `{'` / `'.join(options)}`"
            )
    return str(interrupt_val)


def _format_final(result: dict) -> str:
    """Format the final state into a readable bot response."""
    response = result.get("final_response", "")
    category = result.get("category", "")

    if category == "missing_info" and result.get("profile"):
        profile_str = json.dumps(result["profile"], indent=2)
        response += f"\n\n✅ **Profile saved:**\n```json\n{profile_str}\n```"
    elif category == "emergency":
        ticket = result.get("ticket", {})
        decision = result.get("human_decision", "")
        if ticket:
            response += f"\n\n🎫 **Ticket `{ticket.get('ticket_id', 'N/A')}` created** (decision: `{decision}`)"
        else:
            response += f"\n\n_(Decision: `{decision}` — no ticket created)_"

    return response


# ── Gradio event handlers ─────────────────────────────────────────────────────

def send_message(user_message: str, history: list, thread_state: dict):
    """Handle each user message — new conversation or interrupt resume."""
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
            result = graph.invoke(_make_initial_state(user_message), config=config)

        if "__interrupt__" in result:
            interrupt_val = result["__interrupt__"][0].value
            thread_state["waiting_for_interrupt"] = True
            bot_message = _format_interrupt(interrupt_val)
        else:
            thread_state["waiting_for_interrupt"] = False
            bot_message = _format_final(result)

    except Exception as exc:
        thread_state["waiting_for_interrupt"] = False
        bot_message = f"⚠️ Error: {exc}"

    history.append({"role": "assistant", "content": bot_message})
    return "", history, thread_state


def new_conversation(history: list, thread_state: dict):
    """Reset state for a fresh conversation."""
    return [], {"thread_id": None, "waiting_for_interrupt": False}


# ── Gradio UI ─────────────────────────────────────────────────────────────────

DESCRIPTION = """\
**PlumberBot** — AI-powered plumbing service triage bot.

Handles three types of requests:
- 🔧 **General questions** — "Do you fix water heaters?"
- 📋 **Missing information** — incomplete requests trigger a follow-up question
- 🚨 **Emergencies** — burst pipes / flooding pause for dispatcher review

*Powered by LangGraph + Claude. Conversation state persists via SQLite.*
"""

with gr.Blocks(title="PlumberBot 🔧", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🔧 PlumberBot")
    gr.Markdown(DESCRIPTION)

    thread_state = gr.State({"thread_id": None, "waiting_for_interrupt": False})

    chatbot = gr.Chatbot(
        type="messages",
        height=450,
        placeholder="Start by describing your plumbing issue...",
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
            "Do you fix water heaters?",
            "My sink is leaking.",
            "My basement is flooding from a burst pipe. I am at 22 Oak Street.",
        ],
        inputs=msg_box,
        label="Try these examples:",
    )

    gr.Markdown(
        "_Persistence: conversations survive page refreshes within the same "
        "container session. State resets on cold start (free HF Spaces)._",
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
    demo.launch(server_name="0.0.0.0", server_port=7860)
