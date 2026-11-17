from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app

INTRO = (
    "My name is Maya. I am a software engineer with three years of experience. "
    "I want to transition into AI engineering within six months. "
    "I can study five hours per week."
)
EXPECTED_INTRO = {
    "identity.name": "Maya",
    "career.current_role": "Software Engineer",
    "career.experience_years": "3 years",
    "goals.career_target": "AI Engineering",
    "goals.career_timeline": "6 months",
    "commitments.study_hours_week": "5 hours/week",
}
PROVIDER_ENV = (
    "AIAND_API_KEY",
    "AIAND_BASE_URL",
    "AIAND_MODEL",
    "BACKUP_API_KEY",
    "BACKUP_URL",
    "BACKUP_BASE_URL",
    "BACKUP_MODEL",
)


@pytest.fixture()
def client(tmp_path, monkeypatch):
    for key in PROVIDER_ENV:
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("MEMORA_DB_PATH", str(tmp_path / "api-test.db"))
    with TestClient(create_app()) as test_client:
        yield test_client


def save_intro(client: TestClient) -> dict:
    response = client.post("/agent/chat", json={"session_id": "agent-a", "message": INTRO})
    assert response.status_code == 200
    return response.json()


def test_health_and_seeded_agents(client: TestClient):
    health = client.get("/health").json()
    assert health["status"] == "ok"
    assert health["provider"]["status"] == "standby"
    assert health["provider"]["configured"] is False
    assert health["memory"] == {"status": "online", "backend": "SQLite"}
    assert health["retrieval"] == {"status": "operational", "requires_llm": False}
    assert health["counts"]["agents"] == 2

    sessions = client.get("/agent/sessions").json()["sessions"]
    assert [session["id"] for session in sessions] == ["agent-a", "agent-b"]
    memories = client.get("/memory/list", params={"include_demo": False}).json()
    assert memories["total"] == 0
    demos = client.get("/memory/list", params={"include_demo": True}).json()
    assert demos["total"] == 3
    assert all(memory["is_demo"] for memory in demos["memories"])


def test_save_search_edit_export_and_delete(client: TestClient):
    payload = {
        "content": "Prefers SQLite for local-first prototypes",
        "category": "preferences",
        "owner_id": "user",
        "memory_key": "preferences.database",
        "metadata": {"priority": "high"},
    }
    saved_response = client.post("/memory/save", json=payload)
    assert saved_response.status_code == 200
    saved = saved_response.json()
    assert saved["status"] == "active"
    assert saved["conflict_status"] == "none"
    assert saved["metadata"] == {"priority": "high"}
    assert saved["is_demo"] is False
    assert saved["created_at"].endswith("Z")

    duplicate = client.post("/memory/save", json=payload).json()
    assert duplicate["id"] == saved["id"]
    assert client.get("/memory/list", params={"include_demo": False}).json()["total"] == 1

    found = client.get(
        "/memory/list",
        params={"query": "sqlite", "category": "preferences", "include_demo": False},
    ).json()
    assert found["total"] == 1
    assert found["memories"][0]["id"] == saved["id"]

    updated_response = client.put(
        f"/memory/{saved['id']}",
        json={"content": "Uses PostgreSQL for shared environments", "metadata": {"reviewed": True}},
    )
    assert updated_response.status_code == 200
    updated = updated_response.json()
    assert updated["content"] == "Uses PostgreSQL for shared environments"
    assert updated["metadata"] == {"reviewed": True}
    assert updated["updated_at"] >= saved["updated_at"]
    assert client.get("/memory/list", params={"query": "sqlite"}).json()["total"] == 0

    export_response = client.get("/memory/export", params={"owner_id": "user"})
    assert export_response.status_code == 200
    assert export_response.headers["content-disposition"].startswith("attachment;")
    exported = export_response.json()
    assert exported["owner_id"] == "user"
    assert exported["memory_count"] == len(exported["memories"])
    assert any(memory["id"] == saved["id"] for memory in exported["memories"])

    assert client.delete(f"/memory/{saved['id']}").json() == {
        "deleted": True,
        "id": saved["id"],
    }
    assert client.delete(f"/memory/{saved['id']}").status_code == 404


def test_exact_intro_agent_a_and_agent_b_learning_plan(client: TestClient):
    chat = save_intro(client)
    assert chat["provider_used"] == "local"
    assert chat["model_invoked"] is False
    assert chat["message"] == INTRO
    saved_by_key = {memory["memory_key"]: memory["content"] for memory in chat["memories_saved"]}
    assert saved_by_key == EXPECTED_INTRO
    assert all(memory["source_agent"] == "agent-a" for memory in chat["memories_saved"])

    agent_a_messages = client.get("/agent/sessions/agent-a/messages").json()["messages"]
    assert [message["role"] for message in agent_a_messages] == ["user", "assistant"]
    assert agent_a_messages[0]["content"] == INTRO
    assert client.get("/agent/sessions/agent-b/messages").json()["messages"] == []

    retrieval = client.post(
        "/memory/retrieve",
        json={"query": "Create a learning plan for me", "owner_id": "user", "limit": 10},
    ).json()
    assert retrieval["model_invoked"] is False
    retrieved_keys = {memory["memory_key"] for memory in retrieval["memories"]}
    assert set(EXPECTED_INTRO).issubset(retrieved_keys)
    assert all(memory["score"] > 0 and memory["reason"] for memory in retrieval["memories"])

    goal_retrieval = client.post(
        "/memory/retrieve", json={"query": "What is my career goal?", "owner_id": "user"}
    ).json()
    goal_contents = {memory["memory_key"]: memory["content"] for memory in goal_retrieval["memories"]}
    assert goal_contents["goals.career_target"] == "AI Engineering"
    assert goal_contents["goals.career_timeline"] == "6 months"

    agent_b = client.post(
        "/agent/chat",
        json={"session_id": "agent-b", "message": "Create a learning plan for me"},
    ).json()
    assert agent_b["model_invoked"] is False
    assert {memory["memory_key"] for memory in agent_b["memories_retrieved"]} >= set(EXPECTED_INTRO)
    for value in ("Maya", "Software Engineer", "3 years", "AI Engineering", "6 months", "5 hours/week"):
        assert value in agent_b["response"]
    assert "Months 1–2" in agent_b["response"]
    assert "Months 3–4" in agent_b["response"]
    assert "Months 5–6" in agent_b["response"]

    assert len(client.get("/agent/sessions/agent-a/messages").json()["messages"]) == 2
    agent_b_messages = client.get("/agent/sessions/agent-b/messages").json()["messages"]
    assert [message["role"] for message in agent_b_messages] == ["user", "assistant"]
    assert agent_b_messages[0]["content"] == "Create a learning plan for me"


def test_repeated_intro_is_deduplicated_and_not_reported_as_new(client: TestClient):
    first = save_intro(client)
    assert len(first["memories_saved"]) == 6

    repeated = save_intro(client)
    assert repeated["memories_saved"] == []
    assert next(step for step in repeated["trace"] if step["step"] == "memory_write")["status"] == "skipped"
    memories = client.get("/memory/list", params={"include_demo": False}).json()
    assert memories["total"] == 6
    assert len(client.get("/agent/sessions/agent-a/messages").json()["messages"]) == 4


def test_conflicts_are_explicit_and_make_current_supersedes_other(client: TestClient):
    first = client.post(
        "/memory/save",
        json={
            "content": "AI Engineering",
            "category": "goals",
            "memory_key": "goals.career_target",
        },
    ).json()
    duplicate = client.post(
        "/memory/save",
        json={
            "content": "AI Engineering",
            "category": "goals",
            "memory_key": "goals.career_target",
        },
    ).json()
    assert duplicate["id"] == first["id"]

    second = client.post(
        "/memory/save",
        json={
            "content": "Data Engineering",
            "category": "goals",
            "memory_key": "goals.career_target",
        },
    ).json()
    assert second["conflict_status"] == "pending"
    assert second["conflict_with"] == first["id"]
    all_memories = client.get("/memory/list", params={"include_demo": False}).json()["memories"]
    by_id = {memory["id"]: memory for memory in all_memories}
    assert by_id[first["id"]]["conflict_status"] == "pending"
    assert by_id[first["id"]]["conflict_with"] == second["id"]
    assert client.get("/health").json()["counts"]["conflicts"] == 2

    resolved = client.post(
        f"/memory/{second['id']}/resolve", json={"action": "make_current"}
    ).json()
    assert resolved["status"] == "active"
    assert resolved["conflict_status"] == "none"
    assert resolved["conflict_with"] is None
    old = client.get("/memory/list", params={"status": "superseded"}).json()["memories"]
    assert len(old) == 1
    assert old[0]["id"] == first["id"]
    assert old[0]["superseded_by"] == second["id"]
    assert client.get("/health").json()["counts"]["conflicts"] == 0

    retrieved = client.post(
        "/memory/retrieve", json={"query": "What is my career goal?"}
    ).json()["memories"]
    assert retrieved[0]["content"] == "Data Engineering"


def test_outage_preserves_sqlite_retrieval_and_blocks_primary(tmp_path, monkeypatch):
    for key in PROVIDER_ENV:
        monkeypatch.setenv(key, "")
    monkeypatch.setenv("MEMORA_DB_PATH", str(tmp_path / "outage-test.db"))
    monkeypatch.setenv("AIAND_API_KEY", "test-key")
    monkeypatch.setenv("AIAND_BASE_URL", "https://provider.invalid/v1")
    monkeypatch.setenv("AIAND_MODEL", "test-model")

    async def fail_if_primary_is_called(*args, **kwargs):
        raise AssertionError("A simulated outage must not invoke the primary provider")

    monkeypatch.setattr("backend.app.call_chat_completions", fail_if_primary_is_called)
    with TestClient(create_app()) as client:
        for content, category, key in (
            ("Maya", "personal", "identity.name"),
            ("AI Engineering", "goals", "goals.career_target"),
            ("6 months", "goals", "goals.career_timeline"),
            ("5 hours/week", "commitments", "commitments.study_hours_week"),
        ):
            assert client.post(
                "/memory/save",
                json={"content": content, "category": category, "memory_key": key},
            ).status_code == 200

        outage = client.post("/system/simulate-outage").json()
        assert outage["provider"]["status"] == "offline"
        assert outage["provider"]["outage_simulated"] is True

        retrieval = client.post(
            "/memory/retrieve", json={"query": "Create a learning plan for me"}
        ).json()
        assert retrieval["model_invoked"] is False
        assert {memory["memory_key"] for memory in retrieval["memories"]} >= {
            "goals.career_target",
            "goals.career_timeline",
            "commitments.study_hours_week",
        }

        chat = client.post(
            "/agent/chat",
            json={"session_id": "agent-b", "message": "What is my career goal?"},
        ).json()
        assert chat["provider_used"] == "memory-only"
        assert chat["model_invoked"] is False
        assert "AI Engineering" in chat["response"]
        assert "No model was invoked" in chat["response"]
        assert next(step for step in chat["trace"] if step["step"] == "primary")["status"] == "offline"
        assert client.post("/memory/save", json={"content": "Likes tea", "category": "preferences"}).status_code == 200

        restored = client.post("/system/restore-provider").json()
        assert restored["provider"]["outage_simulated"] is False
        assert restored["provider"]["status"] == "online"
        assert restored["provider"]["last_error"] is None

        events = client.get("/system/events", params={"limit": 50}).json()["events"]
        assert events == sorted(events, key=lambda event: event["id"], reverse=True)
        event_types = {event["event_type"] for event in events}
        assert {"outage_simulated", "provider_restored", "memory_retrieved"}.issubset(event_types)
        assert all(event["timestamp"].endswith("Z") for event in events)


def test_questions_and_temporary_statements_do_not_create_memories(client: TestClient):
    first = client.post(
        "/agent/chat", json={"session_id": "agent-a", "message": "What should I do today?"}
    )
    assert first.status_code == 200
    assert first.json()["memories_saved"] == []
    second = client.post(
        "/agent/chat", json={"session_id": "agent-a", "message": "I am feeling tired right now"}
    )
    assert second.status_code == 200
    assert second.json()["memories_saved"] == []


def test_custom_session_and_independent_history(client: TestClient):
    created = client.post(
        "/agent/sessions",
        json={"name": "Research helper", "role": "research", "description": "A third history"},
    ).json()
    assert created["name"] == "Research helper"
    assert client.post("/agent/chat", json={"session_id": created["id"], "message": "I prefer short answers"}).status_code == 200
    assert len(client.get(f"/agent/sessions/{created['id']}/messages").json()["messages"]) == 2
    assert client.get("/agent/sessions/agent-a/messages").json()["messages"] == []
    assert client.get("/agent/sessions/agent-b/messages").json()["messages"] == []
