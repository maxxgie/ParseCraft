"""Recursive descent parser with call tracing, derivation, and parse tree."""

from __future__ import annotations

from typing import List, Optional, Tuple

from core.first_follow import compute_first, compute_follow
from core.logging_config import get_logger
from core.parse_tree import make_internal, make_leaf
from core.topdown.common import END_MARKER, EPSILON, TopDownStep
from models.grammar import Grammar
from models.parse_tree import ParseTreeNode

logger = get_logger(__name__)

MAX_DEPTH = 2000


class RecursiveDescentParser:
    """A recursive descent parser built from grammar productions.

    Each non-terminal becomes a function that tries its productions in order.
    Terminals are matched against the current input token. The parser records a
    full trace (calls, matches, backtracks), the derivation, failed attempts,
    and decision points, and builds a parse tree on success.
    """

    def __init__(
        self,
        grammar: Grammar,
        first=None,
        follow=None,
        verbose_decisions: bool = False,
    ) -> None:
        self.grammar = grammar
        self.first = first if first is not None else compute_first(grammar)
        self.follow = (
            follow if follow is not None else compute_follow(grammar, self.first)
        )
        self.verbose_decisions = verbose_decisions
        self.steps: List[TopDownStep] = []
        self.derivation: List[Tuple[str, List[str]]] = []
        self.failed_attempts: List[Tuple[str, List[str]]] = []
        self.decision_points: List[Tuple[str, int]] = []
        self._chain: List[str] = []
        self._tokens: List[str] = []
        self._funcs = {nt: self._make_func(nt) for nt in grammar.non_terminals}

    # ------------------------------------------------------------------
    def _record(
        self,
        action: str,
        text: str,
        tokens: List[str],
        pos: int,
        nonterminal: Optional[str] = None,
        production: Optional[List[str]] = None,
    ) -> None:
        self.steps.append(
            TopDownStep(
                index=len(self.steps),
                stack=list(self._chain),
                input_remaining=list(tokens[pos:]) + [END_MARKER],
                action=action,
                action_text=text,
                nonterminal=nonterminal,
                production=production,
            )
        )

    def _make_func(self, nt: str):
        alternatives = self.grammar.productions[nt]

        def func(tokens: List[str], pos: int, depth: int):
            self._record("call", f"call {nt}", tokens, pos, nonterminal=nt)
            self._chain.append(nt)
            if len(alternatives) > 1:
                self.decision_points.append((nt, len(alternatives)))
                if self.verbose_decisions:
                    self._record(
                        "decision",
                        f"choose a production for {nt} ({len(alternatives)} options)",
                        tokens,
                        pos,
                        nonterminal=nt,
                    )
            for alt in alternatives:
                ok, newpos, node = self._match_alternative(
                    nt, alt, tokens, pos, depth
                )
                if ok:
                    self._chain.pop()
                    self.derivation.append((nt, alt))
                    return True, newpos, node
                self.failed_attempts.append((nt, alt))
                self._record(
                    "backtrack",
                    f"{nt} -> {' '.join(alt) if alt else EPSILON} failed; backtrack",
                    tokens,
                    pos,
                    nonterminal=nt,
                    production=alt,
                )
            self._chain.pop()
            self._record(
                "error",
                f"no production of {nt} matches here",
                tokens,
                pos,
                nonterminal=nt,
            )
            return False, pos, None

        return func

    def _match_alternative(
        self,
        nt: str,
        alt: List[str],
        tokens: List[str],
        pos: int,
        depth: int,
    ):
        cur = pos
        children: List[ParseTreeNode] = []
        for sym in alt:
            ok, newpos, node = self._match_symbol(sym, tokens, cur, depth)
            if not ok:
                return False, pos, None
            children.append(node)
            cur = newpos
        if not alt:
            children = [make_leaf(EPSILON, EPSILON)]
        node = make_internal(nt, children)
        self._record(
            "match",
            f"{nt} -> {' '.join(alt) if alt else EPSILON}",
            tokens,
            cur,
            nonterminal=nt,
            production=alt,
        )
        return True, cur, node

    def _match_symbol(self, sym: str, tokens: List[str], pos: int, depth: int):
        if depth > MAX_DEPTH:
            self._record(
                "error",
                "recursion depth exceeded (possible left recursion)",
                tokens,
                pos,
            )
            return False, pos, None
        if sym in self.grammar.non_terminals:
            return self._funcs[sym](tokens, pos, depth + 1)
        if pos < len(tokens) and tokens[pos] == sym:
            self._record("match", f"match '{sym}'", tokens, pos + 1)
            return True, pos + 1, make_leaf(sym, sym)
        found = tokens[pos] if pos < len(tokens) else END_MARKER
        self._record(
            "error",
            f"expected '{sym}' but found '{found}'",
            tokens,
            pos,
        )
        return False, pos, None

    # ------------------------------------------------------------------
    def parse(
        self, tokens: List[str]
    ) -> Tuple[bool, Optional[ParseTreeNode], Optional[str]]:
        """Parse ``tokens`` and return ``(accepted, tree, error)``."""
        self.steps = []
        self.derivation = []
        self.failed_attempts = []
        self.decision_points = []
        self._chain = []
        self._tokens = tokens

        start = self.grammar.start_symbol
        ok, newpos, node = self._funcs[start](tokens, 0, 0)

        if ok and newpos == len(tokens):
            self._record("accept", "accept", tokens, newpos)
            return True, node, None

        if ok and newpos < len(tokens):
            extra = tokens[newpos]
            self._record(
                "error",
                f"unexpected token '{extra}' after a complete parse",
                tokens,
                newpos,
            )
            return False, None, f"Unexpected token '{extra}' after end of input"

        found = tokens[min(newpos, len(tokens) - 1)] if tokens else END_MARKER
        message = f"Could not derive input; error near '{found}'"
        return False, None, message