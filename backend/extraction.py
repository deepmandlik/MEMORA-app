from __future__ import annotations

import re
from typing import Any

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
}
QUESTION_OR_REQUEST = re.compile(
    r"^\s*(what|why|when|where|who|which|how|can you|could you|would you|"
    r"create|make|generate|write|show|tell me|give me|explain|list|find)\b",
    re.IGNORECASE,
)
TEMPORARY = re.compile(
    r"\b(today|tonight|tomorrow|yesterday|right now|this morning|this evening|"
    r"feeling tired|feeling hungry|at the cafe|at the airport)\b",
    re.IGNORECASE,
)


def _number(value: str) -> int | None:
    value = value.lower()
    if value.isdigit():
        return int(value)
    return NUMBER_WORDS.get(value)


def _human_role(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip().strip("."))
    replacements = {
        "software engineer": "Software Engineer",
        "ai engineer": "AI Engineer",
        "ai engineering": "AI Engineering",
    }
    return replacements.get(value.lower(), value[:1].upper() + value[1:])


def _slug(value: str, limit: int = 64) -> str:
    words = re.findall(r"[a-z0-9]+", value.lower())
    stop = {"a", "an", "and", "i", "my", "the", "to"}
    return "_".join(word for word in words if word not in stop)[:limit].rstrip("_") or "detail"


def _record(content: str, category: str, memory_key: str) -> dict[str, str]:
    return {"content": content, "category": category, "memory_key": memory_key}


def extract_enduring_memories(message: str) -> list[dict[str, str]]:
    """Extract only explicit durable facts; requests, questions and fleeting states are ignored."""

    if "?" in message or QUESTION_OR_REQUEST.match(message) or TEMPORARY.search(message):
        return []

    records: list[dict[str, str]] = []
    seen: set[str] = set()

    def add(content: str, category: str, key: str) -> None:
        if key not in seen:
            seen.add(key)
            records.append(_record(content, category, key))

    name = re.search(
        r"\bmy name is\s+([a-z][a-z'-]*(?:\s+[a-z][a-z'-]*){0,3})",
        message,
        re.IGNORECASE,
    )
    if name:
        clean_name = re.split(r"\s+and\s+", name.group(1), maxsplit=1, flags=re.I)[0]
        clean_name = clean_name.strip(" .,")
        if clean_name:
            add(clean_name.title(), "personal", "identity.name")

    role = re.search(
        r"\b(?:i am|i'm)\s+(?:an?|the)\s+([a-z][a-z /-]*?)"
        r"(?=\s+(?:with|who|and)\b|[.,;]|$)",
        message,
        re.IGNORECASE,
    )
    if role and re.search(r"\b(engineer|developer|designer|manager|student|scientist|analyst)\b", role.group(1), re.I):
        add(_human_role(role.group(1)), "career", "career.current_role")

    experience = re.search(
        r"\b(?:with|have|having)\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
        r"\s+(years?|months?)\s+of\s+experience\b",
        message,
        re.IGNORECASE,
    )
    if experience:
        value = _number(experience.group(1))
        unit = experience.group(2).lower()
        if value is not None:
            unit = unit if value != 1 else unit.rstrip("s")
            add(f"{value} {unit}", "career", "career.experience_years")

    target = re.search(
        r"\b(?:transition|move)\s+into\s+(?:an?\s+)?([a-z][a-z /-]*?)"
        r"(?=\s+within\b|[.,;]|$)",
        message,
        re.IGNORECASE,
    )
    if not target:
        target = re.search(
            r"\b(?:become|be)\s+(?:an?\s+)?([a-z][a-z /-]*?(?:engineer|developer|designer|scientist|manager|analyst))"
            r"(?=\s+within\b|[.,;]|$)",
            message,
            re.IGNORECASE,
        )
    if target:
        add(_human_role(target.group(1)), "goals", "goals.career_target")

    timeline = re.search(
        r"\bwithin\s+(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
        r"\s+(years?|months?|weeks?)\b",
        message,
        re.IGNORECASE,
    )
    if timeline:
        value = _number(timeline.group(1))
        unit = timeline.group(2).lower()
        if value is not None:
            unit = unit if value != 1 else unit.rstrip("s")
            add(f"{value} {unit}", "goals", "goals.career_timeline")

    study = re.search(
        r"\b(?:i can|i'll|i will)\s+study\s+"
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)"
        r"\s+(hours?)\s+(?:per|a|each)\s+week\b",
        message,
        re.IGNORECASE,
    )
    if study:
        value = _number(study.group(1))
        if value is not None:
            unit = "hour" if value == 1 else "hours"
            add(f"{value} {unit}/week", "commitments", "commitments.study_hours_week")

    preference_patterns = [
        r"\bi prefer\s+([^.!?\n;]+)",
        r"\bi really like\s+([^.!?\n;]+)",
        r"\bmy preference is\s+([^.!?\n;]+)",
    ]
    for pattern in preference_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" .,")
            add(value, "preferences", f"preferences.{_slug(value)}")
            break

    decision = re.search(r"\b(?:i|we)\s+(?:have\s+)?decided\s+to\s+([^.!?\n;]+)", message, re.I)
    if decision:
        value = decision.group(1).strip(" .,")
        add(f"Decided to {value}", "decisions", f"decisions.{_slug(value)}")

    project_patterns = [
        r"\b(?:i am|i'm)\s+working on\s+([^.!?\n;]+)",
        r"\b(?:i am|i'm)\s+building\s+([^.!?\n;]+)",
        r"\bmy project is\s+([^.!?\n;]+)",
    ]
    for pattern in project_patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            value = match.group(1).strip(" .,")
            add(value, "projects", f"projects.{_slug(value)}")
            break

    commitment = re.search(r"\b(?:i will|i'll)\s+(?!study\b)([^.!?\n;]+)", message, re.I)
    if commitment:
        value = commitment.group(1).strip(" .,")
        add(value, "commitments", f"commitments.{_slug(value)}")

    return records


def valid_llm_memories(value: Any) -> list[dict[str, str]]:
    """Conservatively validate optional model-extracted records."""

    if not isinstance(value, list):
        return []
    allowed = {
        "personal",
        "career",
        "projects",
        "preferences",
        "goals",
        "decisions",
        "commitments",
        "work",
        "health",
        "finance",
        "family",
    }
    result: list[dict[str, str]] = []
    for item in value[:8]:
        if not isinstance(item, dict):
            continue
        content = item.get("content")
        category = item.get("category", "personal")
        memory_key = item.get("memory_key")
        if not isinstance(content, str) or not content.strip() or category not in allowed:
            continue
        result.append(
            {
                "content": content.strip()[:20_000],
                "category": category,
                "memory_key": memory_key.strip()[:200]
                if isinstance(memory_key, str) and memory_key.strip()
                else "",
            }
        )
    return result


def can_save_model_extraction(message: str) -> bool:
    return not ("?" in message or QUESTION_OR_REQUEST.match(message) or TEMPORARY.search(message))
