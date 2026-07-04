# langgraph-plumberbot-hugging-04

**Concept:** Replace the CLI with a Gradio web UI, swap `InMemorySaver` for `SqliteSaver`, and deploy as a single Docker container to Hugging Face Spaces. No LangGraph Server needed.

## Architecture

```
HF Spaces Docker container (port 7860)
  app.py — Gradio UI
    └── graph.invoke() / Command(resume=...) — direct Python calls, no HTTP
  plumberbot/ — same graph + nodes as withllm-02
  /tmp/plumberbot.db — SqliteSaver checkpoint file (ephemeral on free tier)
```

## What changed from withllm-02

| Concern | withllm-02 | hugging-04 |
|---|---|---|
| Checkpointer | `InMemorySaver` | `SqliteSaver` (file-based) |
| UI | `input()` blocking CLI | Gradio `gr.Chatbot` |
| `graph.py` | hardcodes checkpointer | `build_graph(checkpointer=None)` injectable |
| Entry point | `python -m plumberbot.cli` | `python app.py` |

## Key files

```
app.py            — Gradio UI; gr.State holds {thread_id, waiting_for_interrupt} per session
plumberbot/
  graph.py        — build_graph(checkpointer=None) — checkpointer injected at startup
  nodes.py        — identical to withllm-02
  llm.py          — identical to withllm-02
Dockerfile        — python:3.11-slim, port 7860, uid 1000 (HF Spaces requirement)
```

## LangGraph concepts demonstrated

| Concept | File:line |
|---|---|
| `SqliteSaver` | `app.py` — `SqliteSaver(sqlite3.connect(DB_PATH))` |
| Injectable checkpointer | `graph.py:build_graph(checkpointer=None)` |
| Per-session `thread_id` | `app.py` — `uuid.uuid4()` per new chat, stored in `gr.State` |
| Interrupt detection | `app.py:send_message` — `"__interrupt__" in result` |
| Interrupt resume | `app.py:send_message` — `graph.invoke(Command(resume=user_msg), config)` |

## Running locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add ANTHROPIC_API_KEY
python app.py
# → http://localhost:7860
```

## Docker test

```bash
docker build -t plumberbot-hf .
docker run -p 7860:7860 -e ANTHROPIC_API_KEY=sk-ant-... plumberbot-hf
```

## Deploying to HF Spaces

```bash
# From monorepo root — one-time setup
git remote add space https://huggingface.co/spaces/<username>/<space-name>

# Push just this subfolder
git subtree push --prefix langgraph-plumberbot-hugging-04 space main
```

Add `ANTHROPIC_API_KEY` as a Secret in the Space settings (Variables and secrets tab).

## Persistence

- **Free tier** (`/tmp/plumberbot.db`): survives page refreshes, resets on cold start
- **Pro tier** (`/data/plumberbot.db` + Persistent Storage): survives container restarts

Change `DB_PATH` env var to switch — no code changes needed.

## API keys

- `ANTHROPIC_API_KEY` — required
- `ANTHROPIC_MODEL` — optional, default `claude-sonnet-4-6`
- `DB_PATH` — optional, default `/tmp/plumberbot.db`
