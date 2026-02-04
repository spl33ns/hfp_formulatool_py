from __future__ import annotations

import hashlib
import logging
from collections import defaultdict
from pathlib import Path

from core.dnf import normalize_dnf, to_dnf
from core.formula_parser import FormulaParseError, parse_formula_with_literal_parser, parse_literal
from core.models import LiteralModel, SectionKey, SectionResult
from core.stages import Stage
from core.utils import ABBREVIATIONS, ensure_unique_sheet_name, natural_key, sanitize_filename
from exporters.confluence import write_confluence_markdown
from exporters.docs_exporter import write_docs_files
from exporters.xlsx_exporter import write_section_sheet

logger = logging.getLogger(__name__)


class SectionFailure(Exception):
    pass


def _extra(stage: Stage, section: str | None) -> dict[str, str]:
    return {"stage": stage.value, "section": section or "-"}


def _mark_logged(exc: BaseException) -> None:
    try:
        setattr(exc, "_hfp_logged", True)
    except Exception:
        pass


def _is_logged(exc: BaseException) -> bool:
    return bool(getattr(exc, "_hfp_logged", False))


def _format_section_ref(
    env_objective: str | None,
    activity: str | None,
    dnsh_goal: str | None,
    formula_ids: str | None,
    formula_display: str | None,
) -> str:
    def _clean(value: str | None) -> str:
        if value is None:
            return ""
        return str(value).replace("\n", " ").replace("\r", " ").replace("\t", " ").strip()

    a = _clean(env_objective)
    c = _clean(activity)
    f = _clean(dnsh_goal)
    h = _clean(formula_ids)
    h_short = h if len(h) <= 80 else (h[:77] + "...")

    fingerprint_src = "|".join([a, c, f, h, _clean(formula_display)])
    fingerprint = hashlib.md5(fingerprint_src.encode("utf-8")).hexdigest()[:8]

    return f"A={a} | C={c} | F={f} | H={h_short} | id={fingerprint}"


def _run_stage(stage: Stage, section: str | None, func, expected_exceptions: tuple[type[BaseException], ...] = ()):
    logger.info("START", extra=_extra(stage, section))
    try:
        value = func()
    except expected_exceptions as exc:
        logger.warning("FAILED: %s", exc, exc_info=True, extra=_extra(stage, section))
        _mark_logged(exc)
        raise
    except Exception as exc:
        logger.exception("FAILED: unexpected error", extra=_extra(stage, section))
        _mark_logged(exc)
        raise
    else:
        logger.info("OK", extra=_extra(stage, section))
        return value


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
    max_rules: int,
) -> dict[str, list[SectionResult]]:
    from openpyxl import Workbook, load_workbook

    logger.info("START processing", extra=_extra(Stage.RUN, None))
    logger.info("Input=%s Output=%s max_rules=%s", input_path, output_root, max_rules, extra=_extra(Stage.RUN, None))

    workbook = _run_stage(
        Stage.LOAD_WORKBOOK,
        None,
        lambda: load_workbook(input_path, data_only=True),
    )
    sheet = workbook.active

    grouped: dict[tuple[str | None, str | None, str | None, str | None], list[dict[str, str | None]]] = defaultdict(list)
    def _group_rows() -> None:
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

    _run_stage(Stage.GROUP_ROWS, None, _group_rows)
    logger.info("Grouped sections=%d", len(grouped), extra=_extra(Stage.GROUP_ROWS, None))

    activity_results: dict[str, list[SectionResult]] = defaultdict(list)

    for key, rows in grouped.items():
        env_objective, activity, dnsh_goal, formula_ids = key
        first = rows[0]
        section_number = first["B"]
        type_label = first["G"]
        formula_display = first["I"]
        section_ref = _format_section_ref(
            str(env_objective) if env_objective is not None else None,
            str(activity) if activity is not None else None,
            str(dnsh_goal) if dnsh_goal is not None else None,
            str(formula_ids) if formula_ids is not None else None,
            str(formula_display) if formula_display is not None else None,
        )
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
            def _validate_required_fields() -> None:
                if not env_objective or not activity or not dnsh_goal or not formula_ids:
                    raise SectionFailure("Missing required section identification fields")
                if not section_number:
                    raise SectionFailure("Missing section number")
                if not formula_display:
                    raise SectionFailure("Missing display formula")

            _run_stage(Stage.SECTION_VALIDATE, section_ref, _validate_required_fields, expected_exceptions=(SectionFailure,))

            sheet_name = _run_stage(
                Stage.SECTION_SHEET_NAME,
                section_ref,
                lambda: build_sheet_name(str(env_objective), str(section_number)),
                expected_exceptions=(SectionFailure,),
            )
            dnf_clauses, variables = _run_stage(
                Stage.SECTION_PARSE,
                section_ref,
                lambda: parse_formula_pair(str(formula_ids), str(formula_display)),
                expected_exceptions=(SectionFailure, FormulaParseError),
            )

            def _check_rule_limit() -> None:
                if len(dnf_clauses) > max_rules:
                    raise SectionFailure("DNF rule limit exceeded")

            _run_stage(Stage.SECTION_MAX_RULES, section_ref, _check_rule_limit, expected_exceptions=(SectionFailure,))

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
        except Exception as exc:
            if not _is_logged(exc):
                logger.exception("FAILED: hard fail while processing section", extra=_extra(Stage.RUN, section_ref))
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
        activity_ref = f"C={activity}"

        def _init_activity_folders() -> tuple[Path, Path]:
            activity_folder = output_root / sanitize_filename(activity)
            activity_folder.mkdir(parents=True, exist_ok=True)
            confluence_folder = activity_folder / "confluence"
            confluence_folder.mkdir(exist_ok=True)
            return activity_folder, confluence_folder

        activity_folder, confluence_folder = _run_stage(Stage.EXPORT_ACTIVITY_INIT, activity_ref, _init_activity_folders)

        workbook_out = Workbook()
        workbook_out.remove(workbook_out.active)
        used_sheet_names: set[str] = set()
        created_sheet = False
        for section in sections:
            if section.status != "OK":
                continue
            section_ref = _format_section_ref(
                section.key.env_objective,
                section.key.activity,
                section.key.dnsh_goal,
                section.key.formula_ids,
                section.formula_display,
            )

            try:
                def _write_sheet() -> None:
                    assert section.sheet_name
                    unique_name = ensure_unique_sheet_name(section.sheet_name, used_sheet_names)
                    section.sheet_name = unique_name
                    write_section_sheet(workbook_out, section, activity)

                _run_stage(Stage.EXPORT_SECTION_SHEET, section_ref, _write_sheet)
                created_sheet = True

                _run_stage(
                    Stage.EXPORT_SECTION_CONFLUENCE,
                    section_ref,
                    lambda: write_confluence_markdown(confluence_folder, section, activity),
                )
            except Exception as exc:
                # Stage logger already captured stacktrace; reflect failure in result for docs/summary.
                section.status = "FAILED"
                section.error = f"Export failed: {exc}"
                continue

        if not created_sheet:
            def _create_placeholder_sheet() -> None:
                placeholder = workbook_out.create_sheet("No_Valid_Sections")
                placeholder["A1"] = "No valid sections were generated for this activity."

            _run_stage(Stage.EXPORT_ACTIVITY_PLACEHOLDER, activity_ref, _create_placeholder_sheet)

        workbook_path = activity_folder / f"{sanitize_filename(activity)}.xlsx"
        try:
            _run_stage(Stage.EXPORT_ACTIVITY_SAVE_WORKBOOK, activity_ref, lambda: workbook_out.save(workbook_path))
        except Exception:
            # Keep going: docs export may still be helpful.
            pass

        try:
            _run_stage(Stage.EXPORT_ACTIVITY_DOCS, activity_ref, lambda: write_docs_files(activity_folder, activity, sections))
        except Exception:
            pass

    logger.info("DONE processing", extra=_extra(Stage.RUN, None))
    return activity_results
