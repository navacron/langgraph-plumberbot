# langgraph-plumberbot-withllm-02

**Concept:** Replace bare-01's keyword matching with Claude. Same graph topology, same interrupt/resume pattern — only the node implementations change.

## What changed from bare-01

Every node that used `if/elif` keyword matching now calls Claude instead:
- `classify_request` → `llm.with_structured_output(Classification)` with adaptive thinking
- `ask_missing_info` → `llm.invoke([SystemMessage, HumanMessage])` — generates a warm question
- `save_profile` → `llm.with_structured_output(CustomerProfile)` — extracts structured data from free text
- `answer_faq` → `llm.invoke(...)` — natural language answer
- `create_ticket` → `llm.invoke(...)` — professional response based on dispatcher decision
- `human_review` — **unchanged** (no LLM involved in HITL)

## Key files

```
plumberbot/
  llm.py        — ChatAnthropic singleton: model from ANTHROPIC_MODEL env (default claude-sonnet-4-6), temp=0
  state.py      — PlumberState (same shape as bare-01, adds customer_reply for the missing_info round-trip)
  nodes.py      — all nodes now call llm; Classification and CustomerProfile are Pydantic models here
  graph.py      — graph topology identical to bare-01; uses InMemorySaver
  cli.py        — identical interrupt/resume pattern to bare-01
tests/
  test_routing.py — tests route_request() only, no API key needed
```

## LangGraph concepts demonstrated

| Concept | File:line |
|---|---|
| `with_structured_output(PydanticModel)` | `nodes.py:classify_request`, `nodes.py:save_profile` |
| Adaptive thinking | `nodes.py:classify_request` — `thinking={"type": "adaptive"}` |
| LLM text generation | `nodes.py:answer_faq`, `nodes.py:create_ticket` |
| `interrupt()` round-trip | `nodes.py:ask_missing_info` — interrupt waits for customer reply |
| State passing context | `state.py:customer_reply` — set after interrupt, consumed by save_profile |

## Running

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add ANTHROPIC_API_KEY
python -m plumberbot.cli
python -m plumberbot.cli --scenario missing   # or general / emergency
```

## API keys

- `ANTHROPIC_API_KEY` — required
- `ANTHROPIC_MODEL` — optional, default `claude-sonnet-4-6`

## Key implementation pattern

```python
# Classification with structured output
class Classification(BaseModel):
    category: Literal["emergency", "general", "missing_info"]
    urgency_reason: str = ""
    missing_fields: list[str] = []

structured_llm = llm.with_structured_output(Classification)
result: Classification = structured_llm.invoke([SystemMessage(...), HumanMessage(state["customer_message"])])
```
