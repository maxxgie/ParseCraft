"""Top-down parsing package.

Exposes recursive descent, backtracking recursive descent, and LL(1)/predictive
parsing behind a small, uniform API.
"""

from core.topdown.backtracking import BacktrackingRecursiveDescentParser
from core.topdown.common import (
    END_MARKER,
    EPSILON,
    TOPDOWN_METHODS,
    LL1Conflict,
    TopDownResult,
    TopDownStep,
)
from core.topdown.engine import analyze_topdown, simulate_topdown
from core.topdown.ll1 import LL1Table, build_ll1_table, parse_predictive
from core.topdown.recursive_descent import RecursiveDescentParser

__all__ = [
    "END_MARKER",
    "EPSILON",
    "TOPDOWN_METHODS",
    "LL1Conflict",
    "TopDownResult",
    "TopDownStep",
    "LL1Table",
    "RecursiveDescentParser",
    "BacktrackingRecursiveDescentParser",
    "build_ll1_table",
    "parse_predictive",
    "analyze_topdown",
    "simulate_topdown",
]