# langgraph-plumberbot-multiagent-05

**Concept:** Multi-agent architecture using `create_react_agent`. A supervisor routes customer requests to three specialist subagents. Adds a pre-seeded SQLite business database, long-term customer memory, identity verification with HITL, and a RAG knowledge base.

## Architecture

```
START
  └── verify_customer — extracts phone from message, looks up in DB
        │ not found → human_input (interrupt) → verify_customer (loop)
        │ found → sets customer_id in state
    load_memory — reads customer_profile table → loaded_memory string
        │
    supervisor (create_react_agent)
        ├── call_scheduling_subagent → scheduling_subagent (create_react_agent)
        │     tools: get_customer_info, get_service_catalog, get_appointments,
        │            get_available_plumbers, book_appointment
        ├── call_dispatch_subagent → dispatch_subagent (create_react_agent)
        │     tools: get_open_tickets, get_all_tickets, create_ticket, get_plumber_on_call
        └── call_knowledge_subagent → knowledge_subagent (create_react_agent)
              tools: search_knowledge_base, list_articles
        │
    save_memory — upserts customer_profile table
        │
       END
```

## Key files

```
plumberbot/
  state.py          — InputState (messages only) + PlumberState (adds customer_id, loaded_memory)
  llm.py            — ChatAnthropic singleton, temp=0
  db.py             — singleton SQLite connection to business DB; run_query(), run_write()
  knowledge.py      — get_retriever(): auto-selects OpenAI vector or BM25 based on OPENAI_API_KEY
  nodes.py          — verify_customer, human_input, load_memory, save_memory, should_interrupt
  graph.py          — build_graph(checkpointer=None) → StateGraph(PlumberState, input=InputState)
  tools/
    scheduling.py   — 5 tools; all use InjectedState("customer_id")
    dispatch.py     — 4 tools; create_ticket uses Literal priority
    knowledge.py    — search_knowledge_base, list_articles
  agents/
    scheduling.py   — build_scheduling_subagent() with dynamic prompt including loaded_memory
    dispatch.py     — build_dispatch_subagent()
    knowledge.py    — build_knowledge_subagent()
    supervisor.py   — build_supervisor(); subagents wrapped as @tool with InjectedState
db/
  plumberbot.db     — committed to git; 6 tables, pre-seeded
  seed.py           — recreate the DB: python db/seed.py
docs/
  *.txt             — 5 plumbing how-to articles for RAG corpus
cli.py              — MemorySaver (in-memory); handles interrupt via result["__interrupt__"]
app.py              — SqliteSaver; Gradio UI; same gr.State pattern as hugging-04
```

## LangGraph concepts demonstrated

| Concept | File:line |
|---|---|
| `create_react_agent` | `agents/*.py` — all 4 agents (3 subagents + supervisor) |
| `InjectedState("customer_id")` | `tools/scheduling.py`, `tools/dispatch.py`, `agents/supervisor.py` |
| Supervisor → subagent-as-tool | `agents/supervisor.py` — subagents called via `.invoke()` inside `@tool` |
| `state_schema=PlumberState` | All `create_react_agent` calls — makes customer_id available in agent state |
| `InputState` / `PlumberState` | `state.py` — two-tier schema restricts external callers to `messages` only |
| `messages: Annotated[list[AnyMessage], add_messages]` | `state.py` — conversational vs single-shot |
| HITL verification loop | `nodes.py:verify_customer` + `human_input` → loop back |
| Long-term memory (SQL) | `nodes.py:load_memory`, `save_memory` + `customer_profile` table |
| Dynamic prompt function | `agents/scheduling.py:_make_prompt` — injects loaded_memory into system message |
| RAG dual backend | `knowledge.py:get_retriever` — OpenAI vector or BM25, auto-selected |
| Lazy initialization | `knowledge.py:get_retriever` — builds on first call, not at import |

## Database

Two separate SQLite files — never mix them:

| File | Purpose | Committed |
|---|---|---|
| `db/plumberbot.db` | Business data (customers, tickets, appointments, etc.) | Yes |
| `/tmp/plumberbot_checkpoints.db` | LangGraph conversation checkpoints | No (ephemeral) |

Tables: `customers` (6 rows), `service_catalog` (10), `plumbers` (4), `appointments` (6), `tickets` (5), `customer_profile` (3).

Test phone numbers from seed data: Jane Doe `(555) 111-2222`, Bob Smith `(555) 333-4444`.

To recreate: `python3 db/seed.py`

## RAG backend

Auto-selected at startup based on env vars:
- `OPENAI_API_KEY` set → `InMemoryVectorStore` + `text-embedding-3-small` (semantic search)
- Anthropic only → `BM25Retriever` from `langchain_community` (keyword search, no API)

Both expose the same `search_knowledge_base(query)` tool. Startup log confirms which is active:
```
[knowledge] RAG backend: OpenAI vector (text-embedding-3-small) — 65 chunks loaded
```

Note: Anthropic has no embeddings API.

## Running

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set ANTHROPIC_API_KEY (required), OPENAI_API_KEY (optional)

python3 db/seed.py     # only needed if db/plumberbot.db is missing or to reset

python cli.py          # CLI entry point
python app.py          # Gradio UI → http://localhost:7860
```

## Tests

```bash
python -m pytest tests/test_tools.py -v   # 15 tests; no API key needed
python -m pytest tests/test_rag.py -v     # needs ANTHROPIC_API_KEY at minimum
```

## API keys

- `ANTHROPIC_API_KEY` — required for all LLM calls
- `OPENAI_API_KEY` — optional; upgrades knowledge search from BM25 to semantic vector
- `ANTHROPIC_MODEL` — optional, default `claude-sonnet-4-6`
- `BUSINESS_DB_PATH` — optional, default `db/plumberbot.db`
- `CHECKPOINT_DB_PATH` — optional (app.py only), default `/tmp/plumberbot_checkpoints.db`

## Deploying to HF Spaces

```bash
# From monorepo root
git remote add space https://huggingface.co/spaces/<username>/<space-name>
git subtree push --prefix langgraph-plumberbot-multiagent-05 space main
```

Add `ANTHROPIC_API_KEY` (required) and `OPENAI_API_KEY` (optional) as Secrets in Space settings.
