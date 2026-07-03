from langgraph.graph import StateGraph, START, END

from plumberbot.nodes import (
    classify_request,
    route_request,
    ask_missing_info,
    save_profile,
    answer_faq,
    human_review,
    create_ticket,
)
from plumberbot.state import PlumberState


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

    # No checkpointer here — LangGraph Server (local dev or cloud) injects
    # its own durable checkpointer (SQLite locally, Postgres in cloud).
    return builder.compile()


graph = build_graph()
