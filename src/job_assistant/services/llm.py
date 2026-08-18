from __future__ import annotations

import json
import os
import re
from typing import Any, TypeVar

from langchain_openai import ChatOpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


def get_llm(temperature: float = 0.2) -> ChatOpenAI:
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return ChatOpenAI(model=model, temperature=temperature, api_key=api_key)


def invoke_structured(llm: ChatOpenAI, schema: type[T], prompt: str) -> T:
    """Prefer native structured output; fall back to JSON parsing."""
    try:
        structured = llm.with_structured_output(schema)
        result = structured.invoke(prompt)
        if isinstance(result, schema):
            return result
        if isinstance(result, dict):
            return schema.model_validate(result)
    except Exception:
        pass

    raw = llm.invoke(
        prompt
        + "\n\nRespond with ONLY valid JSON matching the required schema. No markdown."
    )
    content = raw.content if hasattr(raw, "content") else str(raw)
    if isinstance(content, list):
        content = "".join(
            part.get("text", "") if isinstance(part, dict) else str(part)
            for part in content
        )
    text = str(content).strip()
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"LLM did not return JSON: {text[:400]}")
    data: dict[str, Any] = json.loads(match.group(0))
    return schema.model_validate(data)
