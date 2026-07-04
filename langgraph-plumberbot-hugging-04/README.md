---
title: PlumberBot
emoji: 🔧
colorFrom: blue
colorTo: green
sdk: docker
pinned: false
---

# langgraph-plumberbot-hugging-04

The same plumbing service triage bot as [`withllm-02`](../langgraph-plumberbot-withllm-02), now deployed to **Hugging Face Spaces** as a Docker container with a **Gradio web UI** and **SQLite-backed persistence**.

This is the **public web demo** in the series. The graph is called directly from Gradio (no LangGraph Server), making it self-contained in a single Docker container.

---

## Architecture

```
HF Spaces Docker Container (single container, port 7860)
  ├── Gradio web UI  (app.py)
  │     └── graph.invoke() / Command(resume=...) — direct Python calls
  ├── plumberbot/ package  (graph, nodes, state, llm)
  └── SQLite database  (/tmp/plumberbot.db)
         └── SqliteSaver checkpointer — persists within container lifetime
```

**Why not LangGraph Server?**  HF Spaces runs a single Docker container. The LangGraph Server (used in `langsmith-03`) requires separate Postgres + Redis services — incompatible with the free tier. `SqliteSaver` gives us persistence with zero external services.

---

## What changed from withllm-02

| Concern | withllm-02 | hugging-04 |
|---|---|---|
| Checkpointer | `InMemorySaver` (RAM only) | `SqliteSaver` (file-based SQLite) |
| UI | CLI (`input()` blocking) | Gradio chatbot (`gr.State` for sessions) |
| Deployment | Local only | HF Spaces Docker (port 7860) |
| Entry point | `python -m plumberbot.cli` | `python app.py` |
| `graph.py` | Hardcodes `InMemorySaver` | `build_graph(checkpointer=None)` injectable |

---

## LangGraph concepts demonstrated

| Concept | Where |
|---|---|
| `SqliteSaver` checkpointer | `app.py` — `SqliteSaver(_conn)`, injected into `build_graph()` |
| Per-session thread IDs | `app.py` — `uuid.uuid4()` per new conversation, stored in `gr.State` |
| Interrupt detection | `app.py:send_message()` — `"__interrupt__" in result` |
| Interrupt resume | `app.py:send_message()` — `graph.invoke(Command(resume=user_message), config)` |
| Gradio stateful chat | `gr.State({"thread_id": ..., "waiting_for_interrupt": ...})` |

---

## Deploying to Hugging Face Spaces

### Step 1 — Create a Space

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces) and click **Create new Space**
2. Fill in:
   - **Space name**: `plumberbot` (or any name)
   - **License**: MIT
   - **SDK**: **Docker**
   - **Docker template**: **Blank**
   - **Visibility**: Public or Private
3. Click **Create Space**

### Step 2 — Add your API key as a Secret

In your Space settings → **Variables and secrets** → **New secret**:

| Name | Value | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Yes |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | No (default: `claude-sonnet-4-6`) |
| `DB_PATH` | `/data/plumberbot.db` | Only for Pro tier (see Persistence below) |

> Secrets are injected as environment variables at runtime. Never commit your API key.

### Step 3 — Push the code

This project lives in a monorepo. Use `git subtree push` to push **only this
subfolder** to HF Spaces — no cloning, no code duplication. Run from the
monorepo root:

```bash
cd /path/to/langgraph-plumberbot   # monorepo root

# One-time: add the HF Space as a second remote
git remote add space https://huggingface.co/spaces/<your-username>/<space-name>

# Push just the hugging-04 subfolder (its contents become the Space root)
git subtree push --prefix langgraph-plumberbot-hugging-04 space main
```

HF receives `Dockerfile`, `app.py`, `plumberbot/`, etc. at the repo root —
exactly where it expects them. Your GitHub remote (`origin`) is unchanged.

**On future updates**, push to both remotes:

```bash
git push origin main                                                    # GitHub
git subtree push --prefix langgraph-plumberbot-hugging-04 space main   # HF Space
```

### Step 4 — Watch the build

In the Space UI, click the **Logs** tab. You'll see:
1. `Building Docker image...` — pip installs run
2. `Container started` — Gradio launches
3. The Space URL becomes live: `https://<your-username>-<space-name>.hf.space`

Build takes ~2 minutes on first push (subsequent pushes are faster due to layer caching).

### Step 5 — (Optional) Enable Persistent Storage (Pro)

Free tier: SQLite lives in `/tmp` — state survives page refreshes but resets on cold start.

Pro/Enterprise tier:
1. Space settings → **Persistent Storage** → Enable (adds a `/data` volume)
2. Add a secret: `DB_PATH` = `/data/plumberbot.db`
3. Redeploy — conversations now survive container restarts

---

## Local development

```bash
cd langgraph-plumberbot-hugging-04

python -m venv .venv
source .venv/bin/activate     # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY

python app.py
# Open http://localhost:7860
```

---

## Local Docker test

Test the exact Docker image before pushing to HF:

```bash
# Build
docker build -t plumberbot-hf .

# Run (pass your API key)
docker run -p 7860:7860 -e ANTHROPIC_API_KEY=sk-ant-... plumberbot-hf

# Open http://localhost:7860
```

---

## Running tests

```bash
python -m pytest tests/ -v
```

`test_routing.py` tests `route_request` in isolation — no API key, no server needed.

---

## Scenario walkthroughs

### Scenario 1 — General question

Type: `Do you fix water heaters?`

→ Claude classifies as `general` → `answer_faq` node → bot responds with services info. No interrupt.

---

### Scenario 2 — Missing information (round-trip)

Type: `My sink is leaking.`

1. Claude classifies as `missing_info` → `ask_missing_info` → graph **pauses** (interrupt)
2. Bot asks for address, phone, issue description
3. You reply: `Jane Doe, 15 Elm St, (555) 999-1234, slow drip, no flooding`
4. Graph resumes → `save_profile` → Claude extracts structured profile → bot confirms

---

### Scenario 3 — Emergency with dispatcher review

Type: `My basement is flooding from a burst pipe. I am at 22 Oak Street.`

1. Claude classifies as `emergency` → `human_review` → graph **pauses** (interrupt)
2. Bot shows dispatch payload with options: `approve / reject / escalate`
3. You type: `approve`
4. Graph resumes → `create_ticket` → ticket created → bot confirms dispatch

---

## Persistence explained

| Tier | SQLite path | Behaviour |
|---|---|---|
| Free HF Spaces | `/tmp/plumberbot.db` | Persists within container session; resets on cold start |
| Pro HF Spaces + Persistent Storage | `/data/plumberbot.db` | Durable across restarts |
| Local dev | `/tmp/plumberbot.db` (default) | Persists within process; customise via `DB_PATH` env var |

The SQLite file holds all LangGraph checkpoint state — thread history, interrupt payloads, node outputs. Changing `DB_PATH` is the only config needed to upgrade persistence.

---

## Default model

`claude-sonnet-4-6` — override via `ANTHROPIC_MODEL` secret in HF Spaces settings.

---

## Resume bullet

> Deployed a LangGraph HITL plumbing triage bot to Hugging Face Spaces as a Docker container; built a Gradio web UI that manages per-session thread IDs via `gr.State`, detects graph interrupts inline, and resumes with user input — demonstrating interrupt/resume without a LangGraph Server, using `SqliteSaver` for file-based persistence.
