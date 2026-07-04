# langgraph-plumberbot-bare-01

**Concept:** Core LangGraph mechanics with zero LLM calls. Classification is pure keyword/regex matching. The focus is entirely on graph structure, state, and human-in-the-loop.

## What it does

Classifies customer plumbing messages into three categories and routes them:
- `missing_info` → asks for address/phone
- `general` → returns a static FAQ answer
- `emergency` → pauses with `interrupt()` for a human dispatcher to approve/reject/escalate, then creates a ticket

## Key files

```
plumberbot/
  state.py      — PlumberState TypedDict: customer_message, category, missing_fields, decision, final_response
  nodes.py      — classify_request (regex), ask_missing_info, answer_faq, human_review (interrupt), create_ticket
  graph.py      — StateGraph wired with InMemorySaver; route_request() is the conditional edge function
  cli.py        — runs 3 scenarios; handles interrupt detection via result["__interrupt__"] and Command(resume=...)
tests/
  test_routing.py — tests route_request() in isolation, no API key needed
```

## LangGraph concepts demonstrated

| Concept | File:line |
|---|---|
| `StateGraph` | `graph.py` |
| `TypedDict` state | `state.py` |
| `interrupt()` | `nodes.py:human_review` |
| `InMemorySaver` | `graph.py` |
| `Command(resume=...)` | `cli.py` |
| `thread_id` in config | `cli.py` |
| Conditional edges | `graph.py:route_request` |

## Running

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m plumberbot.cli                      # all three scenarios
python -m plumberbot.cli --scenario emergency # one scenario
```

No `.env` needed — no API keys required.

## How interrupt/resume works

1. `human_review` calls `interrupt(payload)` — graph checkpoints and `graph.invoke()` returns early
2. `result["__interrupt__"]` contains the payload
3. CLI prompts user for a decision
4. `graph.invoke(Command(resume=decision), config=config)` resumes from the checkpoint
5. `interrupt()` returns the decision value; graph continues to `create_ticket`

The same `thread_id` in both `invoke()` calls is what ties them to the same checkpoint.
