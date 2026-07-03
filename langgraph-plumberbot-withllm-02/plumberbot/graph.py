from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from .nodes import (
    classify_request,
    route_request,
    ask_missing_info,
    save_profile,
    answer_faq,
    human_review,
    create_ticket,
)
from .state import PlumberState


def build_graph():
    builder = StateGraph(PlumberState)

    builder.add_node("classify_request", classify_request)
    builder.add_node("ask_missing_info", ask_missing_info)
    builder.add_node("save_profile", save_profile)
    builder.add_node("answer_faq", answer_faq)
    builder.add_node("human_review", human_review)
    builder.add_node("create_ticket", create_ticket)

    builder.add_edge(START, "classify_request")
    builder.add_conditional_edges("classify_request", route_request)
    builder.add_edge("ask_missing_info", "save_profile")
    builder.add_edge("save_profile", END)
    builder.add_edge("answer_faq", END)
    builder.add_edge("human_review", "create_ticket")
    builder.add_edge("create_ticket", END)

    # LangGraph concept: CHECKPOINTER
    # InMemorySaver keeps graph state in memory so interrupt/resume works.
    # Swap for SqliteSaver or PostgresSaver for production persistence.
    return builder.compile(checkpointer=InMemorySaver())


graph = build_graph()
