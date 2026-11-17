from __future__ import annotations

import re
from typing import Any

TOKEN_RE = re.compile(r"[a-z0-9]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "can",
    "could",
    "create",
    "do",
    "for",
    "from",
    "i",
    "in",
    "is",
    "me",
    "my",
    "of",
    "please",
    "tell",
    "the",
    "to",
    "was",
    "what",
    "when",
    "where",
    "who",
    "why",
    "you",
}
SYNONYMS = {
    "goal": "target",
    "goals": "target",
    "aspiration": "target",
    "ambition": "target",
    "job": "role",
    "position": "role",
    "occupation": "role",
    "timeline": "timeframe",
    "deadline": "timeframe",
    "availability": "hours",
    "available": "hours",
    "study": "study",
    "studying": "study",
    "learning": "learn",
    "engineer": "engineering",
}
LEARNING_PLAN_AFFINITY = {
    "goals.career_target": 100,
    "goals.career_timeline": 95,
    "commitments.study_hours_week": 90,
    "career.current_role": 85,
    "career.experience_years": 80,
    "identity.name": 75,
}
CAREER_GOAL_AFFINITY = {
    "goals.career_target": 100,
    "goals.career_timeline": 90,
    "career.current_role": 75,
    "career.experience_years": 65,
}


def tokens(text: str, remove_stop_words: bool = True) -> set[str]:
    values = TOKEN_RE.findall(text.lower())
    if remove_stop_words:
        values = [value for value in values if value not in STOP_WORDS]
    return {SYNONYMS.get(value, value) for value in values}


def is_learning_plan_query(query: str) -> bool:
    normalized = " ".join(TOKEN_RE.findall(query.lower()))
    return bool(
        (re.search(r"\b(learn|learning|study|studying)\b", normalized))
        and re.search(r"\b(plan|roadmap|schedule|curriculum)\b", normalized)
    )


def is_career_goal_query(query: str) -> bool:
    query_tokens = tokens(query)
    return "career" in query_tokens and "target" in query_tokens


def rank_memories(
    query: str, memories: list[dict[str, Any]], limit: int
) -> list[dict[str, Any]]:
    """Deterministic lexical ranking with transparent, scenario-relevant intent expansion."""

    query_tokens = tokens(query)
    raw_query = query.lower().strip()
    learning_plan = is_learning_plan_query(query)
    career_goal = is_career_goal_query(query)
    general_context = bool(
        re.search(r"\b(?:know|remember|recall)\b.*\b(?:about me|my context|my memories)\b", raw_query)
        or re.search(r"\bwhat do you know about me\b", raw_query)
        or re.search(r"\b(?:show|list|retrieve)\b.*\b(?:memories|memory|context)\b", raw_query)
    )
    ranked: list[dict[str, Any]] = []

    for memory in memories:
        memory_key = memory.get("memory_key") or ""
        category = memory["category"]
        content = memory["content"]
        content_tokens = tokens(content)
        key_tokens = tokens(memory_key.replace(".", " ").replace("_", " "))
        category_tokens = tokens(category)
        memory_tokens = content_tokens | key_tokens | category_tokens
        overlap = query_tokens & memory_tokens
        score = float(len(overlap) * 5 + len(query_tokens & key_tokens) * 2)
        reasons: list[str] = []

        if overlap:
            reasons.append("matched " + ", ".join(sorted(overlap)))
        if raw_query and raw_query in content.lower():
            score += 12
            reasons.append("contains the exact query")
        if category in query.lower():
            score += 3
            if category not in reasons:
                reasons.append(f"matched the {category} category")

        affinity = 0
        if learning_plan:
            affinity = LEARNING_PLAN_AFFINITY.get(memory_key, 0)
            if affinity:
                reasons = [f"learning-plan intent uses {memory_key}"]
        elif career_goal:
            affinity = CAREER_GOAL_AFFINITY.get(memory_key, 0)
            if affinity:
                reasons = [f"career-goal intent uses {memory_key}"]
        score += affinity
        if general_context:
            score += 10
            reasons = ["general context request includes this active memory"]

        if score <= 0:
            continue
        scored = dict(memory)
        scored["score"] = round(score, 3)
        scored["reason"] = "; ".join(reasons) or "Deterministic keyword and category match"
        ranked.append(scored)

    ranked.sort(key=lambda item: (-item["score"], item["created_at"], item["id"]))
    return ranked[:limit]
