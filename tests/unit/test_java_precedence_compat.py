from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from core.formula_parser import AndNode, AstNode, FormulaParseError, LiteralNode, NotNode, OrNode, parse_formula
from core.operator_config import OperatorConfig, load_operator_config


JAVA_REFERENCE_CODE = r"""
static
{
    BS_BASE_OPS = new BitSet();
    BASE_OPS = new RPNCollector.RPNOp[32];
    BASE_OPS[OperatorCode.op_unaryminus]     = new RPNOp(BS_BASE_OPS, "-", 8, RIGHT, OperatorCode.op_unaryminus);
    BASE_OPS[OperatorCode.op_unarynot]       = new RPNOp(BS_BASE_OPS, "~", 8, RIGHT, OperatorCode.op_unarynot);

    BASE_OPS[OperatorCode.op_pow]            = new RPNOp(BS_BASE_OPS, "^", 7, RIGHT, OperatorCode.op_pow);
    BASE_OPS[OperatorCode.op_mult]           = new RPNOp(BS_BASE_OPS, "*", 6, LEFT, OperatorCode.op_mult);
    BASE_OPS[OperatorCode.op_div]            = new RPNOp(BS_BASE_OPS, "/", 6, LEFT, OperatorCode.op_div);
    BASE_OPS[OperatorCode.op_modulo]         = new RPNOp(BS_BASE_OPS, "%", 6, LEFT, OperatorCode.op_modulo);

    BASE_OPS[OperatorCode.op_plus]           = new RPNOp(BS_BASE_OPS, "+", 5, LEFT, OperatorCode.op_plus);
    BASE_OPS[OperatorCode.op_minus]          = new RPNOp(BS_BASE_OPS, "-", 5, LEFT, OperatorCode.op_minus);

    BASE_OPS[OperatorCode.op_gte]            = new RPNOp(BS_BASE_OPS, ">=", 4, LEFT, OperatorCode.op_gte);

    BASE_OPS[OperatorCode.op_lte]            = new RPNOp(BS_BASE_OPS, "<=", 4, LEFT, OperatorCode.op_lte);
    BASE_OPS[OperatorCode.op_gt]             = new RPNOp(BS_BASE_OPS, ">",  4, LEFT, OperatorCode.op_gt);
    BASE_OPS[OperatorCode.op_lt]             = new RPNOp(BS_BASE_OPS, "<",  4, LEFT, OperatorCode.op_lt);

    BASE_OPS[OperatorCode.op_equal]          = new RPNOp(BS_BASE_OPS, "=",  3, LEFT, OperatorCode.op_equal);
    BASE_OPS[OperatorCode.op_notequal]       = new RPNOp(BS_BASE_OPS, "<>", 3, LEFT, OperatorCode.op_notequal);

    BASE_OPS[OperatorCode.op_and]            = new RPNOp(BS_BASE_OPS, "&", 2, LEFT, OperatorCode.op_and);
    BASE_OPS[OperatorCode.op_or]             = new RPNOp(BS_BASE_OPS, "|", 1, LEFT, OperatorCode.op_or);
}
"""

_JAVA_OP_PATTERN = re.compile(
    r'BASE_OPS\[OperatorCode\.(?P<opcode>\w+)\]\s*=\s*'
    r'new RPNOp\(BS_BASE_OPS,\s*"(?P<symbol>[^"]+)",\s*'
    r"(?P<precedence>\d+),\s*(?P<assoc>LEFT|RIGHT),\s*OperatorCode\.\w+\);"
)


def _extract_java_operator_table(java_code: str) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    for match in _JAVA_OP_PATTERN.finditer(java_code):
        opcode = match.group("opcode")
        rows.append(
            {
                "opcode": opcode,
                "symbol": match.group("symbol"),
                "precedence": int(match.group("precedence")),
                "associativity": match.group("assoc"),
                "arity": "unary" if opcode.startswith("op_unary") else "binary",
            }
        )
    return rows


def _java_symbol_operator_config(tmp_path: Path) -> OperatorConfig:
    cfg = {
        "AND": ["&"],
        "OR": ["|"],
        "NOT": ["~", "!", "NOT"],
        "NEQ": ["<>", "!="],
        "EQ": ["="],
        "LPAREN": ["("],
        "RPAREN": [")"],
    }
    path = tmp_path / "java_symbols_ops.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return load_operator_config(path)


def _ast_to_rpn_tokens(node: AstNode) -> list[str]:
    if isinstance(node, LiteralNode):
        return [f"{node.literal.id}:{node.literal.op}"]
    if isinstance(node, NotNode):
        return [*_ast_to_rpn_tokens(node.child), "NOT"]
    if isinstance(node, AndNode):
        return [*_ast_to_rpn_tokens(node.left), *_ast_to_rpn_tokens(node.right), "AND"]
    if isinstance(node, OrNode):
        return [*_ast_to_rpn_tokens(node.left), *_ast_to_rpn_tokens(node.right), "OR"]
    raise AssertionError(f"Unsupported AST node type: {type(node).__name__}")


def _parse_to_rpn(formula: str, op_config: OperatorConfig | None = None) -> str:
    ast = parse_formula(formula, op_config=op_config)
    return " ".join(_ast_to_rpn_tokens(ast))


def test_extract_java_operator_table_from_reference():
    table = _extract_java_operator_table(JAVA_REFERENCE_CODE)

    assert table == [
        {"opcode": "op_unaryminus", "symbol": "-", "precedence": 8, "associativity": "RIGHT", "arity": "unary"},
        {"opcode": "op_unarynot", "symbol": "~", "precedence": 8, "associativity": "RIGHT", "arity": "unary"},
        {"opcode": "op_pow", "symbol": "^", "precedence": 7, "associativity": "RIGHT", "arity": "binary"},
        {"opcode": "op_mult", "symbol": "*", "precedence": 6, "associativity": "LEFT", "arity": "binary"},
        {"opcode": "op_div", "symbol": "/", "precedence": 6, "associativity": "LEFT", "arity": "binary"},
        {"opcode": "op_modulo", "symbol": "%", "precedence": 6, "associativity": "LEFT", "arity": "binary"},
        {"opcode": "op_plus", "symbol": "+", "precedence": 5, "associativity": "LEFT", "arity": "binary"},
        {"opcode": "op_minus", "symbol": "-", "precedence": 5, "associativity": "LEFT", "arity": "binary"},
        {"opcode": "op_gte", "symbol": ">=", "precedence": 4, "associativity": "LEFT", "arity": "binary"},
        {"opcode": "op_lte", "symbol": "<=", "precedence": 4, "associativity": "LEFT", "arity": "binary"},
        {"opcode": "op_gt", "symbol": ">", "precedence": 4, "associativity": "LEFT", "arity": "binary"},
        {"opcode": "op_lt", "symbol": "<", "precedence": 4, "associativity": "LEFT", "arity": "binary"},
        {"opcode": "op_equal", "symbol": "=", "precedence": 3, "associativity": "LEFT", "arity": "binary"},
        {"opcode": "op_notequal", "symbol": "<>", "precedence": 3, "associativity": "LEFT", "arity": "binary"},
        {"opcode": "op_and", "symbol": "&", "precedence": 2, "associativity": "LEFT", "arity": "binary"},
        {"opcode": "op_or", "symbol": "|", "precedence": 1, "associativity": "LEFT", "arity": "binary"},
    ]


def test_java_level_2_vs_1_and_before_or():
    assert _parse_to_rpn("A|B&C") == "A:EQ1 B:EQ1 C:EQ1 AND OR"


def test_java_parentheses_override_precedence():
    assert _parse_to_rpn("(A|B)&C") == "A:EQ1 B:EQ1 OR C:EQ1 AND"


def test_java_left_associative_or_chain():
    assert _parse_to_rpn("A|B|C") == "A:EQ1 B:EQ1 OR C:EQ1 OR"


def test_java_left_associative_and_chain():
    assert _parse_to_rpn("A&B&C") == "A:EQ1 B:EQ1 AND C:EQ1 AND"


def test_java_unary_not_tilde_binds_tighter_than_and(tmp_path):
    op_config = _java_symbol_operator_config(tmp_path)
    assert _parse_to_rpn("~A&B", op_config=op_config) == "A:EQ1 NOT B:EQ1 AND"


def test_java_unary_not_chain_is_right_associative(tmp_path):
    op_config = _java_symbol_operator_config(tmp_path)
    assert _parse_to_rpn("~~A", op_config=op_config) == "A:EQ1 NOT NOT"


def test_java_mixed_equality_and_logical_ops():
    assert _parse_to_rpn("A=1&B<>1|NOT C=1") == "A:EQ1 B:NEQ1 AND C:EQ1 NOT OR"


def test_java_edge_whitespace_and_nested_parentheses():
    assert _parse_to_rpn(" ( ( A  |  B ) & ( C | D ) ) ") == "A:EQ1 B:EQ1 OR C:EQ1 D:EQ1 OR AND"


def test_java_multichar_notequal_operator_is_supported():
    assert _parse_to_rpn("A<>1&B=1") == "A:NEQ1 B:EQ1 AND"


@pytest.mark.xfail(
    raises=FormulaParseError,
    strict=True,
    reason="Java precedence levels 8/7 (-, ^) are not implemented in the Python expression parser.",
)
def test_java_adjacent_levels_8_vs_7_unary_minus_vs_pow_not_supported():
    parse_formula("-A^B")


@pytest.mark.xfail(
    raises=FormulaParseError,
    strict=True,
    reason="Java precedence levels 7/6 (^, *, /, %) are not implemented in the Python expression parser.",
)
def test_java_adjacent_levels_7_vs_6_pow_vs_mult_not_supported():
    parse_formula("A^B*C")


@pytest.mark.xfail(
    raises=FormulaParseError,
    strict=True,
    reason="Java precedence levels 6/5 (*, /, %, +, -) are not implemented in the Python expression parser.",
)
def test_java_adjacent_levels_6_vs_5_mult_vs_plus_not_supported():
    parse_formula("A*B+C")


@pytest.mark.xfail(
    raises=FormulaParseError,
    strict=True,
    reason="Java precedence levels 5/4 (+, -, >=, <=, >, <) are not implemented in the Python expression parser.",
)
def test_java_adjacent_levels_5_vs_4_plus_vs_comparison_not_supported():
    parse_formula("A+B>C")


@pytest.mark.xfail(
    raises=FormulaParseError,
    strict=True,
    reason="Java precedence levels 4/3 (>=, <=, >, <, =, <>) are not implemented as expression operators.",
)
def test_java_adjacent_levels_4_vs_3_comparison_vs_equality_not_supported():
    parse_formula("A>=B=C")


@pytest.mark.xfail(
    raises=FormulaParseError,
    strict=True,
    reason="Java level 3 binary equality is not implemented as an expression operator in Python parser.",
)
def test_java_adjacent_levels_3_vs_2_binary_equal_vs_and_not_supported():
    parse_formula("A=B&C")


@pytest.mark.xfail(
    raises=FormulaParseError,
    strict=True,
    reason="Java right-associative pow chain is not implemented in the Python expression parser.",
)
def test_java_right_associative_pow_chain_not_supported():
    parse_formula("A^B^C")


@pytest.mark.xfail(
    raises=FormulaParseError,
    strict=True,
    reason="Java unary-minus vs binary-minus distinction is not implemented in the Python expression parser.",
)
def test_java_unary_minus_vs_binary_minus_not_supported():
    parse_formula("-A-B")


@pytest.mark.xfail(
    raises=FormulaParseError,
    strict=True,
    reason="Java multi-char >= token is not implemented in the Python expression parser.",
)
def test_java_multichar_gte_token_not_supported():
    parse_formula("A>=B")


@pytest.mark.xfail(
    raises=FormulaParseError,
    strict=True,
    reason="Java multi-char <= token is not implemented in the Python expression parser.",
)
def test_java_multichar_lte_token_not_supported():
    parse_formula("A<=B")
