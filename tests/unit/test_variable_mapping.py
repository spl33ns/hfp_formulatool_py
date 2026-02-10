from __future__ import annotations

import pytest

from core.variable_mapping import VariableMeta, load_variable_mapping_tsv, lookup_variable_meta, normalize_var_id


def _row(values: list[str]) -> str:
    return "\t".join(values)


@pytest.mark.parametrize("with_header", [True, False])
def test_load_variable_mapping_reads_question_text_from_col9(tmp_path, with_header):
    mapping_path = tmp_path / "mapping.csv"
    lines = []
    if with_header:
        lines.append(_row(["ID", "x", "Technical name", "x", "x", "x", "x", "x", "Question text"]))
    lines.append(_row(["A1", "x", "Tech A", "x", "x", "x", "x", "x", '"  Question A  "']))
    lines.append(_row(["B2", "x", "Tech B", "x", "x", "x", "x", "x", "Question B"]))
    mapping_path.write_text("\n".join(lines), encoding="utf-8")

    mapping = load_variable_mapping_tsv(mapping_path)

    assert set(mapping.keys()) == {"A1", "B2"}
    assert mapping["A1"].technical_name == "Tech A"
    assert mapping["A1"].question_text == "Question A"
    assert mapping["B2"].technical_name == "Tech B"
    assert mapping["B2"].question_text == "Question B"


def test_normalize_var_id_strips_numeric_suffix():
    assert normalize_var_id("ePBN113509_1") == "ePBN113509"
    assert normalize_var_id("ePBN113509_10") == "ePBN113509"
    assert normalize_var_id("ePBN113509") == "ePBN113509"


def test_lookup_variable_meta_falls_back_to_normalized_id():
    mapping = {"ePBN113509": VariableMeta(technical_name="Tech", question_text="Question")}
    meta = lookup_variable_meta(mapping, "ePBN113509_1")
    assert meta is not None
    assert meta.technical_name == "Tech"
    assert meta.question_text == "Question"
