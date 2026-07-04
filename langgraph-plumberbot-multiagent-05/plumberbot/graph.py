"""Build the outer PlumberBot multi-agent graph.

Graph topology:
  START → verify_customer → (interrupt) → human_input → verify_customer
                          → load_memory → supervisor → save_memory → END
"""

from langgraph.graph import END, START, StateGraph

from .agents.supervisor import build_supervisor
from .nodes import human_input, load_memory, save_memory, should_interrupt, verify_customer
from .state import InputState, PlumberState


def build_graph(checkpointer=None):
    supervisor = build_supervisor()

    graph = StateGraph(PlumberState, input=InputState)

    graph.add_node("verify_customer", verify_customer)
    graph.add_node("human_input", human_input)
    graph.add_node("load_memory", load_memory)
    graph.add_node("supervisor", supervisor)
    graph.add_node("save_memory", save_memory)

    graph.add_edge(START, "verify_customer")
    graph.add_conditional_edges(
        "verify_customer",
        should_interrupt,
        {"continue": "load_memory", "interrupt": "human_input"},
    )
    graph.add_edge("human_input", "verify_customer")
    graph.add_edge("load_memory", "supervisor")
    graph.add_edge("supervisor", "save_memory")
    graph.add_edge("save_memory", END)

    return graph.compile(checkpointer=checkpointer)
