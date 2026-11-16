"""Unified ACTION/GOTO parsing-table construction.

A single :func:`build_parsing_table` function produces tables for every
supported parser type. The ``mode`` selects how the lookahead set for a
completed item is determined:

* ``lr0``   - reduce on every terminal;
* ``slr1``  - reduce on ``FOLLOW(lhs)``;
* ``clr1``  - reduce on the item's own lookahead;
* ``lalr1`` - reduce on the (merged) item's lookahead.

The builder collects every candidate action per cell, then reports any cell
with more than one distinct action as a :class:`~models.parsing_table.Conflict`
(the first action is stored provisionally; use
:func:`core.conflict_resolution.resolve_conflicts` to resolve them).
"""

from __future__ import annotations

from typing import Dict, List, Set, Tuple

from core.logging_config import get_logger
from models.grammar import Grammar
from models.parsing_table import Conflict, ParseTable, TableAction

logger = get_logger(__name__)

END_MARKER = "$"
AUGMENTED_START = "S'"

# Maps a public parser-type label to the internal mode string.
MODES: Dict[str, str] = {
    "LR(0)": "lr0",
    "SLR(1)": "slr1",
    "CLR(1)": "clr1",
    "LALR(1)": "lalr1",
}


def assign_production_numbers(
    grammar: Grammar,
) -> Tuple[Dict[Tuple[str, Tuple[str, ...]], int], List[Tuple[str, Tuple[str, ...]]]]:
    """Assign a number to every production, including the augmented one.

    The augmented production ``S' -> S`` is number 0; user productions are
    numbered from 1 in declaration order.

    Args:
        grammar: The original grammar (not augmented).

    Returns:
        A tuple ``(numbers, rules)`` where ``numbers`` maps
        ``(lhs, rhs_tuple)`` to a rule number and ``rules`` is the ordered
        list of ``(lhs, rhs_tuple)``.
    """
    numbers: Dict[Tuple[str, Tuple[str, ...]], int] = {}
    rules: List[Tuple[str, Tuple[str, ...]]] = []

    aug_key = (AUGMENTED_START, (grammar.start_symbol,))
    numbers[aug_key] = 0
    rules.append(aug_key)

    index = 1
    for lhs, rhs_list in grammar.productions.items():
        for rhs in rhs_list:
            key = (lhs, tuple(rhs))
            numbers[key] = index
            rules.append(key)
            index += 1
    return numbers, rules


def _dedupe_actions(actions: List[TableAction]) -> List[TableAction]:
    """Remove duplicate actions, preserving order."""
    seen: Set[Tuple] = set()
    result: List[TableAction] = []
    for action in actions:
        key = (
            action.action_type,
            action.state,
            action.production_lhs,
            action.production_rhs,
            action.rule_number,
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(action)
    return result


def build_parsing_table(
    automaton,
    grammar: Grammar,
    mode: str,
    follow: Dict[str, Set[str]] | None = None,
) -> Tuple[ParseTable, List[Conflict]]:
    """Build an ACTION/GOTO parsing table.

    Args:
        automaton: An LR automaton (LR(0)/SLR(1)) or LR(1)/LALR(1) automaton.
        grammar: The original grammar.
        mode: One of ``lr0``, ``slr1``, ``clr1``, ``lalr1``.
        follow: FOLLOW sets (required for ``slr1``).

    Returns:
        A tuple ``(table, conflicts)`` where ``conflicts`` is a list of
        :class:`~models.parsing_table.Conflict` objects.

    Raises:
        ValueError: If ``mode`` is unknown.
    """
    if mode not in ("lr0", "slr1", "clr1", "lalr1"):
        raise ValueError(f"Unknown table mode: {mode}")

    table = ParseTable()
    table.num_states = len(automaton.states)

    terminals = sorted(grammar.terminals)
    if END_MARKER not in terminals:
        terminals.append(END_MARKER)
    table.terminals = terminals
    table.non_terminals = sorted(grammar.non_terminals)

    numbers, _rules = assign_production_numbers(grammar)

    # Collect every candidate action per (state, terminal) cell.
    candidates: Dict[Tuple[int, str], List[TableAction]] = {}

    def add(key: Tuple[int, str], action: TableAction) -> None:
        candidates.setdefault(key, []).append(action)

    for state in automaton.states:
        state_id = state.state_id

        # Shift actions on terminals, GOTO on non-terminals.
        for symbol, target_id in state.transitions.items():
            if symbol in grammar.terminals:
                add((state_id, symbol), TableAction(action_type="shift", state=target_id))
            if symbol in grammar.non_terminals:
                table.goto[(state_id, symbol)] = target_id

        # Completed items -> reduce / accept.
        for item in state.items:
            if not item.is_complete():
                continue
            lhs = item.lhs
            body = item.rhs

            if lhs == AUGMENTED_START and body == (grammar.start_symbol,):
                add((state_id, END_MARKER), TableAction(action_type="accept"))
                continue

            if mode == "lr0":
                lookaheads: Set[str] = set(table.terminals)
            elif mode == "slr1":
                lookaheads = set((follow or {}).get(lhs, set()))
            else:  # clr1 / lalr1
                lookaheads = {item.lookahead} if item.lookahead else set()

            number = numbers.get((lhs, body))
            for la in lookaheads:
                if la not in table.terminals:
                    continue
                add(
                    (state_id, la),
                    TableAction(
                        action_type="reduce",
                        state=number,
                        production_lhs=lhs,
                        production_rhs=body,
                        rule_number=number,
                    ),
                )

    # Finalise: single action -> store; multiple -> record a conflict.
    conflicts: List[Conflict] = []
    for (state_id, terminal), actions in candidates.items():
        unique = _dedupe_actions(actions)
        if len(unique) == 1:
            table.action[(state_id, terminal)] = unique[0]
        else:
            conflicts.append(
                Conflict(state=state_id, terminal=terminal, actions=unique)
            )
            # Provisional value (first wins) until resolution runs.
            table.action[(state_id, terminal)] = unique[0]

    if conflicts:
        logger.warning("%s table: %d conflict(s) detected", mode, len(conflicts))
    logger.info("%s table generated: %d states", mode, table.num_states)
    return table, conflicts