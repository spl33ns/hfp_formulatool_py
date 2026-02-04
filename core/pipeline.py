from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path

from core.dnf import normalize_dnf, to_dnf
from core.formula_parser import FormulaParseError, parse_formula_with_literal_parser, parse_literal
from core.models import LiteralModel, SectionKey, SectionResult
from core.utils import ABBREVIATIONS, ensure_unique_sheet_name, natural_key, sanitize_filename
from exporters.confluence import write_confluence_markdown
from exporters.docs_exporter import write_docs_files
from exporters.xlsx_exporter import write_section_sheet

logger = logging.getLogger(__name__)


class SectionFailure(Exception):
    pass


def build_sheet_name(env_objective: str, section_number: str) -> str:
    if env_objective not in ABBREVIATIONS:
        raise SectionFailure(f"Unknown environmental objective: {env_objective}")
    abbrev = ABBREVIATIONS[env_objective]
    raw_name = f"{abbrev}_{section_number}"
    return raw_name


def parse_formula_pair(formula_ids: str, formula_display: str) -> tuple[list[list[LiteralModel]], list[LiteralModel]]:
    id_literals: list[LiteralModel] = []
    display_literals: list[LiteralModel] = []

    def id_literal_parser(raw_literal: str) -> LiteralModel:
        literal = parse_literal(raw_literal, raw_literal)
        id_literals.append(literal)
        return literal

    def display_literal_parser(raw_literal: str) -> LiteralModel:
        literal = parse_literal(raw_literal, raw_literal)
        display_literals.append(literal)
        return literal

    id_ast = parse_formula_with_literal_parser(formula_ids, id_literal_parser)
    display_ast = parse_formula_with_literal_parser(formula_display, display_literal_parser)

    def compare_structure(left, right) -> None:
        if type(left) is not type(right):
            raise SectionFailure("Formula structure mismatch between H and I")
        if hasattr(left, "literal"):
            return
        if hasattr(left, "child"):
            compare_structure(left.child, right.child)
            return
        if hasattr(left, "left") and hasattr(left, "right"):
            compare_structure(left.left, right.left)
            compare_structure(left.right, right.right)
            return

    compare_structure(id_ast, display_ast)

    if len(id_literals) != len(display_literals):
        raise SectionFailure("Formula literal count mismatch between H and I")

    for id_lit, display_lit in zip(id_literals, display_literals):
        if id_lit.op != display_lit.op:
            raise SectionFailure("Formula literal operators mismatch between H and I")

    id_to_display: dict[str, str] = {}
    for id_lit, display_lit in zip(id_literals, display_literals):
        if id_lit.id in id_to_display and id_to_display[id_lit.id] != display_lit.id:
            raise SectionFailure(f"Inconsistent display name for ID {id_lit.id}")
        id_to_display[id_lit.id] = display_lit.id

    if len(set(id_to_display.values())) != len(id_to_display.values()):
        raise SectionFailure("Duplicate display name for different IDs")

    dnf_clauses = to_dnf(id_ast)
    dnf_with_display = [
        [LiteralModel(id=lit.id, display_name=id_to_display[lit.id], op=lit.op) for lit in clause]
        for clause in dnf_clauses
    ]
    normalized = normalize_dnf(dnf_with_display)

    deduped_vars: dict[str, LiteralModel] = {}
    for lit in id_literals:
        if lit.id not in deduped_vars:
            deduped_vars[lit.id] = LiteralModel(id=lit.id, display_name=id_to_display[lit.id], op=lit.op)
    return normalized, list(deduped_vars.values())


def process_excel(
    input_path: Path,
    output_root: Path,
    template_path: Path | None,
    max_rules: int,
) -> dict[str, list[SectionResult]]:
    from openpyxl import Workbook, load_workbook

    workbook = load_workbook(input_path, data_only=True)
    sheet = workbook.active

    grouped: dict[tuple[str | None, str | None, str | None, str | None], list[dict[str, str | None]]] = defaultdict(list)
    for row in sheet.iter_rows(min_row=2):
        values = {
            "A": row[0].value,
            "B": row[1].value,
            "C": row[2].value,
            "F": row[5].value,
            "G": row[6].value,
            "H": row[7].value,
            "I": row[8].value,
            "J": row[9].value if len(row) > 9 else None,
        }
        key = (values["A"], values["C"], values["F"], values["H"])
        grouped[key].append(values)

    activity_results: dict[str, list[SectionResult]] = defaultdict(list)

    for key, rows in grouped.items():
        env_objective, activity, dnsh_goal, formula_ids = key
        first = rows[0]
        section_number = first["B"]
        type_label = first["G"]
        formula_display = first["I"]
        section_key = SectionKey(
            env_objective=str(env_objective) if env_objective is not None else None,
            section_number=str(section_number) if section_number is not None else None,
            activity=str(activity) if activity is not None else None,
            dnsh_goal=str(dnsh_goal) if dnsh_goal is not None else None,
            formula_ids=str(formula_ids) if formula_ids is not None else None,
            type_label=str(type_label) if type_label is not None else None,
        )
        activity_name = str(activity) if activity else "Unknown"
        try:
            if not env_objective or not activity or not dnsh_goal or not formula_ids:
                raise SectionFailure("Missing required section identification fields")
            if not section_number:
                raise SectionFailure("Missing section number")
            if not formula_display:
                raise SectionFailure("Missing display formula")

            sheet_name = build_sheet_name(str(env_objective), str(section_number))
            dnf_clauses, variables = parse_formula_pair(str(formula_ids), str(formula_display))
            if len(dnf_clauses) > max_rules:
                raise SectionFailure("DNF rule limit exceeded")

            result = SectionResult(
                key=section_key,
                sheet_name=sheet_name,
                formula_ids=str(formula_ids),
                formula_display=str(formula_display),
                variables=sorted(variables, key=lambda lit: natural_key(lit.id)),
                dnf=dnf_clauses,
                status="OK",
                error=None,
            )
        except (SectionFailure, FormulaParseError) as exc:
            result = SectionResult(
                key=section_key,
                sheet_name=None,
                formula_ids=str(formula_ids) if formula_ids else None,
                formula_display=str(formula_display) if formula_display else None,
                variables=[],
                dnf=[],
                status="FAILED",
                error=str(exc),
            )
        activity_results[activity_name].append(result)

    for activity, sections in activity_results.items():
        activity_folder = output_root / sanitize_filename(activity)
        activity_folder.mkdir(parents=True, exist_ok=True)
        confluence_folder = activity_folder / "confluence"
        confluence_folder.mkdir(exist_ok=True)

        workbook_out = Workbook()
        workbook_out.remove(workbook_out.active)
        used_sheet_names: set[str] = set()
        created_sheet = False
        for section in sections:
            if section.status != "OK":
                continue
            assert section.sheet_name
            unique_name = ensure_unique_sheet_name(section.sheet_name, used_sheet_names)
            section.sheet_name = unique_name
            write_section_sheet(
                workbook_out,
                section,
                activity,
            )
            write_confluence_markdown(confluence_folder, section, activity)
            created_sheet = True

        if not created_sheet:
            placeholder = workbook_out.create_sheet("No_Valid_Sections")
            placeholder["A1"] = "No valid sections were generated for this activity."

        workbook_path = activity_folder / f"{sanitize_filename(activity)}.xlsx"
        workbook_out.save(workbook_path)

        write_docs_files(activity_folder, activity, sections)

    return activity_results
