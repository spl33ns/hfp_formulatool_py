import pytest

from core.formula_parser import FormulaParseError, parse_literal
from core.utils import op_to_token


def test_op_to_token_mapping():
    assert op_to_token("EQ1") == "Yes"
    assert op_to_token("EQ0") == "NO"
    assert op_to_token("NEQ1") == "Not Yes"


def test_parse_literal_variants():
    assert parse_literal("a", "a").op == "EQ1"
    assert parse_literal("a=1", "a").op == "EQ1"
    assert parse_literal("a=0", "a").op == "EQ0"
    assert parse_literal("!a", "a").op == "NEQ1"
    assert parse_literal("a<>1", "a").op == "NEQ1"
    assert parse_literal("a!=1", "a").op == "NEQ1"


def test_parse_literal_unsupported_operators():
    with pytest.raises(FormulaParseError):
        parse_literal("a<=1", "a")
    with pytest.raises(FormulaParseError):
        parse_literal("a>=1", "a")
import pytest

from core.formula_parser import FormulaParseError, parse_literal
from core.utils import op_to_token


def test_op_to_token_mapping():
    assert op_to_token("EQ1") == "Yes"
    assert op_to_token("EQ0") == "NO"
    assert op_to_token("NEQ1") == "Not Yes"


def test_parse_literal_variants():
    assert parse_literal("a", "a").op == "EQ1"
    assert parse_literal("a=1", "a").op == "EQ1"
    assert parse_literal("a=0", "a").op == "EQ0"
    assert parse_literal("!a", "a").op == "NEQ1"
    assert parse_literal("a<>1", "a").op == "NEQ1"
    assert parse_literal("a!=1", "a").op == "NEQ1"


def test_parse_literal_unsupported_operators():
    with pytest.raises(FormulaParseError):
        parse_literal("a<=1", "a")
    with pytest.raises(FormulaParseError):
        parse_literal("a>=1", "a")
