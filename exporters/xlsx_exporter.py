from __future__ import annotations

from core.models import SectionResult
from core.utils import op_to_token


HEADER_ROWS = 6


def write_section_sheet(workbook, section: SectionResult, activity: str) -> None:
    sheet = workbook.create_sheet(section.sheet_name)
    sheet["A1"] = "Activity"
    sheet["B1"] = activity
    sheet["A2"] = "DNSH Goal"
    sheet["B2"] = section.key.dnsh_goal
    sheet["A3"] = "Type"
    sheet["B3"] = section.key.type_label
    sheet["A4"] = "Formula IDs"
    sheet["B4"] = section.formula_ids
    sheet["A5"] = "Formula Display"
    sheet["B5"] = section.formula_display

    start_row = HEADER_ROWS + 1
    sheet.cell(row=start_row, column=1, value="ID")
    sheet.cell(row=start_row, column=2, value="Technical name")
    sheet.cell(row=start_row, column=3, value="Question text")

    for idx, clause in enumerate(section.dnf, start=1):
        sheet.cell(row=start_row, column=3 + idx, value=f"Alignment Rule {idx}")

    for row_offset, variable in enumerate(section.variables, start=1):
        row_index = start_row + row_offset
        sheet.cell(row=row_index, column=1, value=variable.id)
        sheet.cell(row=row_index, column=2, value=variable.technical_name)
        sheet.cell(row=row_index, column=3, value=variable.question_text)
        for clause_index, clause in enumerate(section.dnf, start=1):
            token = ""
            for literal in clause:
                if literal.id == variable.id:
                    token = op_to_token(literal.op)
                    break
            sheet.cell(row=row_index, column=3 + clause_index, value=token)
