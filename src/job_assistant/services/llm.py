from __future__ import annotations

import os
from typing import Any, TypeVar

from langchain_anthropic import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_CV_ALIASES = ("updated_cv", "resume", "cv", "updated_resume", "markdown", "text")
_CHANGES_ALIASES = ("changes_made", "changes", "edits", "notes")
_LETTER_ALIASES = ("cover_letter", "letter", "body", "text")


def get_llm(temperature: float = 0.2) -> ChatAnthropic:
    model = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return ChatAnthropic(model=model, temperature=temperature, api_key=api_key)


def coerce_to_schema(schema: type[T], payload: Any) -> T:
    """Map Claude's alternate field names onto our Pydantic models."""
    if isinstance(payload, schema):
        return payload
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object, got {type(payload).__name__}")

    data = dict(payload)
    fields = schema.model_fields

    if "updated_cv" in fields and "updated_cv" not in data:
        for key in _CV_ALIASES:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                data["updated_cv"] = value
                break

    if "changes_made" in fields and "changes_made" not in data:
        for key in _CHANGES_ALIASES:
            if key in data:
                data["changes_made"] = data[key]
                break
        else:
            data["changes_made"] = []

    if isinstance(data.get("changes_made"), str):
        text = data["changes_made"].strip()
        data["changes_made"] = [text] if text else []

    if "keywords_used" in fields:
        data.setdefault("keywords_used", [])
    if "ai_tells_removed" in fields:
        data.setdefault("ai_tells_removed", [])
    if "cover_letter" in fields and "cover_letter" not in data:
        for key in _LETTER_ALIASES:
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                data["cover_letter"] = value
                break
    if "points_used" in fields:
        data.setdefault("points_used", [])
    if isinstance(data.get("points_used"), str):
        text = data["points_used"].strip()
        data["points_used"] = [text] if text else []

    return schema.model_validate(data)


def invoke_structured(llm: BaseChatModel, schema: type[T], prompt: str) -> T:
    """One Anthropic request. Coerce alternate field names locally."""
    structured = llm.with_structured_output(schema)
    result = structured.invoke(prompt)
    return coerce_to_schema(schema, result)
