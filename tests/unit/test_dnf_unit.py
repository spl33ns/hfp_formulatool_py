import pytest

from core.dnf import normalize_dnf, to_dnf, to_nnf
from core.formula_parser import FormulaParseError, parse_formula
from core.models import LiteralModel


def test_to_nnf_de_morgan_and_to_dnf_expansion():
    ast = parse_formula("NOT (A AND B)")
    nnf = to_nnf(ast)
    dnf = to_dnf(nnf)
    assert len(dnf) == 2
    literal_signatures = {clause[0].id + ":" + clause[0].op for clause in dnf}
    assert literal_signatures == {"A:NEQ1", "B:NEQ1"}


def test_to_dnf_or_chain_expands_to_multiple_clauses():
    ast = parse_formula("A OR B OR C")
    dnf = to_dnf(ast)
    assert len(dnf) == 3


def test_normalize_dnf_dedupes_and_removes_contradictions():
    clauses = [
        [
            LiteralModel("A", "A", "EQ1"),
            LiteralModel("A", "A", "EQ1"),
            LiteralModel("B", "B", "EQ1"),
        ],
        [LiteralModel("C", "C", "EQ1"), LiteralModel("C", "C", "EQ0")],
    ]
    normalized = normalize_dnf(clauses)
    assert len(normalized) == 1
    assert [(lit.id, lit.op) for lit in normalized[0]] == [("A", "EQ1"), ("B", "EQ1")]


def test_to_nnf_unsupported_node_raises():
    class FakeNode:
        pass

    with pytest.raises(FormulaParseError):
        to_nnf(FakeNode())
