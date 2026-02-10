from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re


ABBREVIATIONS = {
    "Climate Change Mitigation": "CCM",
    "Climate Change Adaptation": "CCA",
    "PollutionPrevention and Control": "PPC",
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


def create_run_output_dir(output_root: str) -> Path:
    """Create a per-run output directory under the user-selected root folder.

    Folder name format: "YYYY-MM-DD HH-mm-ss-fff" (Windows-safe; no ":")
    If the folder already exists, suffixes "_1", "_2", ... are appended.
    """
    root = Path(output_root).expanduser()
    root.mkdir(parents=True, exist_ok=True)

    now = datetime.now()
    ms = now.microsecond // 1000
    base_name = f"{now.strftime('%Y-%m-%d %H-%M-%S')}-{ms:03d}"

    candidate = root / base_name
    if not candidate.exists():
        candidate.mkdir()
        return candidate.resolve()

    suffix = 1
    while True:
        candidate = root / f"{base_name}_{suffix}"
        if not candidate.exists():
            candidate.mkdir()
            return candidate.resolve()
        suffix += 1


def op_to_token(op: str) -> str:
    mapping = {
        "EQ1": "Yes",
        "EQ0": "NO",
        "NEQ1": "Not Yes",
    }
    return mapping[op]
