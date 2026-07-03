# LangGraph concept: GRAPH
# StateGraph is the container that wires nodes and edges together.
# compile() validates the graph structure and attaches the checkpointer.

# LangGraph concept: CHECKPOINTER
# The checkpointer saves graph state to storage after every step.
# This is what makes interrupt() and resume possible — without it,
# the graph forgets its state the moment it pauses.

from langgraph.checkpoint.memory import InMemorySaver  # in-memory checkpointer (dev/demo)
from langgraph.graph import END, START, StateGraph

from .nodes import (
    ask_missing_info,
    classify_request,
    create_ticket,
    answer_faq,
    human_review,
    route_request,
    save_profile,
)
from .state import PlumberState


def build_graph() -> StateGraph:
    builder = StateGraph(PlumberState)

    # --- Nodes ---
    # LangGraph concept: NODE — each function is a discrete processing step
    builder.add_node("classify_request", classify_request)
    builder.add_node("ask_missing_info", ask_missing_info)
    builder.add_node("save_profile", save_profile)
    builder.add_node("answer_faq", answer_faq)
    builder.add_node("human_review", human_review)
    builder.add_node("create_ticket", create_ticket)

    # --- Edges ---
    # LangGraph concept: EDGE — deterministic transition between two nodes
    builder.add_edge(START, "classify_request")

    # LangGraph concept: CONDITIONAL EDGE
    # After classify_request, call route_request(state) to decide the next node.
    # route_request returns a string matching one of the registered node names.
    builder.add_conditional_edges("classify_request", route_request)

    # Missing-info path: ask → (interrupt) → save_profile → done
    builder.add_edge("ask_missing_info", "save_profile")
    builder.add_edge("save_profile", END)
    builder.add_edge("answer_faq", END)
    builder.add_edge("human_review", "create_ticket")
    builder.add_edge("create_ticket", END)

    # LangGraph concept: CHECKPOINTER (attached at compile time)
    # InMemorySaver keeps state in RAM — fine for demos; use SqliteSaver
    # or PostgresSaver for persistence across process restarts.
    return builder.compile(checkpointer=InMemorySaver())


# Single graph instance shared across the process.
# The InMemorySaver lives inside this object, so both the first invoke()
# (which hits interrupt) and the resume invoke() must use this same instance.
graph = build_graph()
