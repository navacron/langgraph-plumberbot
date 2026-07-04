from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import AnyMessage, add_messages


class InputState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


class PlumberState(InputState):
    customer_id: Optional[int]
    loaded_memory: str
