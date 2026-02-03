from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from core.models import LiteralModel, LiteralOp


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


TOKEN_PATTERN = re.compile(r"(\()|(\))|(!)|\b(AND|OR|NOT)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Token:
    type: str
    value: str


def tokenize(formula: str) -> list[Token]:
    tokens: list[Token] = []
    idx = 0
    for match in TOKEN_PATTERN.finditer(formula):
        start, end = match.span()
        if start > idx:
            literal_text = formula[idx:start].strip()
            if literal_text:
                tokens.append(Token("LITERAL", literal_text))
        if match.group(1):
            tokens.append(Token("LPAREN", "("))
        elif match.group(2):
            tokens.append(Token("RPAREN", ")"))
        elif match.group(3):
            tokens.append(Token("NOT", "!"))
        elif match.group(4):
            tokens.append(Token(match.group(4).upper(), match.group(4).upper()))
        idx = end
    if idx < len(formula):
        literal_text = formula[idx:].strip()
        if literal_text:
            tokens.append(Token("LITERAL", literal_text))
    return tokens


class Parser:
    def __init__(self, tokens: list[Token], literal_parser):
        self.tokens = tokens
        self.position = 0
        self.literal_parser = literal_parser

    def current(self) -> Token | None:
        if self.position >= len(self.tokens):
            return None
        return self.tokens[self.position]

    def consume(self, expected_type: str | None = None) -> Token:
        token = self.current()
        if token is None:
            raise FormulaParseError("Unexpected end of formula")
        if expected_type and token.type != expected_type:
            raise FormulaParseError(f"Expected {expected_type} but got {token.type}")
        self.position += 1
        return token

    def parse(self) -> AstNode:
        node = self.parse_expr()
        if self.current() is not None:
            raise FormulaParseError(f"Unexpected token {self.current().value}")
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
            raise FormulaParseError("Unexpected end of formula")
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
            return LiteralNode(self.literal_parser(literal_token.value))
        raise FormulaParseError(f"Unexpected token {token.value}")


def parse_literal(raw_literal: str, display_name: str) -> LiteralModel:
    text = raw_literal.strip()
    if re.search(r"[<>]=|>=|<=", text):
        raise FormulaParseError(f"Unsupported comparison in literal: {text}")
    if re.search(r"[<>]", text) and not re.search(r"<>1$", text):
        raise FormulaParseError(f"Unsupported comparison in literal: {text}")
    if re.search(r"\bXOR\b|\bIF\b", text, re.IGNORECASE):
        raise FormulaParseError(f"Unsupported operator in literal: {text}")

    op: LiteralOp
    identifier: str

    if text.startswith("!"):
        identifier = text[1:].strip()
        op = "NEQ1"
    elif re.search(r"<>1$", text) or re.search(r"!=1$", text):
        identifier = re.sub(r"(<>1|!=1)$", "", text).strip()
        op = "NEQ1"
    elif re.search(r"=0$", text):
        identifier = text[: text.rfind("=")].strip()
        op = "EQ0"
    elif re.search(r"=1$", text):
        identifier = text[: text.rfind("=")].strip()
        op = "EQ1"
    else:
        identifier = text
        op = "EQ1"

    if not identifier:
        raise FormulaParseError("Literal missing identifier")

    return LiteralModel(id=identifier, display_name=display_name, op=op)


def parse_formula(formula: str) -> AstNode:
    tokens = tokenize(formula)
    if not tokens:
        raise FormulaParseError("Formula is empty")
    parser = Parser(tokens, lambda value: parse_literal(value, value))
    return parser.parse()


def parse_formula_with_literal_parser(formula: str, literal_parser) -> AstNode:
    tokens = tokenize(formula)
    if not tokens:
        raise FormulaParseError("Formula is empty")
    parser = Parser(tokens, literal_parser)
    return parser.parse()


def iterate_literals(node: AstNode) -> Iterable[LiteralNode]:
    if isinstance(node, LiteralNode):
        yield node
    elif isinstance(node, NotNode):
        yield from iterate_literals(node.child)
    elif isinstance(node, (AndNode, OrNode)):
        yield from iterate_literals(node.left)
        yield from iterate_literals(node.right)