"""Precedence and associativity declarations (yacc-style).

Grammars may begin with lines such as::

    %left '+' '-'
    %left '*' '/'
    %right '^'
    %nonassoc '==' '!='

Each directive line increases the precedence level (later lines bind tighter).
The precedence of a production is the precedence of its right-most terminal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Sequence

from core.logging_config import get_logger

logger = get_logger(__name__)

LEFT = "left"
RIGHT = "right"
NONASSOC = "nonassoc"

_DIRECTIVES = {"%left": LEFT, "%right": RIGHT, "%nonassoc": NONASSOC}


@dataclass
class PrecedenceInfo:
    """Precedence levels and associativity for terminals.

    Attributes:
        terminal_level: Mapping ``terminal -> level`` (higher binds tighter).
        associativity: Mapping ``terminal -> left|right|nonassoc``.
    """

    terminal_level: Dict[str, int] = field(default_factory=dict)
    associativity: Dict[str, str] = field(default_factory=dict)

    def level(self, terminal: str) -> Optional[int]:
        """Return the precedence level of a terminal, or ``None``."""
        return self.terminal_level.get(terminal)

    def assoc(self, terminal: str) -> str:
        """Return the associativity of a terminal (default ``nonassoc``)."""
        return self.associativity.get(terminal, NONASSOC)

    def production_level(self, rhs: Sequence[str]) -> Optional[int]:
        """Return the precedence level of a production body.

        Uses the right-most terminal in the body; returns ``None`` if the body
        contains no terminal with a declared precedence.
        """
        for symbol in reversed(rhs):
            if symbol in self.terminal_level:
                return self.terminal_level[symbol]
        return None

    def __bool__(self) -> bool:
        return bool(self.terminal_level)

    def __len__(self) -> int:
        return len(self.terminal_level)


def parse_precedence(text: str) -> PrecedenceInfo:
    """Extract precedence/associativity declarations from grammar text.

    Args:
        text: Grammar text that may contain ``%left``/``%right``/``%nonassoc``
            lines.

    Returns:
        A :class:`PrecedenceInfo` (empty when no declarations are present).
    """
    info = PrecedenceInfo()
    level = 0
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or not line.startswith("%"):
            continue
        parts = line.split()
        directive = parts[0]
        assoc = _DIRECTIVES.get(directive)
        if assoc is None:
            continue
        level += 1
        for symbol in parts[1:]:
            info.terminal_level[symbol] = level
            info.associativity[symbol] = assoc
    logger.debug("Parsed %d precedence declarations", len(info))
    return info