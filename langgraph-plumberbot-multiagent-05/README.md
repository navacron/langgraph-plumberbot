---
title: PlumberBot Multi-Agent
emoji: 🔧
colorFrom: indigo
colorTo: blue
sdk: docker
pinned: false
---

# langgraph-plumberbot-multiagent-05

**Multi-agent** extension of the plumberbot series. A supervisor agent routes customer
requests to three specialist sub-agents, each with their own tools and domain focus.
Includes a pre-seeded business SQLite database committed to git and an in-memory
RAG knowledge base over plumbing how-to articles.

Both a CLI (withllm-02 style) and a Gradio web UI (hugging-04 style) are included.

---

## Architecture

```
START
  └── verify_customer ──(no customer_id)──► human_input ──► verify_customer (loop)
              │ (customer verified via phone lookup)
          load_memory  (reads customer_profile table)
              │
          supervisor ──► scheduling_subagent  (appointments, services, plumbers)
              │       ├──► dispatch_subagent   (tickets, emergencies, on-call)
              │       └──► knowledge_subagent  (RAG over plumbing how-to corpus)
          save_memory  (upserts customer_profile table)
              │
             END
```

### What each layer does

| Layer | Pattern | Purpose |
|---|---|---|
| Outer graph | `StateGraph` | Verification, memory, top-level flow |
| Supervisor | `create_react_agent` | Routes requests to the right subagent |
| Subagents | `create_react_agent` | Specialist tools per domain |
| Subagent tools | `@tool` + `InjectedState` | Query SQLite, call vectorstore |
| Knowledge base | `InMemoryVectorStore` | RAG over 5 how-to articles |
| Persistence | `SqliteSaver` | Conversation checkpoints |
| Long-term memory | `customer_profile` table | Preferences survive sessions |

---

## LangGraph concepts demonstrated

| Concept | Where |
|---|---|
| `create_react_agent` | All 4 agents (`agents/`) |
| `InjectedState` | All DB tools — auto-injects `customer_id` from graph state |
| Supervisor → subagent-as-tool | `agents/supervisor.py` — subagents called inside `@tool` |
| Customer verification + HITL | `nodes.py:verify_customer` + `human_input` |
| Long-term memory (SQL) | `nodes.py:load_memory`, `save_memory` + `customer_profile` |
| RAG subagent | `knowledge.py` — `InMemoryVectorStore` + OpenAI embeddings |
| Messages-based state | `Annotated[list[AnyMessage], add_messages]` |
| `InputState` schema | Restricts external callers to `messages` only |
| `SqliteSaver` checkpoint | `app.py` — persists threads across page refreshes |

---

## Database (`db/plumberbot.db`)

Six tables, pre-seeded and committed to git — no setup required:

| Table | Rows | Purpose |
|---|---|---|
| `customers` | 6 | Name, phone, email, address |
| `service_catalog` | 10 | Services with base price and typical hours |
| `plumbers` | 4 | Staff with specialties and on-call flag |
| `appointments` | 6 | Scheduled and completed jobs |
| `tickets` | 5 | Open and resolved service tickets |
| `customer_profile` | 3 | Long-term memory (preferences, history) |

To recreate the database from scratch:
```bash
python db/seed.py
```

---

## Knowledge Base (`docs/`)

Five plumbing how-to articles loaded into an in-memory vector store at startup:

| File | Topics |
|---|---|
| `fix_a_sink.txt` | Leaky faucet, slow drain, P-trap, supply lines |
| `fix_a_toilet.txt` | Running toilet, weak flush, clogs, wax ring |
| `fix_a_water_heater.txt` | No hot water, pilot light, anode rod, flushing |
| `burst_pipe_emergency.txt` | Immediate steps, shut-off location, temporary fixes |
| `drain_cleaning_tips.txt` | DIY methods, what not to pour, maintenance schedule |

Embeddings: `text-embedding-3-small` via OpenAI API (requires `OPENAI_API_KEY`).

---

## Local development

### 1 — Install dependencies

```bash
cd langgraph-plumberbot-multiagent-05
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2 — Configure environment

```bash
cp .env.example .env
# Edit .env and set:
#   ANTHROPIC_API_KEY=sk-ant-...
#   OPENAI_API_KEY=sk-...
```

### 3 — Run the CLI

```bash
python cli.py
```

The database is pre-seeded, so you can start immediately with any customer's phone number.

### 4 — Run the Gradio UI

```bash
python app.py
# Open http://localhost:7860
```

---

## Scenario walkthroughs

### Scenario 1 — Returning customer: scheduling

```
You: My phone is (555) 111-2222. I need to book a drain cleaning.
PlumberBot: Welcome back, Jane Doe! I've verified your account...
            [supervisor → scheduling_subagent]
            → lists available plumbers → suggests Mike Torres or Lisa Chen
            → confirms appointment booked
```

### Scenario 2 — Returning customer: emergency dispatch

```
You: My number is (555) 333-4444. I have a burst pipe, water everywhere!
PlumberBot: Welcome back, Bob Smith!
            [supervisor → dispatch_subagent]
            → creates emergency ticket (priority: emergency)
            → returns on-call plumber: Mike Torres, (555) 200-0001
```

### Scenario 3 — Returning customer: RAG knowledge

```
You: My phone is (555) 111-2222. How do I fix a running toilet?
PlumberBot: Welcome back, Jane Doe!
            [supervisor → knowledge_subagent → search_knowledge_base("running toilet")]
            → returns tips from fix_a_toilet.txt
            → explains flapper replacement, float adjustment
```

### Scenario 4 — Multi-intent

```
You: My number is (555) 333-4444. What are your drain cleaning prices,
     and do I have any open tickets?
PlumberBot: Welcome back, Bob Smith!
            [supervisor → scheduling_subagent + dispatch_subagent (parallel)]
            → Drain Cleaning: $150 (1 hour)
            → 1 open ticket: water heater issue (medium priority)
```

### Scenario 5 — Second conversation (memory in action)

```
You: My phone is (555) 111-2222. Can I book something?
PlumberBot: Welcome back, Jane Doe! Based on your profile, I know you prefer
            morning appointments (8am–12pm)...
```

### Scenario 6 — Unknown customer

```
You: My phone is (555) 000-9999. I need help.
PlumberBot: I wasn't able to find an account with that number. Could you
            double-check it? Alternatively, call us at (555) 123-4567...
```

---

## Running tests

```bash
# DB tool tests (no API key required)
python -m pytest tests/test_tools.py -v

# RAG tests (requires OPENAI_API_KEY)
python -m pytest tests/test_rag.py -v

# All tests
python -m pytest tests/ -v
```

---

## Deploying to Hugging Face Spaces

### Step 1 — Create a Space

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces) → **Create new Space**
2. Settings: **SDK: Docker**, **Template: Blank**

### Step 2 — Add Secrets

In Space settings → **Variables and secrets**:

| Name | Value | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Yes |
| `OPENAI_API_KEY` | `sk-...` | Yes (for RAG embeddings) |
| `ANTHROPIC_MODEL` | `claude-opus-4-8` | No |
| `CHECKPOINT_DB_PATH` | `/data/plumberbot_checkpoints.db` | Only on Pro tier |

### Step 3 — Push the code

```bash
cd /path/to/langgraph-plumberbot   # monorepo root

# One-time: add the HF Space remote
git remote add space https://huggingface.co/spaces/<your-username>/<space-name>

# Push just the multiagent-05 subfolder
git subtree push --prefix langgraph-plumberbot-multiagent-05 space main
```

If rejected (HF auto-created a commit):
```bash
git push space $(git subtree split --prefix langgraph-plumberbot-multiagent-05):main --force
```

### Step 4 — Watch the build

Click **Logs** in the Space UI. Build takes ~3 minutes on first push (OpenAI embeddings are computed at startup, not at build time).

---

## Local Docker test

```bash
docker build -t plumberbot-multi .
docker run -p 7860:7860 \
  -e ANTHROPIC_API_KEY=sk-ant-... \
  -e OPENAI_API_KEY=sk-... \
  plumberbot-multi
# Open http://localhost:7860
```

---

## What changed from hugging-04

| Concern | hugging-04 | multiagent-05 |
|---|---|---|
| Architecture | Single graph, 5 nodes | Outer graph + supervisor + 3 subagents |
| State | `customer_message`, `category`, etc. | `messages`, `customer_id`, `loaded_memory` |
| Agents | No (direct node functions) | `create_react_agent` for each specialist |
| Tools | No | 11 tools across 3 domains |
| DB | None (SQLite for checkpoints only) | Business DB with 6 tables + checkpoint DB |
| Knowledge | None | RAG over 5 articles (`InMemoryVectorStore`) |
| Memory | Thread-level only | Long-term via `customer_profile` table |
| Identity | None | Phone number verification (HITL) |
