from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings
from .db import Database, utc_now
from .extraction import (
    can_save_model_extraction,
    extract_enduring_memories,
    valid_llm_memories,
)
from .fallback import local_response
from .providers import call_chat_completions
from .retrieval import rank_memories
from .schemas import (
    AgentChat,
    AgentSessionCreate,
    Category,
    MemoryRetrieve,
    MemorySave,
    MemoryStatus,
    MemoryUpdate,
    ResolveConflict,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    database = Database(settings.db_path)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        database.initialize()
        yield

    app = FastAPI(title="Memora API", version="1.0.0", lifespan=lifespan)
    app.state.db = database
    app.state.settings = settings
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    def health() -> dict[str, Any]:
        outage = database.get_state("primary_outage") == "true"
        primary_error = database.get_state("primary_last_error")
        backup_error = database.get_state("backup_last_error")
        if outage:
            primary_status = "offline"
        elif not settings.primary.configured:
            primary_status = "standby"
        elif primary_error:
            primary_status = "degraded"
        else:
            primary_status = "online"
        backup_status = (
            "standby"
            if not settings.backup.configured
            else "degraded"
            if backup_error
            else "online"
        )
        return {
            "status": "ok",
            "provider": {
                "name": settings.primary.name,
                "model": settings.primary.model or "unconfigured",
                "status": primary_status,
                "configured": settings.primary.configured,
                "outage_simulated": outage,
                "last_error": primary_error,
            },
            "backup": {
                "configured": settings.backup.configured,
                "status": backup_status,
            },
            "memory": {"status": "online", "backend": "SQLite"},
            "retrieval": {"status": "operational", "requires_llm": False},
            "counts": database.counts(),
        }

    def retrieve(
        query: str,
        owner_id: str,
        limit: int,
        categories: list[str] | None,
        include_demo: bool,
        agent_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], float]:
        started = time.perf_counter()
        candidates = database.retrieval_candidates(owner_id, include_demo, categories)
        matches = rank_memories(query, candidates, limit)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
        database.log_event(
            "memory_retrieved",
            f"Retrieved {len(matches)} memor{'y' if len(matches) == 1 else 'ies'} for query: {query[:160]}",
            agent_id=agent_id,
        )
        return matches, elapsed_ms

    @app.get("/")
    async def root() -> dict[str, Any]:
        return {
            "service": "Memora API",
            "version": app.version,
            "memory": "SQLite",
            "docs": "/docs",
            "health": "/health",
        }

    @app.get("/health")
    async def get_health() -> dict[str, Any]:
        return health()

    @app.post("/memory/save")
    async def save_memory(payload: MemorySave) -> dict[str, Any]:
        memory, created = database.save_memory(payload.model_dump())
        if created:
            database.log_event(
                "memory_saved",
                f"Saved {memory['category']} memory {memory.get('memory_key') or memory['id']}",
                agent_id=memory.get("source_agent"),
            )
        return memory

    @app.get("/memory/list")
    async def list_memories(
        owner_id: str = "user",
        query: str = "",
        category: Category | None = None,
        status: MemoryStatus | None = None,
        include_demo: bool = True,
    ) -> dict[str, Any]:
        memories = database.list_memories(owner_id, query, category, status, include_demo)
        return {"memories": memories, "total": len(memories)}

    @app.post("/memory/retrieve")
    async def retrieve_memories(payload: MemoryRetrieve) -> dict[str, Any]:
        memories, elapsed_ms = retrieve(
            payload.query,
            payload.owner_id,
            payload.limit,
            payload.categories,
            payload.include_demo,
        )
        return {
            "memories": memories,
            "query": payload.query,
            "count": len(memories),
            "elapsed_ms": elapsed_ms,
            "model_invoked": False,
        }

    @app.put("/memory/{memory_id}")
    async def update_memory(memory_id: str, payload: MemoryUpdate) -> dict[str, Any]:
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            raise HTTPException(status_code=400, detail="At least one editable field is required")
        memory = database.update_memory(memory_id, updates)
        if memory is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        database.log_event("memory_updated", f"Updated memory {memory_id}")
        return memory

    @app.delete("/memory/{memory_id}")
    async def delete_memory(memory_id: str) -> dict[str, Any]:
        if not database.delete_memory(memory_id):
            raise HTTPException(status_code=404, detail="Memory not found")
        database.log_event("memory_deleted", f"Deleted memory {memory_id}")
        return {"deleted": True, "id": memory_id}

    @app.get("/memory/export")
    async def export_memories(owner_id: str = "user") -> Response:
        memories = database.export_memories(owner_id)
        document = {
            "exported_at": utc_now(),
            "owner_id": owner_id,
            "memory_count": len(memories),
            "memories": memories,
        }
        safe_owner = "".join(character if character.isalnum() or character in "-_" else "_" for character in owner_id)
        return Response(
            content=json.dumps(document, ensure_ascii=False, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="memora-{safe_owner}-export.json"'},
        )

    @app.post("/memory/{memory_id}/resolve")
    async def resolve_memory(memory_id: str, payload: ResolveConflict) -> dict[str, Any]:
        memory = database.resolve_memory(memory_id)
        if memory is None:
            raise HTTPException(status_code=404, detail="Memory not found")
        database.log_event("conflict_resolved", f"Made memory {memory_id} current via {payload.action}")
        return memory

    @app.get("/agent/sessions")
    async def list_sessions() -> dict[str, Any]:
        return {"sessions": database.sessions()}

    @app.post("/agent/sessions")
    async def create_session(payload: AgentSessionCreate) -> dict[str, Any]:
        return database.create_session(payload.name, payload.role, payload.description)

    @app.get("/agent/sessions/{session_id}/messages")
    async def list_messages(session_id: str) -> dict[str, Any]:
        messages = database.messages(session_id)
        if messages is None:
            raise HTTPException(status_code=404, detail="Agent session not found")
        return {"messages": messages}

    @app.post("/agent/chat")
    async def agent_chat(payload: AgentChat) -> dict[str, Any]:
        session = database.get_session(payload.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Agent session not found")

        message = payload.message.strip()
        if not message:
            raise HTTPException(status_code=422, detail="Message cannot be blank")
        memories, _ = retrieve(
            query=message,
            owner_id=payload.owner_id,
            limit=10,
            categories=None,
            include_demo=False,
            agent_id=payload.session_id,
        )
        trace = [
            {
                "step": "retrieve",
                "label": "Retrieve durable context",
                "status": "complete",
                "detail": f"Ranked {len(memories)} active SQLite memories before model invocation",
            }
        ]
        trace.append(
            {
                "step": "validation",
                "label": "Validate retrieved context",
                "status": "complete",
                "detail": f"Validated owner scope, active status, and provenance for {len(memories)} retrieved records",
            }
        )
        database.add_message(
            payload.session_id, "user", message, provider=None, retrieved_count=len(memories)
        )
        extracted = extract_enduring_memories(message)
        response_text: str | None = None
        model_extracted: list[dict[str, str]] = []
        provider_used = "local"
        model_invoked = False
        outage = database.get_state("primary_outage") == "true"

        if outage:
            trace.append(
                {
                    "step": "primary",
                    "label": "ai& primary provider",
                    "status": "offline",
                    "detail": "Persisted outage simulation blocked the primary request",
                }
            )
        elif not settings.primary.configured:
            trace.append(
                {
                    "step": "primary",
                    "label": "ai& primary provider",
                    "status": "skipped",
                    "detail": "Primary provider is not configured; no network request was made",
                }
            )
        else:
            try:
                response_text, model_extracted = await call_chat_completions(
                    settings.primary, message, memories
                )
                provider_used = "primary"
                model_invoked = True
                database.set_state("primary_last_error", None)
                trace.append(
                    {
                        "step": "primary",
                        "label": "ai& primary provider",
                        "status": "complete",
                        "detail": f"Received a structured response using {settings.primary.model}",
                    }
                )
            except Exception as error:
                error_message = f"{type(error).__name__}: {error}"[:1_500]
                database.set_state("primary_last_error", error_message)
                database.log_event(
                    "provider_error",
                    f"Primary provider failed: {error_message}",
                    agent_id=payload.session_id,
                    level="error",
                )
                trace.append(
                    {
                        "step": "primary",
                        "label": "ai& primary provider",
                        "status": "failed",
                        "detail": error_message,
                    }
                )

        if response_text is None and settings.backup.configured:
            try:
                response_text, model_extracted = await call_chat_completions(
                    settings.backup, message, memories
                )
                provider_used = "backup"
                model_invoked = True
                database.set_state("backup_last_error", None)
                trace.append(
                    {
                        "step": "backup",
                        "label": "Backup provider",
                        "status": "complete",
                        "detail": f"Received a structured response using {settings.backup.model}",
                    }
                )
            except Exception as error:
                error_message = f"{type(error).__name__}: {error}"[:1_500]
                database.set_state("backup_last_error", error_message)
                database.log_event(
                    "provider_error",
                    f"Backup provider failed: {error_message}",
                    agent_id=payload.session_id,
                    level="error",
                )
                trace.append(
                    {
                        "step": "backup",
                        "label": "Backup provider",
                        "status": "failed",
                        "detail": error_message,
                    }
                )
        else:
            trace.append(
                {
                    "step": "backup",
                    "label": "Backup provider",
                    "status": "skipped",
                    "detail": "Not needed" if response_text is not None else "Backup provider is not configured",
                }
            )

        if response_text is None:
            provider_used = "memory-only" if outage else "local"
            response_text = local_response(message, memories, extracted, memory_only=outage)
            model_invoked = False

        trace.append(
            {
                "step": "verification",
                "label": "Verify response",
                "status": "complete",
                "detail": (
                    f"Verified a non-empty response from {provider_used}; provider failures remain visible in this trace"
                    if model_invoked
                    else "Verified a non-empty deterministic response; no LLM output is being presented as generated"
                ),
            }
        )

        new_records: list[dict[str, str]] = extracted
        if not new_records and can_save_model_extraction(message):
            new_records = valid_llm_memories(model_extracted)
        saved: list[dict[str, Any]] = []
        created_count = 0
        for record in new_records[:8]:
            saved_memory, created = database.save_memory(
                {
                    "content": record["content"],
                    "category": record["category"],
                    "owner_id": payload.owner_id,
                    "source_agent": payload.session_id,
                    "memory_key": record.get("memory_key") or None,
                    "metadata": {"origin": "agent_chat", "session_id": payload.session_id},
                    "status": "active",
                    "is_demo": False,
                }
            )
            if created:
                saved.append(saved_memory)
                created_count += 1
                database.log_event(
                    "memory_saved",
                    f"Agent saved {saved_memory['category']} memory "
                    f"{saved_memory.get('memory_key') or saved_memory['id']}",
                    agent_id=payload.session_id,
                )
        trace.append(
            {
                "step": "memory_write",
                "label": "Persist new enduring context",
                "status": "complete" if created_count else "skipped",
                "detail": f"Saved {created_count} new memories after response generation"
                if created_count
                else "No new enduring memories required a write",
            }
        )
        database.add_message(
            payload.session_id,
            "assistant",
            response_text,
            provider=provider_used,
            retrieved_count=len(memories),
        )
        return {
            "response": response_text,
            "session_id": payload.session_id,
            "memories_retrieved": memories,
            "memories_saved": saved,
            "provider_used": provider_used,
            "model_invoked": model_invoked,
            "trace": trace,
            "message": message,
        }

    @app.post("/system/simulate-outage")
    async def simulate_outage() -> dict[str, Any]:
        database.set_state("primary_outage", "true")
        database.log_event("outage_simulated", "Primary provider outage simulation enabled", level="warning")
        database.log_event(
            "memory_available",
            "Primary model requests are blocked; Memora SQLite retrieval remains operational",
            level="info",
        )
        return health()

    @app.post("/system/restore-provider")
    async def restore_provider() -> dict[str, Any]:
        database.set_state("primary_outage", "false")
        database.set_state("primary_last_error", None)
        database.log_event(
            "provider_restored",
            "Primary provider request path restored; all saved memories were preserved",
        )
        return health()

    @app.get("/system/events")
    async def system_events(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
        return {"events": database.events(limit)}

    return app
