# memora.

**Your AI can go offline. Your context shouldn’t.**

Memora is a local-first, user-controlled context continuity layer for AI agents. It separates durable personal context from model providers, application sessions, and conversation history.

Different agents retrieve the same authorized memory. If the primary provider is unavailable, the FastAPI service and SQLite vault continue to serve context without invoking an LLM.

## What is implemented

- **Persistent Memory Vault** — structured SQLite records with category, owner, source, timestamps, lifecycle status, optional memory keys, and metadata.
- **Cross-agent continuity** — Agent A and Agent B have isolated conversation histories and access the same user-owned memory store.
- **Observable agent harness** — retrieval → validation → model/fallback → verification → memory update, with the actual trace shown in the UI.
- **Controlled outage simulation** — a backend-controlled request gate blocks primary model calls without stopping the API or database.
- **LLM-independent retrieval** — deterministic keyword/category ranking returns real records, match reasons, and elapsed query time.
- **User ownership** — create, inspect, search, edit, resolve conflicts, export JSON, and permanently delete memories.
- **Conflict safety** — a different value for an existing memory key is flagged for user review instead of silently overwriting the previous value.
- **Transparent fallback** — no credentials are required for the demo. Local and memory-only responses are explicitly labeled and never presented as LLM output.
- **Event provenance** — real runtime events with timestamps, source agent, type, and severity.

## Architecture

```text
React + Vite UI
      │
      │ REST (/api proxy)
      ▼
FastAPI agent harness
      │
      ├── deterministic context retrieval ──────┐
      │                                          │
      ├── OPTIONAL primary OpenAI-compatible LLM │
      │       ai& Inference configuration        │
      │                                          ▼
      ├── OPTIONAL backup provider          SQLite Memory Vault
      │                                     independent local file
      └── controlled provider request gate       │
                                            save / retrieve / edit
                                            export / delete / resolve
```

The primary provider is optional infrastructure. It is never the owner of the memory database.

## Quick start

### Prerequisites

- Python 3.11+
- Node.js 20+

### 1. Install dependencies

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
npm install
```

### 2. Configure an optional model

```bash
cp .env.example .env
```

Add the exact ai& OpenAI-compatible base URL, API key, and model supplied by your provider. The repository intentionally does not guess an endpoint.

```dotenv
AIAND_API_KEY=your_key
AIAND_BASE_URL=https://your-provider-endpoint/v1
AIAND_MODEL=your_model
```

You can also configure `BACKUP_API_KEY`, `BACKUP_BASE_URL`, and `BACKUP_MODEL` for an independent backup provider.

**No key is needed for the local demonstration.** With credentials absent, health reports `standby` / Local mode and responses use the deterministic local harness.

### 3. Start Memora

Terminal 1 — backend:

```bash
.venv/bin/uvicorn backend.main:app --reload --port 8000
```

Terminal 2 — frontend:

```bash
npm run dev
```

Open **http://localhost:5178**. Interactive API documentation is available at **http://localhost:8000/docs**.

## Winning demo flow

1. Open **Agent Playground → Agent A**.
2. Click the demo introduction:

   > My name is Maya. I am a software engineer with three years of experience. I want to transition into AI engineering within six months. I can study five hours per week.

3. Inspect the actual extracted records and harness trace. The memories are saved after the interaction and marked with Agent A as their source.
4. Switch to **Agent B** and ask **“Create a learning plan for me.”** Agent B retrieves the shared Memora context despite having a separate conversation history.
5. Open **Resilience Console** and click **Simulate Provider Outage**. The primary provider request path is now blocked on the backend.
6. Run **“What is my career goal?”** in the LLM-free retrieval test, or ask Agent B. Memora returns saved records with **0 model calls**.
7. Open **Memory Vault** and inspect or export the records as JSON. Ownership operations still work during the outage.
8. Click **Restore Provider** to reopen the model request path. Existing memories remain intact.

The outage control simulates provider unavailability locally. It does not claim that an external provider actually failed.

## API surface

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Actual provider, memory, retrieval, and agent status |
| `POST` | `/memory/save` | Save structured context |
| `GET` | `/memory/list` | List, search, and filter records |
| `POST` | `/memory/retrieve` | Deterministic relevant-context retrieval |
| `PUT` | `/memory/{id}` | Edit a record |
| `DELETE` | `/memory/{id}` | Permanently delete a record |
| `POST` | `/memory/{id}/resolve` | Explicitly choose the current conflicting version |
| `GET` | `/memory/export` | Download all user-owned records as JSON |
| `POST` | `/agent/chat` | Run the observable context-aware agent harness |
| `GET` | `/agent/sessions` | List connected agents |
| `POST` | `/agent/sessions` | Create another independent session |
| `GET` | `/agent/sessions/{id}/messages` | Read one agent’s isolated history |
| `POST` | `/system/simulate-outage` | Enforce the primary model request gate |
| `POST` | `/system/restore-provider` | Restore the primary request path |
| `GET` | `/system/events` | Read real runtime events |

All memory endpoints remain independent of primary model availability.

## Tests

```bash
.venv/bin/python -m pytest backend/tests -q
npm run build
```

The backend tests use a temporary database and do not contact an external model. They cover memory CRUD/export, the Maya cross-agent flow, outage retrieval, separate histories, conflict resolution, and provider restoration.

## Storage and demo data

- Default database: `backend/data/memora.db`
- Override with `MEMORA_DB_PATH`.
- Two agent sessions are initialized automatically.
- A few initial records are explicitly labeled **DEMO** in the Memory Vault and excluded from normal agent retrieval.
- User chat and memory data persist across browser refreshes and application restarts.

## Deliberate MVP boundaries

This is a localhost hackathon MVP: no authentication, vector database, Neo4j, MCP transport, or production deployment. Retrieval is deterministic and explainable. LLM extraction is used only when a provider is configured and reachable; otherwise the transparent deterministic extractor is used.

**Models generate intelligence. Agents execute tasks. Memora preserves context.**
