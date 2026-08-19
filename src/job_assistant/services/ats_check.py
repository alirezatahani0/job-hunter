from __future__ import annotations

import re

from job_assistant.services.cv_matcher import extract_cv_profile, skills_in_text
from job_assistant.state import EvaluationScores, Job

AI_TELLS = (
    "spearheaded",
    "leveraged",
    "utilized",
    "robust",
    "seamless",
    "cutting-edge",
    "results-driven",
    "passionate",
    "synerg",
    "meticulous",
    "excelled in",
    "proven track record",
    "dynamic professional",
    "highly motivated",
    "in today's fast-paced",
    "cross-functional excellence",
)

_EMAIL = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
_PHONE = re.compile(r"\d[\d\s().-]{8,}\d")
_HEADING = re.compile(r"^#{1,3} ", re.M)
_SECTION = re.compile(
    r"^#{1,3} .*(summary|experience|competenc|skill|education)",
    re.I | re.M,
)


def ai_tells_in(text: str) -> list[str]:
    lower = text.lower()
    return [phrase for phrase in AI_TELLS if phrase in lower]


def evaluate_ats(cv: str, job: Job) -> EvaluationScores:
    """Heuristic ATS check. No LLM — parseability + JD keyword overlap."""
    text = (cv or "").strip()
    feedback: list[str] = []

    format_quality = _format_score(text, feedback)
    jd_relevance, missing = _relevance_score(text, job, feedback)
    human_readability, ai_detected = _readability_score(text, feedback)

    ats_score = round(format_quality * 0.55 + jd_relevance * 0.45, 1)
    parse_ok = format_quality >= 70
    ats_pass = ats_score >= 70 and parse_ok
    if not parse_ok:
        feedback.append("Format looks risky for ATS parsing (tables, missing sections, or no contact).")
    if ats_pass:
        feedback.append("Likely to pass a typical ATS parse and keyword screen for this JD.")
    else:
        feedback.append("Would likely fail or rank poorly in ATS for this JD.")

    overall = round(
        jd_relevance * 0.35
        + ats_score * 0.25
        + human_readability * 0.20
        + format_quality * 0.20,
        1,
    )
    if missing:
        feedback.append("JD skills missing from this resume: " + ", ".join(missing[:8]))

    return {
        "jd_relevance": round(jd_relevance, 1),
        "human_readability": round(human_readability, 1),
        "format_quality": round(format_quality, 1),
        "ats_score": ats_score,
        "ats_pass": ats_pass,
        "ai_detected": ai_detected,
        "overall": overall,
        "feedback": feedback,
        "missing_skills": missing,
    }


def _format_score(text: str, feedback: list[str]) -> float:
    if not text:
        feedback.append("Resume is empty.")
        return 0.0
    score = 40.0
    if _EMAIL.search(text):
        score += 15
    else:
        feedback.append("No email address found.")
    if _PHONE.search(text):
        score += 8
    if _HEADING.search(text):
        score += 12
    else:
        feedback.append("No markdown headings — ATS parsers like clear section titles.")
    if _SECTION.search(text):
        score += 10
    else:
        feedback.append("Missing a standard section (Summary / Experience / Skills).")
    if re.search(r"^\|.+\|", text, re.M) or "<table" in text.lower():
        score -= 25
        feedback.append("Tables detected — many ATS parsers scramble columns.")
    if re.search(r"<img|!\[", text, re.I):
        score -= 10
        feedback.append("Images/icons are not ATS-safe.")
    length = len(text)
    if 800 <= length <= 12000:
        score += 10
    elif length < 800:
        score -= 15
        feedback.append("Resume is very short; ATS keyword coverage will be thin.")
    else:
        score -= 5
        feedback.append("Resume is long; trim toward 1–2 pages.")
    if re.search(r"^[-*] ", text, re.M):
        score += 5
    return max(0.0, min(100.0, score))


def _relevance_score(text: str, job: Job, feedback: list[str]) -> tuple[float, list[str]]:
    profile = extract_cv_profile(text)
    jd_blob = " ".join(
        [
            job.get("title") or "",
            " ".join(job.get("tags") or []),
            (job.get("description") or "")[:4000],
        ]
    )
    jd_skills = skills_in_text(jd_blob)
    cv_skills = set(profile.skills)
    matched = [skill for skill in jd_skills if skill in cv_skills]
    missing = [skill for skill in jd_skills if skill not in cv_skills]

    if jd_skills:
        coverage = len(matched) / len(jd_skills)
        score = coverage * 100
        feedback.append(
            f"JD keyword hit: {len(matched)}/{len(jd_skills)} tracked skills."
        )
    else:
        title = (job.get("title") or "").lower()
        tokens = [t for t in re.findall(r"[a-z0-9.+#]+", title) if len(t) > 2]
        hits = sum(1 for t in tokens if t in text.lower())
        score = (hits / len(tokens) * 100) if tokens else 50.0
        missing = []

    title_l = (job.get("title") or "").lower()
    if any(token in title_l for token in ("frontend", "front-end", "full-stack", "fullstack", "react")):
        if any(s in cv_skills for s in ("React", "TypeScript", "Next.js", "JavaScript")):
            score = min(100.0, score + 8)
        else:
            score = max(0.0, score - 12)
            feedback.append("Title is frontend/full-stack but core web skills are missing from the CV.")
    return max(0.0, min(100.0, score)), missing


def _readability_score(text: str, feedback: list[str]) -> tuple[float, bool]:
    tells = ai_tells_in(text)
    bullets = [ln[2:].strip() for ln in text.splitlines() if ln.strip().startswith(("- ", "* "))]
    score = 78.0
    if tells:
        score -= min(35.0, 8.0 * len(tells))
        feedback.append("AI-sounding phrases: " + ", ".join(tells[:6]))
    if bullets:
        lengths = [len(b) for b in bullets]
        avg = sum(lengths) / len(lengths)
        if avg < 40:
            score -= 8
            feedback.append("Bullets are very short; add concrete actions and tools.")
        elif avg > 220:
            score -= 8
            feedback.append("Bullets are long; ATS and recruiters prefer scannable lines.")
        openers = [b.split(" ", 1)[0].lower() for b in bullets if b]
        if openers:
            unique = len(set(openers)) / len(openers)
            if unique < 0.35:
                score -= 10
                feedback.append("Too many bullets start with the same verb (AI cadence).")
    if re.search(r"\d", text):
        score += 6
    else:
        feedback.append("Few or no metrics — numbers help both ATS and humans.")
    ai_detected = len(tells) >= 3 or (len(tells) >= 2 and score < 65)
    return max(0.0, min(100.0, score)), ai_detected
