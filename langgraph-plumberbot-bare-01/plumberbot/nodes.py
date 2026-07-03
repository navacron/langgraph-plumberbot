# LangGraph concept: NODES
# Each function below is a node — a discrete step in the graph.
# Nodes receive the current state and return a dict of fields to update.
# LangGraph merges the returned dict into the shared state.

import re

from langgraph.types import interrupt  # LangGraph concept: INTERRUPT

from .state import PlumberState

# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

EMERGENCY_KEYWORDS = [
    "flood", "flooding", "burst", "pipe burst", "sewer", "overflow",
    "water everywhere", "no water", "major leak",
]

FAQ_KEYWORDS = [
    "do you", "can you", "fix", "repair", "service", "cost",
    "price", "hour", "water heater", "heater",
]

STREET_WORDS = [
    "street", "st", "ave", "avenue", "road", "rd", "drive", "dr",
    "blvd", "boulevard", "lane", "ln", "way", "court", "ct", "place", "pl",
]


def _has_location(msg: str) -> bool:
    """Heuristic: message contains a street number or address keyword."""
    if re.search(r"\d+", msg):
        return True
    return any(word in msg for word in STREET_WORDS)


# ---------------------------------------------------------------------------
# Node 1: classify_request
# ---------------------------------------------------------------------------

def classify_request(state: PlumberState) -> dict:
    """Classify the customer message into emergency / general / missing_info.

    Uses deterministic keyword matching — no LLM required for the MVP.
    """
    msg = state["customer_message"].lower()

    is_emergency = any(kw in msg for kw in EMERGENCY_KEYWORDS)
    is_faq = any(kw in msg for kw in FAQ_KEYWORDS)

    if is_emergency:
        if _has_location(msg):
            matched = [kw for kw in EMERGENCY_KEYWORDS if kw in msg]
            return {
                "category": "emergency",
                "urgency_reason": f"Emergency keywords detected: {matched}",
                "missing_fields": [],
            }
        else:
            return {
                "category": "missing_info",
                "urgency_reason": "",
                "missing_fields": ["address", "phone number"],
            }

    if is_faq:
        return {
            "category": "general",
            "urgency_reason": "",
            "missing_fields": [],
        }

    return {
        "category": "missing_info",
        "urgency_reason": "",
        "missing_fields": ["address", "phone number", "description of issue"],
    }


# ---------------------------------------------------------------------------
# Conditional router (used as the routing function for add_conditional_edges)
# ---------------------------------------------------------------------------

# LangGraph concept: CONDITIONAL EDGE
# This function is NOT a node — it runs after classify_request and returns
# the NAME of the next node to route to. LangGraph uses the return value
# to decide which edge to follow.

def route_request(state: PlumberState) -> str:
    """Return the name of the next node based on the current category."""
    if state["category"] == "missing_info":
        return "ask_missing_info"
    elif state["category"] == "emergency":
        return "human_review"
    else:
        return "answer_faq"


# ---------------------------------------------------------------------------
# Node 2: ask_missing_info
# ---------------------------------------------------------------------------

def ask_missing_info(state: PlumberState) -> dict:
    """Ask the customer for missing info, then pause for their reply.

    Uses interrupt() so the graph checkpoints here and waits for the
    customer to type their details before continuing to save_profile.
    """
    missing = state["missing_fields"]
    items = "\n".join(f"  • {f}" for f in missing) if missing else "  • address\n  • phone number"
    question = (
        "Thanks for reaching out to PlumberBot!\n\n"
        "To help you as quickly as possible, could you please provide:\n"
        f"{items}\n"
        "  • A brief description of the issue\n"
        "  • Is water actively leaking right now? (yes/no)"
    )

    # LangGraph concept: INTERRUPT (used here to collect the customer reply)
    # Pauses the graph and surfaces the question to the CLI.
    # The customer's typed reply is returned when resumed with Command(resume=reply).
    reply = interrupt({
        "bot_message": question,
        "instructions": "Please reply with the information above.",
    })

    return {
        "final_response": question,
        "customer_reply": reply,
    }


# ---------------------------------------------------------------------------
# Node 3: save_profile
# ---------------------------------------------------------------------------

def save_profile(state: PlumberState) -> dict:
    """Parse the customer's reply and save it as a profile."""
    reply = state["customer_reply"]

    # Extract a phone number if present (simple heuristic)
    phone_match = re.search(r"[\d\-\(\)\+][\d\s\-\(\)]{7,}", reply)
    phone = phone_match.group().strip() if phone_match else "not provided"

    # Extract an address if a number + street word appears
    address = "not provided"
    addr_match = re.search(r"\d+\s+\w+(?:\s+\w+){0,3}", reply)
    if addr_match and any(w in reply.lower() for w in STREET_WORDS):
        address = addr_match.group().strip()

    profile = {
        "status": "saved",
        "raw_info": reply,
        "phone": phone,
        "address": address,
        "source": "customer_reply",
    }

    confirmation = (
        "Got it — your information has been saved!\n\n"
        f"  Phone   : {phone}\n"
        f"  Address : {address}\n"
        f"  Notes   : {reply}\n\n"
        "A plumber will be in touch within 2 hours to confirm your appointment."
    )

    return {"profile": profile, "final_response": confirmation}


# ---------------------------------------------------------------------------
# Node 4: answer_faq
# ---------------------------------------------------------------------------

def answer_faq(state: PlumberState) -> dict:
    """Return a standard FAQ answer about PlumberBot's services."""
    response = (
        "Thanks for your question!\n\n"
        "PlumberBot handles:\n"
        "  • Leaks and dripping faucets\n"
        "  • Clogged drains and toilets\n"
        "  • Water heater installation and repair\n"
        "  • Sewer line backups\n"
        "  • Emergency plumbing (burst pipes, flooding)\n\n"
        "Give us a call at (555) 123-4567 or reply with your address "
        "and issue description to schedule a visit."
    )
    return {"final_response": response}


# ---------------------------------------------------------------------------
# Node 5: human_review  (HUMAN-IN-THE-LOOP — uses interrupt())
# ---------------------------------------------------------------------------

# LangGraph concept: INTERRUPT
# interrupt() pauses graph execution here and surfaces the payload to the caller.
# The graph state is checkpointed so it can be resumed later.
# When resumed with Command(resume=<value>), interrupt() returns that value
# and the node continues from this line.
#
# IMPORTANT: The node restarts from the TOP when resumed — code before
# interrupt() runs again. Design it to be idempotent (it is here).

def human_review(state: PlumberState) -> dict:
    """Pause for a human dispatcher to approve, reject, or escalate the ticket."""
    decision = interrupt({
        "message": "Emergency plumbing dispatch requires approval",
        "customer_message": state["customer_message"],
        "urgency_reason": state["urgency_reason"],
        "options": ["approve", "reject", "escalate"],
    })
    # decision is whatever value was passed to Command(resume=...)
    return {"human_decision": decision}


# ---------------------------------------------------------------------------
# Node 6: create_ticket
# ---------------------------------------------------------------------------

def create_ticket(state: PlumberState) -> dict:
    """Create a dispatch ticket based on the human reviewer's decision."""
    decision = state["human_decision"]

    if decision == "approve":
        ticket = {
            "ticket_id": "PLUMB-001",
            "status": "created",
            "source": "LangGraph MVP",
            "customer_message": state["customer_message"],
        }
        response = (
            "Your emergency has been approved for dispatch!\n\n"
            f"Ticket #{ticket['ticket_id']} has been created. "
            "A plumber is being dispatched to your location. "
            "You will receive a call within 15 minutes."
        )
        return {"ticket": ticket, "final_response": response}

    elif decision == "reject":
        return {
            "ticket": {},
            "final_response": (
                "A human dispatcher reviewed your request and determined "
                "that additional information is needed before dispatching.\n\n"
                "Please call us directly at (555) 123-4567 or reply with "
                "more details about your situation."
            ),
        }

    else:  # escalate
        return {
            "ticket": {},
            "final_response": (
                "Your case has been escalated to a senior human dispatcher.\n\n"
                "You will be contacted within 5 minutes. If this is a life-safety "
                "emergency, please also call 911."
            ),
        }
