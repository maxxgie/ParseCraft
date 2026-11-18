"""Shared data types for top-down parsers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from models.parse_tree import ParseTreeNode

END_MARKER = "$"
EPSILON = "ε"

TOPDOWN_METHODS = [
    "Recursive Descent",
    "Backtracking Recursive Descent",
    "Predictive (LL(1))",
    "LL(1)",
]


@dataclass
class TopDownStep:
    """A single configuration captured during a top-down parse.

    Attributes:
        index: Zero-based step number.
        stack: Parse stack (bottom first, top last). For recursive descent
            this is the chain of non-terminals currently being expanded.
        input_remaining: Input tokens not yet consumed, including ``$``.
        action: One of ``call``, ``match``, ``backtrack``, ``predict``,
            ``accept``, ``error``.
        action_text: Human-readable description of the action.
        nonterminal: The non-terminal involved, when relevant.
        production: The production body used, when relevant.
    """

    index: int
    stack: List[str]
    input_remaining: List[str]
    action: str
    action_text: str
    nonterminal: Optional[str] = None
    production: Optional[List[str]] = None


@dataclass
class TopDownResult:
    """Aggregated top-down analysis for a grammar and method.

    Attributes:
        grammar: The grammar that was analysed.
        method: The top-down method name.
        first: FIRST sets for every symbol.
        follow: FOLLOW sets for every non-terminal.
        left_recursion: Whether the grammar has left recursion.
        left_factoring: Whether the grammar has common prefixes.
        ll1_table: The LL(1) table, when the method is table-driven.
        conflicts: LL(1) table conflicts, if any.
        parse_tree: The parse tree of the last simulation, if accepted.
        steps: Trace steps from the last simulation.
        accepted: Whether the last simulation accepted its input.
        error: Error message from the last simulation, if rejected.
        derivation: Successful expansions ``(lhs, rhs)`` in order.
        failed_attempts: Alternative productions that were tried and failed.
        decision_points: Points where a choice between alternatives was made.
    """

    grammar: object
    method: str
    first: Dict[str, Set[str]] = field(default_factory=dict)
    follow: Dict[str, Set[str]] = field(default_factory=dict)
    left_recursion: bool = False
    left_factoring: bool = False
    ll1_table: object = None
    conflicts: List["LL1Conflict"] = field(default_factory=list)
    parse_tree: Optional[ParseTreeNode] = None
    steps: List[TopDownStep] = field(default_factory=list)
    accepted: bool = False
    error: Optional[str] = None
    derivation: List[Tuple[str, List[str]]] = field(default_factory=list)
    failed_attempts: List[Tuple[str, List[str]]] = field(default_factory=list)
    decision_points: List[Tuple[str, int]] = field(default_factory=list)
    transforms: List[str] = field(default_factory=list)
    stages: Dict[str, str] = field(default_factory=dict)
    #: The original grammar exactly as entered by the user (never overwritten).
    #: ``grammar`` is the transformed grammar actually parsed by the top-down
    #: parser (identical to ``original`` when no transforms were applied).
    original: Optional[object] = None

    @property
    def is_ll1(self) -> bool:
        """Return ``True`` when the grammar is LL(1) (no table conflicts)."""
        return not self.conflicts

    @property
    def grammar_text(self) -> str:
        """Return the grammar actually used (after any transformations)."""
        return self.grammar.to_text()


@dataclass
class LL1Conflict:
    """A multiply-defined LL(1) table cell.

    Attributes:
        nonterminal: The non-terminal row.
        terminal: The lookahead terminal column.
        productions: The competing production bodies.
    """

    nonterminal: str
    terminal: str
    productions: List[List[str]]

    def message(self) -> str:
        """Return a human-readable description of the conflict."""
        alts = " / ".join(
            f"{self.nonterminal} -> {' '.join(p) if p else EPSILON}"
            for p in self.productions
        )
        return f"LL(1) conflict on '{self.nonterminal}' with lookahead '{self.terminal}': {alts}"