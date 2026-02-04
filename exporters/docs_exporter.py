from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path


from core.models import SectionResult


DOC_COLUMNS = [
    "Activity",
    "SheetName",
    "Goal",
    "Type",
    "RuleName",
    "ClauseText",
    "LiteralCount",
    "SectionKeyA",
    "SectionKeyB",
    "SectionKeyC",
    "SectionKeyF",
    "SectionKeyG",
    "SectionKeyH",
    "Status",
    "ErrorMessage",
]


def clause_to_text(clause, use_display: bool = False) -> str:
    parts = []
    for literal in clause:
        name = literal.display_name if use_display else literal.id
        parts.append(f"{name} {literal.op}")
    return " AND ".join(parts)


def write_docs_files(folder: Path, activity: str, sections: list[SectionResult]) -> None:
    rows: list[list[object]] = []
    json_sections = []

    for section in sections:
        if section.status != "OK":
            rows.append(
                [
                    activity,
                    section.sheet_name,
                    section.key.dnsh_goal,
                    section.key.type_label,
                    "",
                    "",
                    0,
                    section.key.env_objective,
                    section.key.section_number,
                    section.key.activity,
                    section.key.dnsh_goal,
                    section.key.type_label,
                    section.key.formula_ids,
                    section.status,
                    section.error,
                ]
            )
            json_sections.append(
                {
                    "key": {
                        "A": section.key.env_objective,
                        "B": section.key.section_number,
                        "C": section.key.activity,
                        "F": section.key.dnsh_goal,
                        "G": section.key.type_label,
                        "H": section.key.formula_ids,
                    },
                    "sheetName": section.sheet_name,
                    "formulaIds": section.formula_ids,
                    "formulaDisplay": section.formula_display,
                    "variables": [],
                    "dnf": [],
                    "rules": [],
                    "status": section.status,
                    "error": section.error,
                }
            )
            continue

        rules = []
        for idx, clause in enumerate(section.dnf, start=1):
            rule_name = f"Alignment Rule {idx}"
            clause_text = clause_to_text(clause, use_display=False)
            rows.append(
                [
                    activity,
                    section.sheet_name,
                    section.key.dnsh_goal,
                    section.key.type_label,
                    rule_name,
                    clause_text,
                    len(clause),
                    section.key.env_objective,
                    section.key.section_number,
                    section.key.activity,
                    section.key.dnsh_goal,
                    section.key.type_label,
                    section.key.formula_ids,
                    section.status,
                    section.error,
                ]
            )
            rules.append({"name": rule_name, "clauseIndex": idx - 1})

        json_sections.append(
            {
                "key": {
                    "A": section.key.env_objective,
                    "B": section.key.section_number,
                    "C": section.key.activity,
                    "F": section.key.dnsh_goal,
                    "G": section.key.type_label,
                    "H": section.key.formula_ids,
                },
                "sheetName": section.sheet_name,
                "formulaIds": section.formula_ids,
                "formulaDisplay": section.formula_display,
                "variables": [
                    {"id": var.id, "displayName": var.display_name} for var in section.variables
                ],
                "dnf": [
                    [
                        {"id": lit.id, "displayName": lit.display_name, "op": lit.op}
                        for lit in clause
                    ]
                    for clause in section.dnf
                ],
                "rules": rules,
                "status": section.status,
                "error": section.error,
            }
        )

    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(DOC_COLUMNS)
    for row in rows:
        sheet.append(row)

    excel_path = folder / f"DNF_{activity}.xlsx"
    workbook.save(excel_path)

    csv_path = folder / f"DNF_{activity}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(DOC_COLUMNS)
        writer.writerows(rows)

    json_path = folder / f"DNF_{activity}.json"
    data = {
        "activity": activity,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "sections": json_sections,
        "summary": {
            "sectionsTotal": len(sections),
            "sectionsSucceeded": len([s for s in sections if s.status == "OK"]),
            "sectionsFailed": len([s for s in sections if s.status != "OK"]),
        },
    }
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
