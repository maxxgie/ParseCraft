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