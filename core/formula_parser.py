from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Iterable

from core.models import LiteralModel, LiteralOp
from core.operator_config import OperatorConfig, load_operator_config

logger = logging.getLogger(__name__)


class FormulaParseError(ValueError):
    pass


@dataclass(frozen=True)
class AstNode:
    pass


@dataclass(frozen=True)
class LiteralNode(AstNode):
    literal: LiteralModel


@dataclass(frozen=True)
class NotNode(AstNode):
    child: AstNode


@dataclass(frozen=True)
class AndNode(AstNode):
    left: AstNode
    right: AstNode


@dataclass(frozen=True)
class OrNode(AstNode):
    left: AstNode
    right: AstNode


@dataclass(frozen=True)
class Token:
    type: str
    value: str
    pos: int


_IDENTIFIER_RE = re.compile(r"[A-Za-z0-9_]+")


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch == "_"


def _near(formula: str, pos: int, *, window: int = 40) -> str:
    start = max(0, pos - window)
    end = min(len(formula), pos + window)
    snippet = formula[start:end]
    return snippet.replace("\n", " ").replace("\r", " ").replace("\t", " ")


def _matches_at(formula: str, pos: int, token: str, *, is_word: bool) -> bool:
    if is_word:
        end = pos + len(token)
        if end > len(formula):
            return False
        if formula[pos:end].upper() != token:
            return False
        before_ok = pos == 0 or not _is_word_char(formula[pos - 1])
        after_ok = end == len(formula) or not _is_word_char(formula[end])
        return before_ok and after_ok
    return formula.startswith(token, pos)


def tokenize(
    formula: str,
    op_config: OperatorConfig | None = None,
    *,
    log_extra: dict[str, str] | None = None,
) -> list[Token]:
    """Tokenize a formula using the operator config.

    Supported (configurable) expression operators:
    - AND / OR / NOT
    - LPAREN / RPAREN

    Special logs:
    - TOKENIZE_START / TOKENIZE_OK / TOKENIZE_FAILED
    """
    op_config = op_config or load_operator_config(log_extra=log_extra)

    if log_extra:
        logger.info("TOKENIZE_START: len=%d", len(formula), extra=log_extra)
    else:
        logger.info("TOKENIZE_START: len=%d", len(formula))

    tokens: list[Token] = []
    i = 0
    while i < len(formula):
        if formula[i].isspace():
            i += 1
            continue

        # Operators (longest-match-first)
        matched_op = False
        for op_token, op_type, is_word in op_config.expression_ops:
            if _matches_at(formula, i, op_token, is_word=is_word):
                tokens.append(Token(op_type, op_token, i))
                i += len(op_token)
                matched_op = True
                break
        if matched_op:
            continue

        # Literal: optional leading '!' + identifier + optional (NEQ|EQ)(0|1)
        start = i
        if formula[i] == "!":
            i += 1

        m = _IDENTIFIER_RE.match(formula, i)
        if not m:
            ch = formula[start]
            near = _near(formula, start)
            summary = op_config.summary()
            msg = f"TOKENIZE_FAILED: unknown character '{ch}' at pos={start} near='{near}' expected_ops={summary}"
            if log_extra:
                logger.error(msg, extra=log_extra)
            else:
                logger.error(msg)
            raise FormulaParseError(msg)
        i = m.end()

        # Comparators are handled inside literals, but still configurable.
        comp_matched = None
        for comp in list(op_config.neq_ops) + list(op_config.eq_ops):
            if formula.startswith(comp, i):
                comp_matched = comp
                i += len(comp)
                break
        if comp_matched is not None:
            if i >= len(formula) or formula[i] not in "01":
                got = "<eof>" if i >= len(formula) else formula[i]
                near = _near(formula, i)
                summary = op_config.summary()
                msg = (
                    f"TOKENIZE_FAILED: expected 0/1 after '{comp_matched}' at pos={i} "
                    f"got='{got}' near='{near}' expected_ops={summary}"
                )
                if log_extra:
                    logger.error(msg, extra=log_extra)
                else:
                    logger.error(msg)
                raise FormulaParseError(msg)
            i += 1

        tokens.append(Token("LITERAL", formula[start:i], start))

    if log_extra:
        logger.info("TOKENIZE_OK: tokens=%d", len(tokens), extra=log_extra)
    else:
        logger.info("TOKENIZE_OK: tokens=%d", len(tokens))

    return tokens


class Parser:
    def __init__(self, tokens: list[Token], literal_parser, formula: str):
        self.tokens = tokens
        self.position = 0
        self.literal_parser = literal_parser
        self.formula = formula

    def _error(self, message: str, pos: int) -> FormulaParseError:
        near = _near(self.formula, pos)
        return FormulaParseError(f"PARSE_FAILED: {message} at pos={pos} near='{near}'")

    def current(self) -> Token | None:
        if self.position >= len(self.tokens):
            return None
        return self.tokens[self.position]

    def consume(self, expected_type: str | None = None) -> Token:
        token = self.current()
        if token is None:
            raise self._error("unexpected end of formula", len(self.formula))
        if expected_type and token.type != expected_type:
            raise self._error(
                f"expected {expected_type} but got {token.type} ('{token.value}')",
                token.pos,
            )
        self.position += 1
        return token

    def parse(self) -> AstNode:
        node = self.parse_expr()
        if self.current() is not None:
            token = self.current()
            assert token is not None
            raise self._error(f"unexpected token '{token.value}'", token.pos)
        return node

    def parse_expr(self) -> AstNode:
        node = self.parse_term()
        while self.current() and self.current().type == "OR":
            self.consume("OR")
            node = OrNode(node, self.parse_term())
        return node

    def parse_term(self) -> AstNode:
        node = self.parse_factor()
        while self.current() and self.current().type == "AND":
            self.consume("AND")
            node = AndNode(node, self.parse_factor())
        return node

    def parse_factor(self) -> AstNode:
        token = self.current()
        if token is None:
            raise self._error("unexpected end of formula", len(self.formula))
        if token.type == "NOT":
            self.consume("NOT")
            return NotNode(self.parse_factor())
        if token.type == "LPAREN":
            self.consume("LPAREN")
            node = self.parse_expr()
            self.consume("RPAREN")
            return node
        if token.type == "LITERAL":
            literal_token = self.consume("LITERAL")
            try:
                literal = self.literal_parser(literal_token.value)
            except FormulaParseError as exc:
                # Add position/context to semantic literal errors (e.g. invalid comparisons).
                raise FormulaParseError(
                    f"LITERAL_FAILED: {exc} at pos={literal_token.pos} near='{_near(self.formula, literal_token.pos)}'"
                ) from exc
            return LiteralNode(literal)
        raise self._error(f"unexpected token '{token.value}'", token.pos)


def parse_literal(raw_literal: str, display_name: str, op_config: OperatorConfig | None = None) -> LiteralModel:
    op_config = op_config or load_operator_config()
    text = raw_literal.strip()
    if re.search(r"[<>]=|>=|<=", text):
        raise FormulaParseError(f"Unsupported comparison in literal: {text}")
    if re.search(r"[<>]", text):
        # We only support NEQ comparisons (<> / !=) against 1. "<>0" must hard-fail explicitly.
        for neq in op_config.neq_ops:
            if text.endswith(f"{neq}0"):
                raise FormulaParseError(f"Invalid comparison in literal: '{neq}0' is not allowed (use '{neq}1'). Literal: {text}")
    if re.search(r"\bXOR\b|\bIF\b", text, re.IGNORECASE):
        raise FormulaParseError(f"Unsupported operator in literal: {text}")

    op: LiteralOp
    identifier: str

    if text.startswith("!"):
        identifier = text[1:].strip()
        op = "NEQ1"
    else:
        identifier = text
        # NEQ first (e.g. "!=" should not be misread as "=")
        for neq in op_config.neq_ops:
            if identifier.endswith(f"{neq}1"):
                identifier = identifier[: -len(neq) - 1].strip()
                op = "NEQ1"
                break
        else:
            for eq in op_config.eq_ops:
                if identifier.endswith(f"{eq}0"):
                    identifier = identifier[: -len(eq) - 1].strip()
                    op = "EQ0"
                    break
                if identifier.endswith(f"{eq}1"):
                    identifier = identifier[: -len(eq) - 1].strip()
                    op = "EQ1"
                    break
            else:
                op = "EQ1"

    if not identifier:
        raise FormulaParseError("Literal missing identifier")

    if not _IDENTIFIER_RE.fullmatch(identifier):
        raise FormulaParseError(f"Invalid literal identifier: {identifier!r} (expected [A-Za-z0-9_]+)")

    return LiteralModel(id=identifier, display_name=display_name, op=op)


def parse_formula(formula: str, op_config: OperatorConfig | None = None) -> AstNode:
    op_config = op_config or load_operator_config()
    return parse_formula_with_literal_parser(formula, lambda value: parse_literal(value, value, op_config), op_config=op_config)


def parse_formula_with_literal_parser(
    formula: str,
    literal_parser,
    op_config: OperatorConfig | None = None,
    *,
    log_extra: dict[str, str] | None = None,
) -> AstNode:
    """Parse a formula with a custom literal parser.

    Special logs:
    - PARSE_START / PARSE_OK / PARSE_FAILED
    """
    op_config = op_config or load_operator_config(log_extra=log_extra)

    if log_extra:
        logger.info("PARSE_START: len=%d", len(formula), extra=log_extra)
    else:
        logger.info("PARSE_START: len=%d", len(formula))

    tokens = tokenize(formula, op_config, log_extra=log_extra)
    if not tokens:
        raise FormulaParseError("PARSE_FAILED: formula is empty")
    parser = Parser(tokens, literal_parser, formula)
    try:
        node = parser.parse()
    except FormulaParseError as exc:
        token_dump = " ".join(f"{t.type}:{t.value}@{t.pos}" for t in tokens[:200])
        if len(tokens) > 200:
            token_dump += " ... (truncated)"
        prefix = "" if str(exc).startswith("PARSE_FAILED") else "PARSE_FAILED: "
        if log_extra:
            logger.error("%s%s token_dump=%s", prefix, exc, token_dump, extra=log_extra)
        else:
            logger.error("%s%s token_dump=%s", prefix, exc, token_dump)
        raise

    if log_extra:
        logger.info("PARSE_OK: tokens=%d", len(tokens), extra=log_extra)
    else:
        logger.info("PARSE_OK: tokens=%d", len(tokens))

    return node


def iterate_literals(node: AstNode) -> Iterable[LiteralNode]:
    if isinstance(node, LiteralNode):
        yield node
    elif isinstance(node, NotNode):
        yield from iterate_literals(node.child)
    elif isinstance(node, (AndNode, OrNode)):
        yield from iterate_literals(node.left)
        yield from iterate_literals(node.right)
