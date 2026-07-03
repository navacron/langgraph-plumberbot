"""CLI demo for PlumberBot withllm-02 — LangGraph + Claude API.

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
from .llm import MODEL
from .state import PlumberState


EXAMPLES = {
    "missing": "My sink is leaking.",
    "general": "Do you fix water heaters?",
    "emergency": "My basement is flooding from a burst pipe. I am at 22 Oak Street.",
}


def make_initial_state(message: str) -> PlumberState:
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


def _divider(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print("=" * 60)


def run_missing(thread_id: str = "scenario-missing-1") -> None:
    _divider("SCENARIO: Missing Information (LLM-powered)")
    message = EXAMPLES["missing"]
    print(f"Customer message: {message!r}\n")
    print("  [Calling Claude to classify and generate question...]\n")

    config = {"configurable": {"thread_id": thread_id}}

    # Phase 1: classify + ask — graph pauses at interrupt() in ask_missing_info
    result = graph.invoke(make_initial_state(message), config=config)

    if "__interrupt__" not in result:
        print(f"Category : {result['category']}")
        print(f"\nResponse :\n{result['final_response']}")
        return

    payload = result["__interrupt__"][0].value
    print(f"Category : {result['category']}")
    print(f"\nBot asks:\n{payload['bot_message']}\n")

    print("(Type your details and press Enter)\n")
    customer_reply = input("Customer reply: ").strip()

    # Phase 2: resume → save_profile extracts structured data via Claude
    print("\n  [Calling Claude to extract profile from reply...]\n")
    print(">>> Graph resumed — saving profile <<<\n")
    final = graph.invoke(Command(resume=customer_reply), config=config)

    print(f"Profile saved : {json.dumps(final['profile'], indent=2)}")
    print(f"\nBot response  :\n{final['final_response']}")


def run_general(thread_id: str = "scenario-general-1") -> None:
    _divider("SCENARIO: General Question (LLM-powered FAQ)")
    message = EXAMPLES["general"]
    print(f"Customer: {message!r}\n")
    print("  [Calling Claude to generate FAQ response...]\n")

    config = {"configurable": {"thread_id": thread_id}}
    result = graph.invoke(make_initial_state(message), config=config)

    print(f"Category : {result['category']}")
    print(f"\nResponse :\n{result['final_response']}")


def run_emergency(thread_id: str = "scenario-emergency-1") -> None:
    _divider("SCENARIO: Emergency Dispatch (Human-in-the-Loop)")
    message = EXAMPLES["emergency"]
    print(f"Customer: {message!r}\n")
    print("  [Calling Claude to classify emergency...]\n")

    # LangGraph concept: CHECKPOINTER + thread_id
    # Same config is used for the initial invoke AND the resume.
    config = {"configurable": {"thread_id": thread_id}}

    # Phase 1: run until interrupt() inside human_review
    result = graph.invoke(make_initial_state(message), config=config)

    if "__interrupt__" not in result:
        print(f"Category : {result['category']}")
        print(f"\nResponse :\n{result['final_response']}")
        return

    interrupt_payload = result["__interrupt__"][0].value
    print(">>> GRAPH PAUSED — human review required <<<\n")
    print(json.dumps(interrupt_payload, indent=2))

    print("\nOptions:", interrupt_payload.get("options", ["approve", "reject", "escalate"]))
    while True:
        decision = input("Enter decision [approve / reject / escalate]: ").strip().lower()
        if decision in ("approve", "reject", "escalate"):
            break
        print("  Invalid — please type approve, reject, or escalate.")

    print(f"\n  [Calling Claude to generate response for decision: {decision!r}...]\n")
    print(f">>> Resuming graph with decision: {decision!r} <<<\n")

    # Phase 2: resume — Command(resume=...) re-enters human_review, then create_ticket
    final = graph.invoke(Command(resume=decision), config=config)

    print(f"Category  : {final['category']}")
    print(f"Decision  : {final['human_decision']}")
    if final.get("ticket"):
        print(f"Ticket    : {json.dumps(final['ticket'], indent=2)}")
    print(f"\nResponse  :\n{final['final_response']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"PlumberBot withllm-02 — LangGraph + Claude API (model: {MODEL})"
    )
    parser.add_argument(
        "--scenario",
        choices=["missing", "general", "emergency", "all"],
        default="all",
        help="Which scenario to run (default: all)",
    )
    args = parser.parse_args()

    print(f"\nModel: {MODEL}")
    print("Scenarios make live Anthropic API calls. Ensure ANTHROPIC_API_KEY is set.\n")

    if args.scenario in ("missing", "all"):
        run_missing()

    if args.scenario in ("general", "all"):
        run_general()

    if args.scenario in ("emergency", "all"):
        run_emergency()


if __name__ == "__main__":
    main()
