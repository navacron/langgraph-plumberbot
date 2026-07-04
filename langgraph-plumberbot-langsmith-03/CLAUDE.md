# langgraph-plumberbot-langsmith-03

**Concept:** Deploy the withllm-02 graph to LangGraph Cloud and call it over HTTP via the `langgraph-sdk`. The graph code is unchanged; what changes is the runtime and the client.

## Architecture

```
Terminal 1: langgraph dev  →  LangGraph Server at localhost:2024
Terminal 2: python -m cli.main  →  SDK client makes HTTP calls to the server
```

The CLI uses `langgraph-sdk` to stream runs, detect interrupts via thread state polling, and resume — the exact same pattern a Next.js frontend would use.

## Key files

```
plumberbot/       ← server side (deployed to LangGraph Cloud)
  graph.py        — compiled WITHOUT a checkpointer (server injects Postgres/Redis)
  nodes.py        — identical to withllm-02
  llm.py          — identical to withllm-02
  state.py        — identical to withllm-02
cli/              ← client side (runs locally against the server)
  scenarios.py    — async functions using langgraph-sdk; Next.js equivalents annotated in comments
  main.py         — argparse entry point, asyncio.run()
langgraph.json    — registers plumberbot graph for the server
pyproject.toml    — base deps (server) + [dev] extras (cli, sdk, pytest)
```

## LangGraph concepts demonstrated

| Concept | File:line |
|---|---|
| `langgraph.json` graph registration | `langgraph.json` |
| `langgraph dev` local server | Terminal command |
| `client.threads.create()` | `cli/scenarios.py` |
| `client.runs.stream(stream_mode="values")` | `cli/scenarios.py:_stream_until_done` |
| Interrupt detection via HTTP | `cli/scenarios.py:_get_interrupt` — polls `client.threads.get_state()` |
| Resume via SDK | `command={"resume": value}` in `client.runs.stream()` |
| No checkpointer in graph | `graph.py` — server injects durable storage |

## Running

```bash
# Install everything (server package + cli + sdk + pytest)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # add ANTHROPIC_API_KEY

# Terminal 1
langgraph dev

# Terminal 2
python -m cli.main --scenario emergency
```

## Deployment tiers

1. **`langgraph dev`** — local, in-memory, free (default, already working)
2. **Docker** — `langgraph build -t img && docker compose up` — durable Postgres+Redis, free
3. **LangSmith Cloud** — `langgraph deploy` — fully managed, requires Plus plan (~$39+/month)

Set `LANGGRAPH_URL` in `.env` to switch between tiers — CLI code is unchanged.

## API keys

- `ANTHROPIC_API_KEY` — required
- `LANGSMITH_API_KEY` — required for Docker tier and LangSmith Cloud tier
- `LANGGRAPH_URL` — default `http://127.0.0.1:2024`; change for Docker/Cloud
