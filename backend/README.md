# Memora backend

Local-first FastAPI + SQLite service. It creates the database on startup, enables foreign keys, seeds two independent agent sessions, and seeds three `is_demo` memories only into an empty memory table. Agent retrieval excludes demo records by default.

## Run

From the repository root:

```bash
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements.txt
.venv/bin/uvicorn backend.main:app --reload --port 8000
```

The frontend can proxy `/api` to `http://localhost:8000`. API docs are available at `/docs`. Copy `backend/.env.example` to `backend/.env` to configure an OpenAI-compatible provider; no provider is required for local mode.

## Test

```bash
.venv/bin/pytest backend/tests -q
```

Tests use isolated temporary SQLite files and never contact external providers.
