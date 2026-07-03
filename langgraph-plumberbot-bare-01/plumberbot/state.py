# LangGraph concept: STATE
# The state is a TypedDict that flows through every node in the graph.
# Each node receives the full state and returns a dict of fields to update.
# LangGraph merges those updates back into the shared state automatically.

from typing_extensions import TypedDict


class PlumberState(TypedDict):
    customer_message: str      # raw input from the customer
    category: str              # "emergency" | "general" | "missing_info"
    missing_fields: list[str]  # fields the customer forgot to provide
    urgency_reason: str        # why this was flagged as an emergency
    human_decision: str        # "approve" | "reject" | "escalate" (set after interrupt)
    ticket: dict               # dispatch ticket created after approval
    customer_reply: str        # customer's follow-up reply after being asked for info
    profile: dict              # saved customer profile extracted from the reply
    final_response: str        # message to show the customer at the end
