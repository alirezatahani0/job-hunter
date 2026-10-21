from __future__ import annotations

import re
from dataclasses import dataclass, field

from job_assistant.state import Job

# Canonical skill -> aliases found in CVs and JDs
SKILL_ALIASES: dict[str, tuple[str, ...]] = {
    "JavaScript": ("javascript", "ecmascript", "es6", "es6+", r"\bjs\b"),
    "TypeScript": ("typescript", r"\bts\b"),
    "React": ("react.js", "reactjs", r"\breact\b"),
    "Next.js": ("next.js", "nextjs"),
    "Node.js": ("node.js", "nodejs"),
    "Express": ("express.js", "expressjs", r"\bexpress\b"),
    "Redux": ("redux",),
    "Redux-Saga": ("redux-saga", "redux saga"),
    "Zustand": ("zustand",),
    "React Query": ("react query", "tanstack query", "react-query"),
    "React Hook Form": ("react hook form", "react-hook-form"),
    "Zod": (r"\bzod\b",),
    "GraphQL": ("graphql",),
    "Apollo": ("apollo client", "apollo"),
    "Webpack": ("webpack",),
    "HTML": ("html5", r"\bhtml\b"),
    "CSS": ("css3", r"\bcss\b"),
    "SASS/LESS": ("sass", "scss", "less"),
    "Tailwind": ("tailwind", "tailwindcss"),
    "Socket.io": ("socket.io", "socketio", "websockets", "web sockets"),
    "Firebase": ("firebase",),
    "Docker": ("docker",),
    "CI/CD": ("ci/cd", "github actions", "gitlab ci", "jenkins"),
    "Git": (r"\bgit\b", "github", "gitlab"),
    "Jest": (r"\bjest\b",),
    "Design Systems": ("design system", "component library", "ui library"),
    "REST APIs": ("rest api", "restful", r"\bapi\b"),
    "Performance": (
        "web vitals",
        "lighthouse",
        "performance optimization",
        "web workers",
    ),
    "Fintech": ("fintech", "trading", "order-book", "order book"),
    "Claude": ("claude api", r"\bclaude\b", "anthropic"),
    "LLM": (r"\bllm\b", "large language model", "structured output", "structured outputs"),
    "Cursor": (r"\bcursor\b",),
    "LangGraph": ("langgraph",),
    "Pydantic": ("pydantic",),
}

SKILL_WEIGHTS: dict[str, float] = {
    "React": 1.0,
    "TypeScript": 1.0,
    "Next.js": 0.95,
    "JavaScript": 0.85,
    "Node.js": 0.8,
    "Redux": 0.7,
    "Redux-Saga": 0.55,
    "Zustand": 0.5,
    "React Query": 0.65,
    "React Hook Form": 0.5,
    "GraphQL": 0.6,
    "Apollo": 0.5,
    "Webpack": 0.45,
    "Tailwind": 0.55,
    "Docker": 0.45,
    "CI/CD": 0.5,
    "Jest": 0.4,
    "Design Systems": 0.6,
    "Performance": 0.7,
    "Fintech": 0.55,
    "Claude": 0.85,
    "LLM": 0.85,
    "Cursor": 0.5,
    "LangGraph": 0.55,
    "Pydantic": 0.45,
    "REST APIs": 0.4,
    "HTML": 0.3,
    "CSS": 0.3,
    "SASS/LESS": 0.3,
    "Socket.io": 0.4,
    "Firebase": 0.3,
    "Express": 0.45,
    "Zod": 0.35,
    "Git": 0.25,
}

ROLE_POSITIVE = (
    "frontend",
    "front-end",
    "front end",
    "full-stack",
    "fullstack",
    "full stack",
    "react",
    "next.js",
    "nextjs",
    "ui engineer",
    "web engineer",
    "lead frontend",
    "lead front-end",
)

ROLE_SENIOR = ("senior", "lead", "staff", "principal", "architect")
ROLE_JUNIOR = ("junior", "intern", "entry-level", "entry level", "graduate")

ROLE_PENALTIES: tuple[tuple[str, float, str], ...] = (
    ("php", 0.35, "PHP-heavy role"),
    (".net", 0.3, ".NET stack"),
    ("c#", 0.3, "C# / .NET"),
    ("vb.net", 0.45, "VB.Net"),
    ("ruby on rails", 0.3, "Rails"),
    ("ror", 0.2, "Rails"),
    ("shopify", 0.2, "Shopify"),
    ("angular", 0.18, "Angular instead of React"),
    ("vue", 0.12, "Vue instead of React"),
    ("java ", 0.2, "Java backend"),
    ("kotlin", 0.2, "Kotlin"),
    ("swift", 0.2, "Swift"),
)


@dataclass
class CvProfile:
    skills: list[str] = field(default_factory=list)
    text: str = ""


def _contains(text: str, alias: str) -> bool:
    if alias.startswith(r"\b") or any(ch in alias for ch in r".*+?[]()|"):
        return re.search(alias, text, flags=re.IGNORECASE) is not None
    return alias in text


def skills_in_text(text: str) -> list[str]:
    blob = text.lower()
    found: list[str] = []
    for canonical, aliases in SKILL_ALIASES.items():
        if any(_contains(blob, alias) for alias in aliases):
            found.append(canonical)
    return found


def extract_cv_profile(base_cv: str) -> CvProfile:
    skills = skills_in_text(base_cv)
    # Core competencies section is the strongest signal if present
    match = re.search(
        r"core competencies(.*?)(?:\n## |\n### |$)",
        base_cv,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if match:
        section_skills = skills_in_text(match.group(1))
        ordered = list(dict.fromkeys(section_skills + skills))
        skills = ordered
    return CvProfile(skills=skills, text=base_cv)


def _job_blob(job: Job) -> str:
    return " ".join(
        [
            job.get("title") or "",
            job.get("company") or "",
            " ".join(job.get("tags") or []),
            job.get("category") or "",
            (job.get("description") or "")[:4000],
        ]
    ).lower()


def _role_score(title: str) -> tuple[float, list[str]]:
    title_l = title.lower()
    reasons: list[str] = []
    score = 0.2
    if any(token in title_l for token in ROLE_POSITIVE):
        score = 0.85
        reasons.append("Title matches frontend / full-stack / React")
    if any(token in title_l for token in ROLE_SENIOR):
        score = min(1.0, score + 0.15)
        reasons.append("Seniority matches lead/senior profile")
    if any(token in title_l for token in ROLE_JUNIOR):
        score = max(0.0, score - 0.35)
        reasons.append("Junior/intern seniority is a weaker fit")
    return score, reasons


def _penalty(blob: str, title: str) -> tuple[float, list[str]]:
    hay = f"{title} {blob}".lower()
    total = 0.0
    notes: list[str] = []
    for needle, amount, label in ROLE_PENALTIES:
        if needle == "ror":
            hit = re.search(r"\bror\b", hay) is not None
        else:
            hit = needle in hay
        if hit:
            total += amount
            notes.append(label)
    return min(0.6, total), notes


def score_job_against_cv(job: Job, profile: CvProfile) -> dict:
    blob = _job_blob(job)
    job_skills = skills_in_text(blob)
    matched = [skill for skill in profile.skills if skill in job_skills]
    missing_core = [
        skill
        for skill in ("React", "TypeScript", "Next.js", "Node.js")
        if skill in profile.skills and skill not in matched
    ]

    if profile.skills:
        weighted_hits = sum(SKILL_WEIGHTS.get(s, 0.4) for s in matched)
        weighted_all = sum(SKILL_WEIGHTS.get(s, 0.4) for s in profile.skills) or 1.0
        skill_score = min(1.0, weighted_hits / (weighted_all * 0.45))
    else:
        skill_score = 0.4

    role_score, role_reasons = _role_score(job.get("title") or "")
    penalty, penalty_notes = _penalty(blob, job.get("title") or "")

    overall = max(
        0.0,
        min(
            1.0,
            skill_score * 0.62 + role_score * 0.38 - penalty,
        ),
    )
    reasons = [
        f"Matched skills: {', '.join(matched)}" if matched else "Few CV skills in the JD",
        *role_reasons,
        *[f"Penalty: {note}" for note in penalty_notes],
    ]
    return {
        "score": round(overall, 4),
        "skill_score": round(skill_score, 4),
        "role_score": round(role_score, 4),
        "penalty": round(penalty, 4),
        "matched_skills": matched,
        "missing_core_skills": missing_core,
        "reasons": reasons,
    }
