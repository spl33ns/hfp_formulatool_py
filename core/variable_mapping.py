from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_ID_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")
_HEADER_ID_MARKERS = {"id", "variable id", "variable_id"}
_HEADER_TECH_MARKERS = {"technical name", "technical_name"}
_HEADER_QUESTION_MARKERS = {"question text", "question_text"}
_ID_SUFFIX_PATTERN = re.compile(r"^(.*)_\d+$")


class VariableMappingError(ValueError):
    pass


@dataclass(frozen=True)
class VariableMeta:
    technical_name: str
    question_text: str


def _normalize(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _looks_like_id(value: str) -> bool:
    return bool(_ID_PATTERN.fullmatch(value))


def normalize_var_id(var_id: str) -> str:
    normalized = var_id.strip()
    match = _ID_SUFFIX_PATTERN.match(normalized)
    if match:
        return match.group(1)
    return normalized


def lookup_variable_meta(mapping: dict[str, VariableMeta], var_id: str) -> VariableMeta | None:
    original_id = var_id.strip()
    meta = mapping.get(original_id)
    if meta is not None:
        return meta
    return mapping.get(normalize_var_id(original_id))


def _is_header_row(id_value: str, technical_name: str, question_text: str) -> bool:
    if id_value.casefold() in _HEADER_ID_MARKERS:
        return True
    if technical_name.casefold() in _HEADER_TECH_MARKERS:
        return True
    if question_text.casefold() in _HEADER_QUESTION_MARKERS:
        return True
    return False


def load_variable_mapping_tsv(
    path: str | Path,
    *,
    log_extra: dict[str, str] | None = None,
) -> dict[str, VariableMeta]:
    """Load variable metadata mapping from UTF-8 TSV file.

    Required format:
    - file extension can be .csv, but content must be TAB-delimited
    - encoding UTF-8
    - columns (1-based): 1=ID, 3=Technical name, 9=Question text
    """
    mapping_path = Path(path).expanduser().resolve()

    if log_extra:
        logger.info("CONFIG_LOAD_START: mapping_path=%s", mapping_path, extra=log_extra)
    else:
        logger.info("CONFIG_LOAD_START: mapping_path=%s", mapping_path)

    mapping: dict[str, VariableMeta] = {}
    duplicate_ids: list[str] = []
    try:
        with mapping_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, delimiter="\t")
            for row_index, row in enumerate(reader, start=1):
                if not row:
                    continue

                padded = row + [""] * max(0, 9 - len(row))
                id_value = _normalize(padded[0])
                technical_name = _normalize(padded[2])
                question_text = _normalize(padded[8])

                if row_index == 1 and (
                    _is_header_row(id_value, technical_name, question_text)
                    or (id_value and not _looks_like_id(id_value))
                ):
                    continue

                if not id_value:
                    continue

                if id_value in mapping:
                    duplicate_ids.append(id_value)
                mapping[id_value] = VariableMeta(
                    technical_name=technical_name,
                    question_text=question_text,
                )
    except Exception as exc:
        if log_extra:
            logger.error(
                "CONFIG_LOAD_FAILED: mapping_path=%s error=%s",
                mapping_path,
                exc,
                exc_info=True,
                extra=log_extra,
            )
        else:
            logger.error(
                "CONFIG_LOAD_FAILED: mapping_path=%s error=%s",
                mapping_path,
                exc,
                exc_info=True,
            )
        raise VariableMappingError(
            f"CONFIG_LOAD_FAILED: could not read mapping file '{mapping_path}'"
        ) from exc

    if duplicate_ids:
        unique_duplicate_ids = list(dict.fromkeys(duplicate_ids))
        sample = unique_duplicate_ids[:20]
        if log_extra:
            logger.warning(
                "DUPLICATE_ID_MAPPING: duplicates=%d sample=%s",
                len(unique_duplicate_ids),
                sample,
                extra=log_extra,
            )
        else:
            logger.warning(
                "DUPLICATE_ID_MAPPING: duplicates=%d sample=%s",
                len(unique_duplicate_ids),
                sample,
            )

    if log_extra:
        logger.info(
            "CONFIG_LOAD_OK: mapping_path=%s mappings=%d",
            mapping_path,
            len(mapping),
            extra=log_extra,
        )
    else:
        logger.info("CONFIG_LOAD_OK: mapping_path=%s mappings=%d", mapping_path, len(mapping))

    return mapping
