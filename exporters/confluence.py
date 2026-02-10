from __future__ import annotations

from pathlib import Path

from core.models import SectionResult
from core.utils import op_to_token


def clause_to_text(clause) -> str:
    return " AND ".join(f"{lit.display_name} ({lit.op})" for lit in clause)


def _escape_md_cell(value: object) -> str:
    text = "" if value is None else str(value)
    # Keep Confluence pipe-table cells stable even if source text contains separators/newlines.
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def write_confluence_markdown(folder: Path, section: SectionResult, activity: str) -> None:
    if section.status != "OK" or not section.sheet_name:
        return
    lines = []
    lines.append(f"# {activity} - {section.sheet_name}")
    lines.append("")
    lines.append(f"**Goal:** {section.key.dnsh_goal}")
    lines.append(f"**Type:** {section.key.type_label}")
    lines.append("")
    lines.append(f"**Formula IDs:** {section.formula_ids}")
    lines.append(f"**Formula Display:** {section.formula_display}")
    lines.append("")
    lines.append("## DNF")
    if not section.dnf:
        lines.append("- (unsatisfiable)")
    else:
        for idx, clause in enumerate(section.dnf, start=1):
            lines.append(f"- Alignment Rule {idx}: {clause_to_text(clause)}")

    lines.append("")
    header = ["ID", "Technical name", "Question text"] + [f"Alignment Rule {i}" for i in range(1, len(section.dnf) + 1)]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join([" --- "] * len(header)) + "|")

    for variable in section.variables:
        row = [
            _escape_md_cell(variable.id),
            _escape_md_cell(variable.technical_name),
            _escape_md_cell(variable.question_text),
        ]
        for clause in section.dnf:
            token = ""
            for literal in clause:
                if literal.id == variable.id:
                    token = op_to_token(literal.op)
                    break
            row.append(_escape_md_cell(token))
        lines.append("| " + " | ".join(row) + " |")

    path = folder / f"{section.sheet_name}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
