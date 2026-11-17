"""LL(1) table construction and predictive (stack-based) parsing."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from core.first_follow import (
    compute_first,
    compute_first_of_string,
    compute_follow,
)
from core.logging_config import get_logger
from core.parse_tree import make_leaf
from core.topdown.common import (
    END_MARKER,
    EPSILON,
    LL1Conflict,
    TopDownStep,
)
from models.grammar import Grammar
from models.parse_tree import ParseTreeNode

logger = get_logger(__name__)

MAX_STEPS = 100000


@dataclass
class LL1Table:
    """The LL(1) predictive parsing table.

    Attributes:
        non_terminals: Row labels.
        terminals: Column labels (grammar terminals plus ``$``).
        productions: Indexed list of ``(lhs, body)`` pairs.
        entries: ``(nonterminal, terminal) -> [production index, ...]``.
        conflicts: Cells with more than one production.
    """

    non_terminals: List[str]
    terminals: List[str]
    productions: List[Tuple[str, List[str]]] = field(default_factory=list)
    entries: Dict[Tuple[str, str], List[int]] = field(default_factory=dict)
    conflicts: List[LL1Conflict] = field(default_factory=list)

    def cell(self, nonterminal: str, terminal: str) -> List[int]:
        """Return the production indices stored for a cell."""
        return self.entries.get((nonterminal, terminal), [])


def build_ll1_table(
    grammar: Grammar, first=None, follow=None
) -> LL1Table:
    """Build the LL(1) table for ``grammar``.

    Args:
        grammar: The grammar to tabulate.
        first: Pre-computed FIRST sets.
        follow: Pre-computed FOLLOW sets.

    Returns:
        An :class:`LL1Table` with conflicts recorded.
    """
    first = first if first is not None else compute_first(grammar)
    follow = follow if follow is not None else compute_follow(grammar, first)

    productions: List[Tuple[str, List[str]]] = []
    for nt, bodies in grammar.productions.items():
        for body in bodies:
            productions.append((nt, list(body)))

    terminals = sorted(grammar.terminals) + [END_MARKER]
    entries: Dict[Tuple[str, str], List[int]] = {}

    def add(nonterminal: str, terminal: str, index: int) -> None:
        entries.setdefault((nonterminal, terminal), []).append(index)

    for index, (nt, body) in enumerate(productions):
        first_body = compute_first_of_string(body, first)
        if EPSILON in first_body:
            for terminal in first_body - {EPSILON}:
                add(nt, terminal, index)
            for terminal in follow.get(nt, set()):
                add(nt, terminal, index)
        else:
            for terminal in first_body:
                add(nt, terminal, index)

    conflicts: List[LL1Conflict] = []
    for (nt, terminal), indices in entries.items():
        unique = list(dict.fromkeys(indices))
        if len(unique) > 1:
            bodies = [productions[i][1] for i in unique]
            conflicts.append(LL1Conflict(nt, terminal, bodies))

    logger.info(
        "LL(1) table built: %d rows, %d columns, %d conflict(s)",
        len(grammar.non_terminals),
        len(terminals),
        len(conflicts),
    )
    return LL1Table(
        non_terminals=list(grammar.productions.keys()),
        terminals=terminals,
        productions=productions,
        entries=entries,
        conflicts=conflicts,
    )


@dataclass
class LL1Issue:
    """A validated LL(1) conflict with a classification and a suggested fix.

    Attributes:
        nonterminal: The non-terminal row.
        terminal: The lookahead terminal column.
        kind: ``FIRST/FIRST`` or ``FIRST/FOLLOW``.
        productions: The competing production bodies.
        reason: Why the conflict occurs.
        suggestion: How to fix the grammar.
    """

    nonterminal: str
    terminal: str
    kind: str
    productions: List[List[str]]
    reason: str
    suggestion: str

    def message(self) -> str:
        """Return a human-readable description of the issue."""
        alts = " / ".join(
            f"{self.nonterminal} -> {' '.join(p) if p else EPSILON}"
            for p in self.productions
        )
        return (
            f"M[{self.nonterminal}, {self.terminal}]: {self.kind} conflict "
            f"({alts}). {self.reason} Fix: {self.suggestion}"
        )


def validate_ll1_table(
    table: LL1Table,
    grammar: Grammar,
    first=None,
    follow=None,
) -> List[LL1Issue]:
    """Classify every LL(1) table conflict and suggest a fix.

    Args:
        table: The LL(1) table to validate.
        grammar: The grammar the table was built from.
        first: Pre-computed FIRST sets.
        follow: Pre-computed FOLLOW sets.

    Returns:
        A list of :class:`LL1Issue`; empty means the grammar is LL(1).
    """
    first = first if first is not None else compute_first(grammar)
    follow = follow if follow is not None else compute_follow(grammar, first)

    issues: List[LL1Issue] = []
    for conflict in table.conflicts:
        nt = conflict.nonterminal
        terminal = conflict.terminal
        bodies = conflict.productions

        nullable = [
            b for b in bodies if EPSILON in compute_first_of_string(b, first)
        ]
        if nullable:
            kind = "FIRST/FOLLOW"
            reason = (
                f"'{nt}' has a nullable alternative and another production also "
                f"predicts on '{terminal}' ∈ FOLLOW({nt})."
            )
            suggestion = (
                "Left-factor or restructure the alternatives so the nullable "
                "production's lookahead is disjoint from the others."
            )
        else:
            kind = "FIRST/FIRST"
            reason = (
                f"More than one production of '{nt}' can start with "
                f"'{terminal}' (their FIRST sets overlap)."
            )
            suggestion = (
                "Left-factor the common prefix: A -> α β1 | α β2 becomes "
                "A -> α A', A' -> β1 | β2."
            )
        issues.append(
            LL1Issue(
                nonterminal=nt,
                terminal=terminal,
                kind=kind,
                productions=[list(b) for b in bodies],
                reason=reason,
                suggestion=suggestion,
            )
        )
    return issues


def explain_ll1_cell(
    table: LL1Table,
    grammar: Grammar,
    nonterminal: str,
    terminal: str,
    first=None,
    follow=None,
) -> str:
    """Explain why ``M[nonterminal, terminal]`` holds the productions it does.

    Args:
        table: The LL(1) table.
        grammar: The grammar.
        nonterminal: The row.
        terminal: The column.
        first: Pre-computed FIRST sets.
        follow: Pre-computed FOLLOW sets.

    Returns:
        A multi-line explanation.
    """
    first = first if first is not None else compute_first(grammar)
    follow = follow if follow is not None else compute_follow(grammar, first)

    indices = list(dict.fromkeys(table.cell(nonterminal, terminal)))
    lines: List[str] = [f"M[{nonterminal}, {terminal}]"]

    if not indices:
        lines.append("")
        lines.append("Empty cell: no production of the grammar predicts this lookahead.")
        lines.append(
            f"'{terminal}' is not in the FIRST set of any production of "
            f"'{nonterminal}' (nor in FOLLOW({nonterminal}) for a nullable one)."
        )
        return "\n".join(lines)

    for index in indices:
        nt, body = table.productions[index]
        body_text = " ".join(body) if body else EPSILON
        body_first = compute_first_of_string(body, first)
        lines.append("")
        lines.append(f"Production r{index}: {nt} -> {body_text}")
        if EPSILON in body_first:
            lines.append(
                f"  ε ∈ FIRST({body_text}), so the production is also placed on "
                f"every terminal in FOLLOW({nt})."
            )
        if terminal in body_first - {EPSILON}:
            lines.append(f"  '{terminal}' ∈ FIRST({body_text}).")
        elif EPSILON in body_first and terminal in follow.get(nt, set()):
            lines.append(
                f"  '{terminal}' ∈ FOLLOW({nt}) and the production is nullable."
            )

    if len(indices) > 1:
        lines.append("")
        lines.append(
            f"Conflict: {len(indices)} productions share this cell "
            f"({', '.join('r' + str(i) for i in indices)})."
        )
        issues = {i.terminal: i for i in validate_ll1_table(table, grammar, first, follow)}
        issue = next(
            (i for i in issues.values() if i.nonterminal == nonterminal), None
        )
        if issue is not None:
            lines.append(f"Reason: {issue.reason}")
            lines.append(f"Suggested fix: {issue.suggestion}")

    return "\n".join(lines)


@dataclass
class PredictiveOutcome:
    """Result of a predictive (LL(1)) parse."""

    accepted: bool
    steps: List[TopDownStep] = field(default_factory=list)
    tree: Optional[ParseTreeNode] = None
    error: Optional[str] = None
    derivation: List[Tuple[str, List[str]]] = field(default_factory=list)


def parse_predictive(
    table: LL1Table, grammar: Grammar, tokens: List[str]
) -> PredictiveOutcome:
    """Run a table-driven predictive parser over ``tokens``.

    Args:
        table: The LL(1) table.
        grammar: The grammar (start symbol and terminals).
        tokens: Input terminals.

    Returns:
        A :class:`PredictiveOutcome`.
    """
    steps: List[TopDownStep] = []
    derivation: List[Tuple[str, List[str]]] = []
    start = grammar.start_symbol

    symbol_stack: List[str] = [END_MARKER, start]
    root = ParseTreeNode(symbol=start)
    node_stack: List[Optional[ParseTreeNode]] = [None, root]
    inputs = tokens + [END_MARKER]
    ip = 0
    accepted = False
    error: Optional[str] = None

    def rec(
        action: str,
        text: str,
        nonterminal: Optional[str] = None,
        production: Optional[List[str]] = None,
    ) -> None:
        steps.append(
            TopDownStep(
                index=len(steps),
                stack=list(symbol_stack),
                input_remaining=list(inputs[ip:]),
                action=action,
                action_text=text,
                nonterminal=nonterminal,
                production=production,
            )
        )

    rec("start", "initial configuration")

    while len(steps) <= MAX_STEPS:
        top = symbol_stack[-1]
        lookahead = inputs[ip]

        if top in grammar.non_terminals:
            indices = list(dict.fromkeys(table.cell(top, lookahead)))
            if not indices:
                rec("error", f"no LL(1) rule for '{top}' on '{lookahead}'",
                    nonterminal=top)
                error = (
                    f"LL(1) error: no production for '{top}' "
                    f"with lookahead '{lookahead}'"
                )
                break
            index = indices[0]
            nt, body = table.productions[index]
            nt_node = node_stack[-1]
            symbol_stack.pop()
            node_stack.pop()
            child_nodes: List[ParseTreeNode] = []
            if nt_node is not None:
                if not body:
                    nt_node.add_child(make_leaf(EPSILON, EPSILON))
                for sym in body:
                    child = ParseTreeNode(symbol=sym)
                    nt_node.add_child(child)
                    child_nodes.append(child)
            for sym, child in reversed(list(zip(body, child_nodes))):
                symbol_stack.append(sym)
                node_stack.append(child)
            derivation.append((nt, body))
            rec(
                "predict",
                f"predict {nt} -> {' '.join(body) if body else EPSILON}",
                nonterminal=nt,
                production=body,
            )
            continue

        if top == END_MARKER:
            if lookahead == END_MARKER:
                rec("accept", "accept")
                accepted = True
                break
            rec("error", f"expected end of input but found '{lookahead}'")
            error = f"Unexpected token '{lookahead}' after end of input"
            break

        # Terminal expected.
        if top == lookahead:
            current = node_stack[-1]
            if current is not None:
                current.value = lookahead
            symbol_stack.pop()
            node_stack.pop()
            ip += 1
            rec("match", f"match '{lookahead}'")
        else:
            rec("error", f"expected '{top}' but found '{lookahead}'")
            error = f"Syntax error: expected '{top}' but found '{lookahead}'"
            break

    if not accepted and error is None:
        error = "Parse did not complete (step limit exceeded)"

    return PredictiveOutcome(
        accepted=accepted,
        steps=steps,
        tree=root if accepted else None,
        error=None if accepted else error,
        derivation=derivation,
    )