from typing import Annotated, Optional
from typing_extensions import TypedDict
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.managed.is_last_step import RemainingSteps


class InputState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


class PlumberState(InputState):
    customer_id: Optional[int]
    loaded_memory: str
    remaining_steps: RemainingSteps
    # Registration flow — set when a phone number is looked up but not found
    pending_phone: Optional[str]
    pending_name: Optional[str]
