"""Grammar data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Grammar:
    """Represents a context-free grammar.

    Attributes:
        start_symbol: The start symbol of the grammar.
        productions: Dictionary mapping non-terminals to lists of production
            bodies. Each production body is a list of symbols.
        terminals: Set of terminal symbols.
        non_terminals: Set of non-terminal symbols.
        duplicates: Human-readable duplicate productions detected while parsing
            (kept for reporting; the duplicates themselves are removed).
    """

    start_symbol: str
    productions: Dict[str, List[List[str]]] = field(default_factory=dict)
    terminals: set[str] = field(default_factory=set)
    non_terminals: set[str] = field(default_factory=set)
    duplicates: List[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Compute terminal and non-terminal sets after initialization."""
        if not self.productions:
            return

        # Non-terminals are the keys in productions
        self.non_terminals = set(self.productions.keys())

        # Terminals are symbols that appear in productions but are not
        # non-terminals and are not the epsilon marker
        self.terminals = set()
        for lhs, rhs_list in self.productions.items():
            for rhs in rhs_list:
                for sym in rhs:
                    if sym not in self.non_terminals and sym != "ε":
                        self.terminals.add(sym)

    def get_productions_for(self, non_terminal: str) -> List[List[str]]:
        """Return all production bodies for the given non-terminal.

        Args:
            non_terminal: The non-terminal symbol.

        Returns:
            List of production bodies, or empty list if not found.
        """
        return self.productions.get(non_terminal, [])

    def is_terminal(self, symbol: str) -> bool:
        """Check if a symbol is a terminal.

        Args:
            symbol: The symbol to check.

        Returns:
            True if the symbol is a terminal, False otherwise.
        """
        return symbol in self.terminals

    def is_non_terminal(self, symbol: str) -> bool:
        """Check if a symbol is a non-terminal.

        Args:
            symbol: The symbol to check.

        Returns:
            True if the symbol is a non-terminal, False otherwise.
        """
        return symbol in self.non_terminals

    def is_epsilon(self, symbol: str) -> bool:
        """Check if a symbol is the epsilon marker.

        Args:
            symbol: The symbol to check.

        Returns:
            True if the symbol is 'ε', False otherwise.
        """
        return symbol == "ε"

    def has_production(self, non_terminal: str, body: List[str]) -> bool:
        """Check if a specific production exists.

        Args:
            non_terminal: The left-hand side non-terminal.
            body: The production body.

        Returns:
            True if the production exists, False otherwise.
        """
        return body in self.productions.get(non_terminal, [])

    def add_production(self, non_terminal: str, body: List[str]) -> None:
        """Add a production to the grammar.

        Args:
            non_terminal: The left-hand side non-terminal.
            body: The production body.
        """
        if non_terminal not in self.productions:
            self.productions[non_terminal] = []
        if body not in self.productions[non_terminal]:
            self.productions[non_terminal].append(body)
        # Recompute symbol sets
        self.__post_init__()

    def remove_production(self, non_terminal: str, body: List[str]) -> None:
        """Remove a production from the grammar.

        Args:
            non_terminal: The left-hand side non-terminal.
            body: The production body to remove.
        """
        if non_terminal in self.productions:
            if body in self.productions[non_terminal]:
                self.productions[non_terminal].remove(body)
            if not self.productions[non_terminal]:
                del self.productions[non_terminal]
        self.__post_init__()

    def to_text(self) -> str:
        """Convert the grammar to BNF text representation.

        Returns:
            String representation in BNF format.
        """
        lines = []
        for lhs, rhs_list in self.productions.items():
            alternatives = []
            for rhs in rhs_list:
                if not rhs:
                    alternatives.append("ε")
                else:
                    alternatives.append(" ".join(rhs))
            lines.append(f"{lhs} -> {' | '.join(alternatives)}")
        return "\n".join(lines)

    def to_expanded_text(self) -> str:
        """Return the grammar in expanded, textbook form.

        Every production alternative is written on its own line (``A -> α``);
        the ``|`` shorthand is never used.  The ``->`` arrow is aligned across
        all productions and a blank line separates the alternatives of
        different non-terminals.  An empty right-hand side is rendered as
        ``ε``.

        Returns:
            A multi-line string, one production per line.
        """
        if not self.productions:
            return ""
        width = max(len(lhs) for lhs in self.productions)
        blocks: List[str] = []
        for lhs, rhs_list in self.productions.items():
            pad = lhs.ljust(width)
            lines = [
                f"{pad} -> {' '.join(rhs) if rhs else 'ε'}" for rhs in rhs_list
            ]
            blocks.append("\n".join(lines))
        return "\n\n".join(blocks)

    def __str__(self) -> str:
        return self.to_text()