"""Grammar parser for BNF format input."""

from __future__ import annotations

from typing import Dict, List, Set

from core.logging_config import get_logger
from models.grammar import Grammar

logger = get_logger(__name__)


def _defined_non_terminals(text: str) -> Set[str]:
    """Return every non-terminal defined on a left-hand side.

    A pre-scan is needed so that right-hand-side tokenization can tell a
    multi-character non-terminal (e.g. ``Expr``) apart from a run of single
    symbols written without spaces (e.g. ``MA`` meaning ``M A``).
    """
    defined: Set[str] = set()
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line or line.startswith("#") or line.startswith("%"):
            continue
        if "->" not in line:
            continue
        lhs = line.split("->", 1)[0].strip()
        if lhs and " " not in lhs and "|" not in lhs:
            defined.add(lhs)
    return defined


def _expand_token(token: str, non_terminals: Set[str]) -> List[str]:
    """Expand a whitespace-delimited RHS token into grammar symbols.

    Rules:

    * A token that names a non-terminal is kept whole (``Expr`` stays ``Expr``).
    * A token made only of uppercase letters is split into single symbols, so
      ``MA`` becomes ``M`` and ``A``. This lets ``C -> MA`` mean ``C -> M A``
      without requiring spaces, while word terminals such as ``id`` or ``if``
      (lower-case) and mixed-case names are left untouched.
    * Everything else (operators, ``id``, ``E'`` ...) is kept whole.
    """
    if token in non_terminals:
        return [token]
    if len(token) > 1 and token.isalpha() and token.isupper():
        return list(token)
    return [token]


class GrammarParseError(Exception):
    """Exception raised when grammar parsing fails."""

    def __init__(self, message: str, line_number: int | None = None) -> None:
        """Initialize the error.

        Args:
            message: The error message.
            line_number: The line number where the error occurred.
        """
        if line_number is not None:
            super().__init__(f"Error:\n{message}\nLine {line_number}:")
        else:
            super().__init__(f"Error:\n{message}")
        self.message = message
        self.line_number = line_number


def parse_grammar(text: str) -> Grammar:
    """Parse a BNF grammar string into a Grammar object.

    Args:
        text: The grammar text in BNF format.

    Returns:
        A Grammar object.

    Raises:
        GrammarParseError: If the grammar is invalid.
    """
    if not text or not text.strip():
        raise GrammarParseError("Grammar cannot be empty.")

    productions: Dict[str, List[List[str]]] = {}
    start_symbol: str | None = None
    duplicates: List[str] = []
    defined_non_terminals = _defined_non_terminals(text)

    lines = text.split("\n")
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()

        # Skip empty lines, comments, and precedence/associativity declarations
        if not line or line.startswith("#") or line.startswith("%"):
            continue

        # Check for the production arrow, distinguishing an invalid operator.
        if "->" not in line:
            if "=" in line:
                raise GrammarParseError(
                    "Invalid production operator; expected '->'.", line_number
                )
            raise GrammarParseError(
                f"Missing arrow in production: '{line}'", line_number
            )

        # Split into left-hand side and right-hand side
        parts = line.split("->", 1)
        if len(parts) != 2:
            raise GrammarParseError(
                f"Invalid production format: '{line}'", line_number
            )

        lhs = parts[0].strip()
        rhs_text = parts[1].strip()

        # Validate left-hand side
        if not lhs:
            raise GrammarParseError(
                "Production has no left-hand non-terminal.", line_number
            )
        if " " in lhs or "|" in lhs:
            raise GrammarParseError(
                f"Invalid non-terminal name: '{lhs}'", line_number
            )

        # A production with nothing after the arrow is an error (epsilon must
        # be written explicitly as ``ε`` or as an empty alternative ``A -> a |``).
        if rhs_text == "":
            raise GrammarParseError(
                f"Production {lhs} has no derivation.", line_number
            )

        # Track defined non-terminals and set the start symbol.
        if start_symbol is None:
            start_symbol = lhs

        # Parse right-hand side alternatives.
        alternatives = rhs_text.split("|")
        for alt in alternatives:
            alt = alt.strip()
            if not alt:
                # Empty alternative is epsilon.
                key: tuple = ()
                body: List[str] = []
            else:
                symbols: List[str] = []
                for token in alt.split():
                    symbols.extend(_expand_token(token, defined_non_terminals))
                for sym in symbols:
                    if sym == "ε":
                        # Epsilon is only valid as the sole symbol.
                        if len(symbols) > 1:
                            raise GrammarParseError(
                                "Epsilon 'ε' must be the only symbol in "
                                f"alternative: '{alt}'",
                                line_number,
                            )
                    elif sym == "->":
                        raise GrammarParseError(
                            f"Invalid symbol '->' in production: '{alt}'",
                            line_number,
                        )
                # An explicit 'ε' is normalised to an empty body.
                if symbols == ["ε"]:
                    key = ()
                    body = []
                else:
                    body = symbols
                    key = tuple(symbols)

            existing = productions.setdefault(lhs, [])
            if key in (tuple(b) for b in existing):
                duplicates.append(
                    f"{lhs} -> {' '.join(body) if body else 'ε'}"
                )
                continue
            existing.append(body)

    if start_symbol is None:
        raise GrammarParseError("No productions found in grammar")

    # Any symbol that appears on a right-hand side but is not defined as a
    # left-hand side is a terminal (e.g. '+', 'id', '(', ')'). This is valid
    # and does not require any additional declaration.

    grammar = Grammar(
        start_symbol=start_symbol,
        productions=productions,
        duplicates=duplicates,
    )
    if duplicates:
        logger.warning(
            "Grammar parsed with %d duplicate production(s)", len(duplicates)
        )
    logger.info("Grammar parsed successfully: %d non-terminals", len(productions))
    return grammar


def validate_grammar(grammar: Grammar) -> List[str]:
    """Validate a grammar and return a list of warnings/errors.

    Args:
        grammar: The grammar to validate.

    Returns:
        List of validation messages.
    """
    errors: List[str] = []

    if not grammar.productions:
        errors.append("Grammar has no productions")
        return errors

    # Check if start symbol has productions
    if grammar.start_symbol not in grammar.productions:
        errors.append(f"Start symbol '{grammar.start_symbol}' has no productions")

    # Check for unreachable non-terminals
    reachable = set()
    reachable.add(grammar.start_symbol)
    changed = True
    while changed:
        changed = False
        for nt in list(reachable):
            for rhs in grammar.productions.get(nt, []):
                for sym in rhs:
                    if sym in grammar.non_terminals and sym not in reachable:
                        reachable.add(sym)
                        changed = True

    unreachable = grammar.non_terminals - reachable
    for nt in unreachable:
        errors.append(f"Non-terminal '{nt}' is unreachable from start symbol")

    # Check for non-productive non-terminals
    productive = set()
    changed = True
    while changed:
        changed = False
        for nt, rhs_list in grammar.productions.items():
            if nt in productive:
                continue
            for rhs in rhs_list:
                if all(sym in productive or sym in grammar.terminals or sym == "ε" for sym in rhs):
                    productive.add(nt)
                    changed = True
                    break

    non_productive = grammar.non_terminals - productive
    for nt in non_productive:
        errors.append(f"Non-terminal '{nt}' is non-productive (cannot derive a terminal string)")

    return errors