"""CLI demo for the PlumberBot HITL LangGraph project.

Demonstrates three scenarios:
  missing   — customer message is missing address/contact info
  general   — customer asks a general FAQ-style question
  emergency — emergency dispatch that pauses for human approval (interrupt/resume)

Usage:
  python -m plumberbot.cli                    # runs all three scenarios
  python -m plumberbot.cli --scenario missing
  python -m plumberbot.cli --scenario general
  python -m plumberbot.cli --scenario emergency
"""

import argparse
import json

from langgraph.types import Command  # LangGraph concept: RESUME

from .graph import graph
from .state import PlumberState

# ---------------------------------------------------------------------------
# Example messages
# ---------------------------------------------------------------------------

EXAMPLES = {
    "missing": "My sink is leaking.",
    "general": "Do you fix water heaters?",
    "emergency": "My basement is flooding from a burst pipe. I am at 22 Oak Street.",
}


def make_initial_state(message: str) -> PlumberState:
    """Return a fully-initialised state dict with empty defaults."""
    return PlumberState(
        customer_message=message,
        category="",
        missing_fields=[],
        urgency_reason="",
        human_decision="",
        ticket={},
        customer_reply="",
        profile={},
        final_response="",
    )


# ---------------------------------------------------------------------------
# Scenario runners
# ---------------------------------------------------------------------------

def _divider(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def run_missing(thread_id: str = "scenario-missing-1") -> None:
    _divider("SCENARIO: Missing Information")
    message = EXAMPLES["missing"]
    print(f"Customer message: {message!r}\n")

    config = {"configurable": {"thread_id": thread_id}}

    # --- Phase 1: classify + ask ---
    # Graph runs to ask_missing_info, which calls interrupt() and pauses.
    result = graph.invoke(make_initial_state(message), config=config)

    if "__interrupt__" not in result:
        print(f"Category : {result['category']}")
        print(f"\nResponse :\n{result['final_response']}")
        return

    # Show the bot's question to the customer
    payload = result["__interrupt__"][0].value
    print(f"Category : {result['category']}")
    print(f"Missing  : {result['missing_fields']}")
    print(f"\nBot asks:\n{payload['bot_message']}\n")

    # Collect the customer's reply
    print("(Type your details and press Enter)\n")
    customer_reply = input("Customer reply: ").strip()

    # --- Phase 2: resume → save_profile ---
    # Command(resume=...) sends the reply back into ask_missing_info,
    # which returns it as customer_reply, then save_profile runs.
    print("\n>>> Graph resumed — saving profile <<<\n")
    final = graph.invoke(Command(resume=customer_reply), config=config)

    print(f"Profile saved : {json.dumps(final['profile'], indent=2)}")
    print(f"\nBot response  :\n{final['final_response']}")


def run_general(thread_id: str = "scenario-general-1") -> None:
    _divider("SCENARIO: General Question (FAQ)")
    message = EXAMPLES["general"]
    print(f"Customer: {message!r}\n")

    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(make_initial_state(message), config=config)

    print(f"Category : {result['category']}")
    print(f"\nResponse :\n{result['final_response']}")


def run_emergency(thread_id: str = "scenario-emergency-1") -> None:
    _divider("SCENARIO: Emergency Dispatch (Human-in-the-Loop)")
    message = EXAMPLES["emergency"]
    print(f"Customer: {message!r}\n")

    # LangGraph concept: CHECKPOINTER + thread_id
    # The same config must be used for both the initial invoke and the resume.
    # The checkpointer uses thread_id to find the saved state.
    config = {"configurable": {"thread_id": thread_id}}

    # --- Phase 1: Run until interrupt ---
    # The graph hits interrupt() inside human_review and returns early.
    # result["__interrupt__"] contains the payload passed to interrupt().
    result = graph.invoke(make_initial_state(message), config=config)

    if "__interrupt__" not in result:
        # Unexpected: graph finished without pausing
        print(f"Category : {result['category']}")
        print(f"\nResponse :\n{result['final_response']}")
        return

    # --- Interrupt surfaced ---
    interrupt_payload = result["__interrupt__"][0].value
    print(">>> GRAPH PAUSED — human review required <<<\n")
    print(json.dumps(interrupt_payload, indent=2))

    # Ask the human dispatcher for a decision
    print("\nOptions:", interrupt_payload.get("options", ["approve", "reject", "escalate"]))
    while True:
        decision = input("Enter decision [approve / reject / escalate]: ").strip().lower()
        if decision in ("approve", "reject", "escalate"):
            break
        print("  Invalid input — please type approve, reject, or escalate.")

    print(f"\n>>> Resuming graph with decision: {decision!r} <<<\n")

    # --- Phase 2: Resume ---
    # LangGraph concept: RESUME
    # Command(resume=<value>) is passed instead of a new state dict.
    # The graph picks up exactly where it left off; interrupt() returns
    # <value> inside human_review, which then flows into create_ticket.
    final = graph.invoke(Command(resume=decision), config=config)

    print(f"Category  : {final['category']}")
    print(f"Decision  : {final['human_decision']}")
    if final.get("ticket"):
        print(f"Ticket    : {json.dumps(final['ticket'], indent=2)}")
    print(f"\nResponse  :\n{final['final_response']}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="PlumberBot HITL demo — LangGraph human-in-the-loop example"
    )
    parser.add_argument(
        "--scenario",
        choices=["missing", "general", "emergency", "all"],
        default="all",
        help="Which scenario to run (default: all)",
    )
    args = parser.parse_args()

    if args.scenario in ("missing", "all"):
        run_missing()

    if args.scenario in ("general", "all"):
        run_general()

    if args.scenario in ("emergency", "all"):
        run_emergency()


if __name__ == "__main__":
    main()
