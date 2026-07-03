"""Async scenario runners — each mirrors what a Next.js API route would do.

Every function:
  1. Creates a thread (Next.js: stores thread_id in sessionStorage / DB)
  2. Streams a run (Next.js: forwards SSE to the browser via ReadableStream)
  3. Detects interrupts via thread state (Next.js: returns JSON to UI)
  4. Resumes with command={"resume": value} (Next.js: POST handler calls SDK)

The LangGraph SDK client speaks the same HTTP API regardless of whether the
server is `langgraph dev` (local) or LangSmith Cloud.
"""

import json

GRAPH_ID = "plumberbot"

DIVIDER = "=" * 60


def _initial_state(message: str) -> dict:
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


async def _stream_until_done(client, thread_id: str, input_: dict | None, command: dict | None = None) -> dict:
    """Stream a run and return the final state snapshot.

    Next.js equivalent:
      const stream = await client.runs.stream(threadId, GRAPH_ID, { input, command, streamMode: "values" })
      for await (const chunk of stream) { ... }
    """
    final_state: dict = {}
    async for chunk in client.runs.stream(
        thread_id,
        GRAPH_ID,
        input=input_,
        command=command,
        stream_mode="values",
    ):
        if chunk.event == "values":
            final_state = chunk.data
    return final_state


async def _get_interrupt(client, thread_id: str) -> dict | None:
    """Return the interrupt payload if the graph is paused, else None.

    Next.js equivalent:
      const state = await client.threads.getState(threadId)
      return state.next.length > 0 ? state.tasks[0].interrupts[0].value : null
    """
    thread_state = await client.threads.get_state(thread_id)
    if thread_state.next:
        return thread_state.tasks[0].interrupts[0].value
    return None


# ── Scenario: General question ────────────────────────────────────────────────

async def run_general(client) -> None:
    print(f"\n{DIVIDER}")
    print("  SCENARIO: General Question (LLM-powered FAQ)")
    print(DIVIDER)

    message = "Do you fix water heaters?"
    print(f"Customer: '{message}'\n")

    thread = await client.threads.create()
    thread_id = thread["thread_id"]

    print("  [Calling Claude to generate FAQ response...]\n")
    state = await _stream_until_done(client, thread_id, _initial_state(message))

    print(f"Category : {state.get('category', '')}\n")
    print(f"Response :\n{state.get('final_response', '')}\n")


# ── Scenario: Missing information (LLM round-trip with interrupt) ─────────────

async def run_missing(client) -> None:
    print(f"\n{DIVIDER}")
    print("  SCENARIO: Missing Information (LLM-powered)")
    print(DIVIDER)

    message = "My sink is leaking."
    print(f"Customer message: '{message}'\n")

    thread = await client.threads.create()
    thread_id = thread["thread_id"]

    # ── Phase 1: classify → ask_missing_info → interrupt ──────────────────────
    print("  [Calling Claude to classify and generate question...]\n")
    await _stream_until_done(client, thread_id, _initial_state(message))

    interrupt_payload = await _get_interrupt(client, thread_id)
    if not interrupt_payload:
        print("(no interrupt — graph completed without asking for info)")
        return

    bot_question = interrupt_payload["bot_message"]
    category_state = await client.threads.get_state(thread_id)
    print(f"Category : {category_state.values.get('category', '')}\n")
    print(f"Bot asks:\n{bot_question}\n")

    # ── Human reply (CLI prompt — Next.js: form input → POST /api/resume) ─────
    print("(Type your details and press Enter)")
    customer_reply = input("\nCustomer reply: ").strip()
    if not customer_reply:
        customer_reply = "Jane Doe, 15 Elm Street, (555) 999-1234, slow drip under the sink, no flooding"
        print(f"  (using demo reply: {customer_reply})")

    # ── Phase 2: resume → save_profile → END ──────────────────────────────────
    print("\n  [Calling Claude to extract profile from reply...]\n")
    print(">>> Graph resumed — saving profile <<<\n")

    final_state = await _stream_until_done(
        client, thread_id, input_=None, command={"resume": customer_reply}
    )

    profile = final_state.get("profile", {})
    print(f"Profile saved : {json.dumps(profile, indent=2)}\n")
    print(f"Bot response  :\n{final_state.get('final_response', '')}\n")


# ── Scenario: Emergency with human-in-the-loop approval ──────────────────────

async def run_emergency(client) -> None:
    print(f"\n{DIVIDER}")
    print("  SCENARIO: Emergency Dispatch (Human-in-the-Loop)")
    print(DIVIDER)

    message = "My basement is flooding from a burst pipe. I am at 22 Oak Street."
    print(f"Customer: '{message}'\n")

    thread = await client.threads.create()
    thread_id = thread["thread_id"]

    # ── Phase 1: classify → human_review → interrupt ──────────────────────────
    print("  [Calling Claude to classify emergency...]\n")
    await _stream_until_done(client, thread_id, _initial_state(message))

    interrupt_payload = await _get_interrupt(client, thread_id)
    if not interrupt_payload:
        print("(no interrupt — check classification)")
        return

    print(">>> GRAPH PAUSED — human review required <<<\n")
    print(json.dumps(interrupt_payload, indent=2))

    # ── Human decision (CLI prompt — Next.js: button click → POST /api/resume) ─
    options = interrupt_payload.get("options", ["approve", "reject", "escalate"])
    print(f"\nOptions: {options}")
    decision = input(f"Enter decision [{' / '.join(options)}]: ").strip().lower()
    if decision not in options:
        decision = "approve"
        print(f"  (invalid input — defaulting to '{decision}')")

    # ── Phase 2: resume → create_ticket → END ─────────────────────────────────
    print(f"\n  [Calling Claude to generate response for decision: '{decision}'...]\n")
    print(f">>> Resuming graph with decision: '{decision}' <<<\n")

    final_state = await _stream_until_done(
        client, thread_id, input_=None, command={"resume": decision}
    )

    category_state = await client.threads.get_state(thread_id)
    print(f"Category  : {category_state.values.get('category', '')}")
    print(f"Decision  : {final_state.get('human_decision', '')}")

    ticket = final_state.get("ticket", {})
    if ticket:
        print(f"Ticket    : {json.dumps(ticket, indent=2)}")

    print(f"\nResponse  :\n{final_state.get('final_response', '')}\n")
