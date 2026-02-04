from core.dnf import normalize_dnf, to_dnf
from core.formula_parser import parse_formula
from core.models import LiteralModel


def test_dnf_or_expansion():
    ast = parse_formula("A OR B OR C")
    dnf = to_dnf(ast)
    assert len(dnf) == 3


def test_dnf_and_or():
    ast = parse_formula("A AND (B OR C)")
    dnf = to_dnf(ast)
    assert len(dnf) == 2


def test_normalization_dedupe():
    clauses = [[LiteralModel("A", "A", "EQ1"), LiteralModel("A", "A", "EQ1")]]
    normalized = normalize_dnf(clauses)
    assert len(normalized) == 1
    assert len(normalized[0]) == 1


def test_normalization_contradiction():
    clauses = [[LiteralModel("A", "A", "EQ1"), LiteralModel("A", "A", "EQ0")]]
    normalized = normalize_dnf(clauses)
    assert len(normalized) == 0