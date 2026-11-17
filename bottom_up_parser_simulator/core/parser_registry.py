"""Classification of parsers into table-based and procedure-based families.

Not every parser uses a formal parsing table:

* **table-based** parsers are driven by a generated table
  (LL(1)/predictive use the M[Non-terminal, Terminal] table; the LR family
  uses ACTION + GOTO tables);
* **procedure-based** parsers (recursive descent and backtracking recursive
  descent) are encoded as mutually recursive functions and therefore have no
  parse table — their "trace" is the sequence of function calls and the
  alternatives they select.

This module is the single source of truth for that classification so the rest
of the application (tab selection, validation, simulation) agrees on which
parsers produce tables.
"""

from __future__ import annotations

from typing import Dict, List

# Parsers driven by a generated predictive (LL(1)) table.
LL1_PARSERS: List[str] = ["Predictive (LL(1))", "LL(1)"]

# Parsers driven by generated ACTION + GOTO tables.
LR_PARSERS: List[str] = ["Shift Reduce", "LR(0)", "SLR(1)", "CLR(1)", "LALR(1)"]

# Parsers encoded as procedures (no table).
PROCEDURE_PARSERS: List[str] = [
    "Recursive Descent",
    "Backtracking Recursive Descent",
]

TABLE_BASED_PARSERS: List[str] = LL1_PARSERS + LR_PARSERS

# The table kinds each parser family produces.
TABLE_KINDS: Dict[str, List[str]] = {
    **{parser: ["LL(1)"] for parser in LL1_PARSERS},
    **{parser: ["ACTION", "GOTO"] for parser in LR_PARSERS},
    **{parser: [] for parser in PROCEDURE_PARSERS},
}


def uses_parse_table(parser_type: str) -> bool:
    """Return ``True`` when ``parser_type`` is driven by a generated table."""
    return parser_type in TABLE_BASED_PARSERS


def is_ll1_parser(parser_type: str) -> bool:
    """Return ``True`` for predictive / LL(1) parsers."""
    return parser_type in LL1_PARSERS


def is_lr_parser(parser_type: str) -> bool:
    """Return ``True`` for the LR family (Shift Reduce, LR(0), SLR, CLR, LALR)."""
    return parser_type in LR_PARSERS


def is_procedure_parser(parser_type: str) -> bool:
    """Return ``True`` for recursive-descent parsers (no table)."""
    return parser_type in PROCEDURE_PARSERS


def parse_table_kinds(parser_type: str) -> List[str]:
    """Return the table kinds generated for ``parser_type`` (may be empty)."""
    return list(TABLE_KINDS.get(parser_type, []))


def procedure_trace_kind(parser_type: str) -> str:
    """Describe what a procedure-based parser displays instead of a table."""
    if parser_type == "Backtracking Recursive Descent":
        return "function calls, backtracking points and the successful alternative"
    if parser_type == "Recursive Descent":
        return "function-call structure and recursive execution trace"
    return "execution trace"