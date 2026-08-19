from __future__ import annotations

import re
from pathlib import Path


def _normalize_spaced_pdf_text(text: str) -> str:
    """Fix PDF extraction that splits words across lines or pads spaces."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]

    merged: list[str] = []
    buffer = ""
    for line in lines:
        if not line:
            if buffer:
                merged.append(buffer.strip())
                buffer = ""
            if merged and merged[-1] != "":
                merged.append("")
            continue

        # Many resume PDFs emit one short token/phrase per line.
        if len(line) < 40 and not line.endswith((".", ":", ";", ")", "]")):
            buffer = f"{buffer} {line}".strip()
            continue

        if buffer:
            line = f"{buffer} {line}".strip()
            buffer = ""
        merged.append(line)

    if buffer:
        merged.append(buffer.strip())

    text = "\n".join(merged)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


_PRIVATE_CONTACT_LINE = re.compile(
    r"^\s*(?:\*\*)?(?:Location|Phone|Mobile|Tel(?:ephone)?|Cell)(?:\*\*)?\s*:.*$",
    re.I,
)
_PRIVATE_PHONE = re.compile(r"0?912[\s.-]*621[\s.-]*8002")
_INLINE_LOCATION = re.compile(r"\s*\|\s*\*\*Location:\*\*[^|]*", re.I)
_INLINE_PHONE = re.compile(r"\s*\|\s*\*\*Phone:\*\*[^|]*", re.I)


def strip_private_contact(text: str) -> str:
    """Drop personal location and phone; keep email."""
    lines: list[str] = []
    for raw in text.splitlines():
        line = _INLINE_LOCATION.sub("", raw)
        line = _INLINE_PHONE.sub("", line)
        stripped = line.strip()
        if _PRIVATE_CONTACT_LINE.match(stripped):
            continue
        if _PRIVATE_PHONE.search(line):
            remainder = _PRIVATE_PHONE.sub("", line).strip(" *-|:")
            if not remainder:
                continue
            line = _PRIVATE_PHONE.sub("", line)
        lines.append(line)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def load_cv(path: str | Path) -> str:
    """Load a CV from markdown/text or PDF."""
    cv_path = Path(path)
    if not cv_path.exists():
        raise FileNotFoundError(f"CV file not found: {cv_path}")

    suffix = cv_path.suffix.lower()
    if suffix == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(cv_path))
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        raw = "\n\n".join(parts)
        return strip_private_contact(_normalize_spaced_pdf_text(raw))

    return strip_private_contact(cv_path.read_text(encoding="utf-8"))
