import json

import pytest

from core.dnf import normalize_dnf, to_dnf
from core.formula_parser import FormulaParseError, parse_formula, parse_formula_with_literal_parser, parse_literal
from core.models import LiteralModel
from core.operator_config import load_operator_config


def test_parser_supports_ampersand_pipe_and_neq():
    op_config = load_operator_config()

    def id_literal_parser(raw_literal: str) -> LiteralModel:
        parsed = parse_literal(raw_literal, raw_literal, op_config=op_config)
        return LiteralModel(id=parsed.id, display_name=parsed.id, op=parsed.op)

    ast = parse_formula_with_literal_parser(
        "((ePBN111002_1|ePBN111003_1))&(ePBN993847_1<>1)&ePBN110911_1",
        id_literal_parser,
        op_config=op_config,
    )
    dnf = normalize_dnf(to_dnf(ast))

    assert len(dnf) == 2
    clause_sets = [{(lit.id, lit.op) for lit in clause} for clause in dnf]
    assert all(("ePBN993847_1", "NEQ1") in s for s in clause_sets)
    assert all(("ePBN110911_1", "EQ1") in s for s in clause_sets)
    assert {("ePBN111002_1", "EQ1"), ("ePBN111003_1", "EQ1")} == {next(iter(s - {("ePBN993847_1", "NEQ1"), ("ePBN110911_1", "EQ1")})) for s in clause_sets}


def test_parse_literal_rejects_neq0():
    op_config = load_operator_config()
    with pytest.raises(FormulaParseError) as exc:
        parse_literal("A<>0", "A", op_config=op_config)
    assert "<>0" in str(exc.value)


def test_custom_and_operator_double_ampersand(tmp_path):
    cfg = {
        "AND": ["&&"],
        "OR": ["|"],
        "NOT": ["!"],
        "NEQ": ["<>"],
        "EQ": ["="],
        "LPAREN": ["("],
        "RPAREN": [")"],
    }
    path = tmp_path / "operators.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")

    op_config = load_operator_config(path)
    ast = parse_formula("A&&B", op_config=op_config)
    dnf = to_dnf(ast)
    assert len(dnf) == 1
    assert {(lit.id, lit.op) for lit in dnf[0]} == {("A", "EQ1"), ("B", "EQ1")}


def test_tokenize_fails_when_operator_not_configured(tmp_path):
    cfg = {
        "AND": ["AND"],  # no "&"
        "OR": ["OR"],
        "NOT": ["NOT"],
        "NEQ": ["<>"],
        "EQ": ["="],
        "LPAREN": ["("],
        "RPAREN": [")"],
    }
    path = tmp_path / "operators.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")

    op_config = load_operator_config(path)
    with pytest.raises(FormulaParseError) as exc:
        parse_formula("A&B", op_config=op_config)
    assert "TOKENIZE_FAILED" in str(exc.value)
    assert "pos=" in str(exc.value)
