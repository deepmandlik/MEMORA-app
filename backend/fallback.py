from __future__ import annotations

import re
from typing import Any

from .retrieval import is_career_goal_query, is_learning_plan_query


def _by_key(records: list[dict[str, Any]]) -> dict[str, str]:
    values: dict[str, str] = {}
    for record in records:
        key = record.get("memory_key")
        if key and key not in values:
            values[key] = record["content"]
    return values


def _phase_ranges(timeline: str | None) -> list[str]:
    match = re.search(r"\b(\d+)\s+months?\b", timeline or "", re.IGNORECASE)
    if not match:
        return ["Phase 1", "Phase 2", "Phase 3"]
    count = int(match.group(1))
    if count == 1:
        return ["Early month 1", "Mid-month 1", "Late month 1"]
    if count == 2:
        return ["Month 1", "Months 1–2", "Month 2"]
    first_end = max(1, round(count / 3))
    second_end = max(first_end + 1, round(2 * count / 3))
    second_end = min(second_end, count - 1)
    return [
        f"Months 1–{first_end}",
        f"Months {first_end + 1}–{second_end}",
        f"Months {second_end + 1}–{count}",
    ]


def learning_plan(records: list[dict[str, Any]], disclosure: str) -> str:
    values = _by_key(records)
    name = values.get("identity.name")
    target = values.get("goals.career_target", "your target role")
    timeline = values.get("goals.career_timeline", "your chosen timeline")
    study = values.get("commitments.study_hours_week", "your available weekly study time")
    role = values.get("career.current_role")
    experience = values.get("career.experience_years")
    phases = _phase_ranges(values.get("goals.career_timeline"))

    greeting = f"{name}, here" if name else "Here"
    starting_point = ""
    if role and experience:
        starting_point = f"\n**Starting point:** {role} with {experience} of experience."
    elif role or experience:
        starting_point = f"\n**Starting point:** {role or experience}."
    lines = [
        f"{greeting} is a personalized path toward **{target}**, using your **{timeline}** "
        f"timeline and **{study}** commitment."
        + starting_point,
        f"**Weekly rhythm:** Protect {study} for focused study, hands-on practice, and a short review "
        "of what to carry into the next week.",
        f"**{phases[0]} — Foundations:** Close the core knowledge gaps for {target}; take notes and "
        "complete small exercises.",
        f"**{phases[1]} — Applied work:** Build one focused project, document trade-offs, and use your "
        "current experience to make the work practical.",
        f"**{phases[2]} — Proof and transition:** Finish a portfolio-ready project, rehearse explaining "
        f"it, and map your progress toward {target}.",
    ]
    missing = []
    if "goals.career_target" not in values:
        missing.append("target role")
    if "goals.career_timeline" not in values:
        missing.append("timeline")
    if "commitments.study_hours_week" not in values:
        missing.append("weekly availability")
    if missing:
        lines.append("To personalize this further, save your " + ", ".join(missing) + ".")
    lines.append(disclosure)
    return "\n\n".join(lines)


def local_response(
    message: str,
    memories: list[dict[str, Any]],
    extracted: list[dict[str, Any]],
    memory_only: bool,
) -> str:
    disclosure = (
        "The primary model is offline. No model was invoked; this answer uses retrieved SQLite "
        "memories and deterministic local logic."
        if memory_only
        else "No model was invoked; this answer was generated locally from the available context."
    )
    if is_learning_plan_query(message):
        return learning_plan(memories, disclosure)

    values = _by_key(memories)
    extracted_values = _by_key(extracted)
    lowered = message.lower()

    if is_career_goal_query(message) or ("career" in lowered and "goal" in lowered):
        target = values.get("goals.career_target")
        timeline = values.get("goals.career_timeline")
        if target:
            answer = f"Your career goal is **{target}**."
            if timeline:
                answer += f" Your saved timeline is **{timeline}**."
            return answer + "\n\n" + disclosure

    if "my name" in lowered and values.get("identity.name"):
        return f"Your name is **{values['identity.name']}**.\n\n{disclosure}"
    if ("study" in lowered or "available" in lowered) and values.get("commitments.study_hours_week"):
        return (
            f"Your saved study commitment is **{values['commitments.study_hours_week']}**."
            f"\n\n{disclosure}"
        )

    if extracted:
        name = extracted_values.get("identity.name")
        target = extracted_values.get("goals.career_target")
        timeline = extracted_values.get("goals.career_timeline")
        study = extracted_values.get("commitments.study_hours_week")
        greeting = f"Thanks, {name}. " if name else "Thanks. "
        details = []
        if target:
            details.append(f"your goal of {target}")
        if timeline:
            details.append(f"your {timeline} timeline")
        if study:
            details.append(f"your availability of {study}")
        suffix = f" I’ve captured {', '.join(details)} as separate durable memories." if details else " I’ve captured the durable details."
        return greeting + "I’ll use that context in future conversations." + suffix + "\n\n" + disclosure

    if memories:
        lines = [
            f"- **{memory.get('memory_key') or memory['category']}:** {memory['content']}"
            for memory in memories[:6]
        ]
        return "Here’s what I found in your saved context:\n" + "\n".join(lines) + "\n\n" + disclosure

    return (
        "I don’t have enough saved context to answer that yet. Share an enduring goal, preference, "
        "project, or commitment, and I can use it in future conversations.\n\n"
        + disclosure
    )
