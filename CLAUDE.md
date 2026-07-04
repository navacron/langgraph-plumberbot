# langgraph-plumberbot monorepo

A teaching series of five progressively complex LangGraph examples, all built around the same plumbing service triage scenario. Each project adds exactly one new concept on top of the last.

## Project progression

| Folder | Concept added | Entry point |
|---|---|---|
| `langgraph-plumberbot-bare-01` | `StateGraph`, typed state, `interrupt()`, `InMemorySaver` — no LLM | `python -m plumberbot.cli` |
| `langgraph-plumberbot-withllm-02` | Claude via `langchain-anthropic`, `with_structured_output`, adaptive thinking | `python -m plumberbot.cli` |
| `langgraph-plumberbot-langsmith-03` | LangGraph Cloud / `langgraph dev`, `langgraph-sdk` HTTP client, async streaming | `python -m cli.main` (two terminals) |
| `langgraph-plumberbot-hugging-04` | HF Spaces Docker, Gradio UI, `SqliteSaver` checkpoint | `python app.py` |
| `langgraph-plumberbot-multiagent-05` | `create_react_agent`, supervisor + 3 subagents, `InjectedState`, SQLite business DB, RAG | `python cli.py` or `python app.py` |

## Shared patterns across all projects

- **`PlumberState` TypedDict** flows through every graph node
- **`interrupt()` + `Command(resume=...)`** is the HITL mechanism — identical in all projects
- **`thread_id`** ties checkpoint state to a conversation; always passed in `config["configurable"]`
- **Claude model** default is `claude-sonnet-4-6`, overridable via `ANTHROPIC_MODEL` env var
- **`.env` / `.env.example`** pattern — never commit real keys

## Deploying a project to Hugging Face Spaces

Each project with a `Dockerfile` can be pushed as a Space using `git subtree`:

```bash
# One-time: add the HF Space as a remote
git remote add space https://huggingface.co/spaces/<username>/<space-name>

# Push just the subfolder (its contents become the Space root)
git subtree push --prefix langgraph-plumberbot-<name>-<n> space main

# Future updates
git push origin main
git subtree push --prefix langgraph-plumberbot-<name>-<n> space main
```

## Running tests

Each project has a `tests/` directory. From inside the project folder:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt   # or: pip install -e ".[dev]" for langsmith-03
python -m pytest tests/ -v
```

## API keys summary

| Project | `ANTHROPIC_API_KEY` | `OPENAI_API_KEY` |
|---|---|---|
| bare-01 | Not needed | Not needed |
| withllm-02 | Required | Not needed |
| langsmith-03 | Required | Not needed |
| hugging-04 | Required | Not needed |
| multiagent-05 | Required | Optional (upgrades RAG from BM25 → vector search) |
