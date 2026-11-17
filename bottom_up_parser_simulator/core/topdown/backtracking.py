"""Backtracking recursive descent parser.

Behaves like :class:`~core.topdown.recursive_descent.RecursiveDescentParser`
but records the decision points and failed attempts explicitly so the GUI can
visualize backtracking paths.
"""

from __future__ import annotations

from core.topdown.recursive_descent import RecursiveDescentParser


class BacktrackingRecursiveDescentParser(RecursiveDescentParser):
    """Recursive descent that highlights decisions and backtracking."""

    def __init__(self, grammar, first=None, follow=None) -> None:
        super().__init__(grammar, first, follow, verbose_decisions=True)