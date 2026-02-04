from __future__ import annotations

from core.formula_parser import AndNode, AstNode, LiteralNode, NotNode, OrNode, FormulaParseError
from core.models import LiteralModel
from core.utils import natural_key


OP_ORDER = {"EQ0": 0, "EQ1": 1, "NEQ1": 2}


def negate_literal(literal: LiteralModel) -> LiteralModel:
    if literal.op == "EQ1":
        return LiteralModel(id=literal.id, display_name=literal.display_name, op="NEQ1")
    if literal.op == "NEQ1":
        return LiteralModel(id=literal.id, display_name=literal.display_name, op="EQ1")
    raise FormulaParseError(f"Negation of literal '{literal.id}=0' is not supported")


def to_nnf(node: AstNode) -> AstNode:
    if isinstance(node, LiteralNode):
        return node
    if isinstance(node, NotNode):
        child = node.child
        if isinstance(child, LiteralNode):
            return LiteralNode(negate_literal(child.literal))
        if isinstance(child, NotNode):
            return to_nnf(child.child)
        if isinstance(child, AndNode):
            return OrNode(to_nnf(NotNode(child.left)), to_nnf(NotNode(child.right)))
        if isinstance(child, OrNode):
            return AndNode(to_nnf(NotNode(child.left)), to_nnf(NotNode(child.right)))
    if isinstance(node, AndNode):
        return AndNode(to_nnf(node.left), to_nnf(node.right))
    if isinstance(node, OrNode):
        return OrNode(to_nnf(node.left), to_nnf(node.right))
    raise FormulaParseError("Unsupported AST node")


def distribute_and(left: list[list[LiteralModel]], right: list[list[LiteralModel]]) -> list[list[LiteralModel]]:
    clauses: list[list[LiteralModel]] = []
    for l_clause in left:
        for r_clause in right:
            clauses.append(l_clause + r_clause)
    return clauses


def to_dnf(node: AstNode) -> list[list[LiteralModel]]:
    node = to_nnf(node)
    if isinstance(node, LiteralNode):
        return [[node.literal]]
    if isinstance(node, OrNode):
        return to_dnf(node.left) + to_dnf(node.right)
    if isinstance(node, AndNode):
        return distribute_and(to_dnf(node.left), to_dnf(node.right))
    raise FormulaParseError("Unsupported AST node")


def normalize_dnf(clauses: list[list[LiteralModel]]) -> list[list[LiteralModel]]:
    normalized: list[list[LiteralModel]] = []
    seen = set()
    for clause in clauses:
        by_id: dict[str, LiteralModel] = {}
        contradiction = False
        for literal in clause:
            existing = by_id.get(literal.id)
            if existing:
                if existing.op != literal.op:
                    contradiction = True
                    break
                continue
            by_id[literal.id] = literal
        if contradiction:
            continue
        ordered = sorted(by_id.values(), key=lambda lit: (natural_key(lit.id), OP_ORDER[lit.op]))
        signature = tuple((lit.id, lit.op) for lit in ordered)
        if signature in seen:
            continue
        seen.add(signature)
        normalized.append(ordered)
    normalized.sort(key=lambda clause: [(natural_key(lit.id), OP_ORDER[lit.op]) for lit in clause])
    return normalized
