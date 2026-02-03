from __future__ import annotations

import re


ABBREVIATIONS = {
    "Climate Change Mitigation": "CCM",
    "Climate Change Adaptation": "CCA",
    "Water": "WTR",
    "Biodiversity": "BIO",
    "Circular Economy": "CE",
}


def natural_key(text: str) -> list[object]:
    parts: list[object] = []
    for piece in re.split(r"(\d+)", text):
        if piece.isdigit():
            parts.append(int(piece))
        else:
            parts.append(piece.lower())
    return parts


def sanitize_excel_sheet_name(name: str) -> str:
    cleaned = re.sub(r"[\[\]\*\?/\\:]", "", name)
    cleaned = cleaned.replace("'", "")
    return cleaned.strip()


def ensure_unique_sheet_name(name: str, used: set[str]) -> str:
    base = sanitize_excel_sheet_name(name)
    trimmed = base[:31]
    candidate = trimmed
    if candidate not in used:
        used.add(candidate)
        return candidate
    suffix = 1
    while True:
        suffix_text = f"_{suffix}"
        candidate = (trimmed[: 31 - len(suffix_text)] + suffix_text).rstrip()
        if candidate not in used:
            used.add(candidate)
            return candidate
        suffix += 1


def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
    return cleaned.strip("_") or "output"


def op_to_token(op: str) -> str:
    mapping = {
        "EQ1": "Yes",
        "EQ0": "NO",
        "NEQ1": "Not Yes",
    }
    return mapping[op]