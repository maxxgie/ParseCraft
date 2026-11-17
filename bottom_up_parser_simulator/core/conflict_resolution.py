"""Conflict resolution for LR parsing tables.

Two families of conflicts can occur in an ACTION table:

* **shift-reduce** - the parser could shift the next token or reduce a
  production. Common strategies: prefer *shift*, prefer *reduce*, or use
  *precedence/associativity* (the yacc approach).
* **reduce-reduce** - two (or more) completed items could be reduced. Common
  strategies: prefer the *first* rule (lowest rule number) or use
  *precedence*.

:func:`resolve_conflicts` applies a :class:`ResolutionConfig` to a table and
its detected :class:`~models.parsing_table.Conflict` list, updating the table
in place and returning a record of what it did.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from core.logging_config import get_logger
from core.precedence import LEFT, RIGHT, PrecedenceInfo
from models.parsing_table import Conflict, ParseTable, TableAction

logger = get_logger(__name__)

# Shift/reduce strategies
SHIFT = "shift"
REDUCE = "reduce"
PRECEDENCE = "precedence"
NONE = "none"

# Reduce/reduce strategies
FIRST = "first"

SHIFT_REDUCE_OPTIONS = [NONE, SHIFT, REDUCE, PRECEDENCE]
REDUCE_REDUCE_OPTIONS = [NONE, FIRST, PRECEDENCE]


@dataclass
class ResolutionConfig:
    """User-selected conflict-resolution strategy.

    Attributes:
        enabled: Whether conflicts should be resolved at all.
        shift_reduce: One of :data:`SHIFT_REDUCE_OPTIONS`.
        reduce_reduce: One of :data:`REDUCE_REDUCE_OPTIONS`.
    """

    enabled: bool = False
    shift_reduce: str = SHIFT
    reduce_reduce: str = FIRST

    def validate(self) -> None:
        """Raise :class:`ValueError` if a strategy is not recognised."""
        if self.shift_reduce not in SHIFT_REDUCE_OPTIONS:
            raise ValueError(
                f"Unknown shift/reduce strategy '{self.shift_reduce}'. "
                f"Expected one of {SHIFT_REDUCE_OPTIONS}."
            )
        if self.reduce_reduce not in REDUCE_REDUCE_OPTIONS:
            raise ValueError(
                f"Unknown reduce/reduce strategy '{self.reduce_reduce}'. "
                f"Expected one of {REDUCE_REDUCE_OPTIONS}."
            )


@dataclass
class Resolution:
    """A single applied conflict resolution.

    Attributes:
        conflict: The conflict that was resolved.
        chosen: The action written into the table cell.
        strategy: The strategy label used.
        description: Human-readable explanation.
    """

    conflict: Conflict
    chosen: TableAction
    strategy: str
    description: str

    @property
    def state(self) -> int:
        """The state of the resolved conflict."""
        return self.conflict.state

    @property
    def terminal(self) -> str:
        """The terminal of the resolved conflict."""
        return self.conflict.terminal


def _first_reduce(conflict: Conflict) -> Optional[TableAction]:
    """Return the lowest-numbered reduce action, or ``None``."""
    reduces = [a for a in conflict.actions if a.action_type == "reduce"]
    if not reduces:
        return None
    return sorted(
        reduces, key=lambda a: a.rule_number if a.rule_number is not None else 1 << 30
    )[0]


def _resolve_shift_reduce(
    conflict: Conflict, strategy: str, precedence: PrecedenceInfo
) -> Tuple[Optional[TableAction], str]:
    """Resolve a shift-reduce conflict, returning ``(action, description)``."""
    shift = next((a for a in conflict.actions if a.action_type == "shift"), None)
    reduce_action = _first_reduce(conflict)

    if strategy == SHIFT:
        return shift, "prefer shift"
    if strategy == REDUCE:
        return reduce_action, "prefer reduce"

    # Precedence-based resolution (yacc style).
    term = conflict.terminal
    term_level = precedence.level(term)
    rule_level = (
        precedence.production_level(reduce_action.production_rhs)
        if reduce_action is not None
        else None
    )

    if term_level is None or rule_level is None:
        return shift, "no precedence declared; default to shift"

    if term_level > rule_level:
        return shift, f"shift ('{term}' level {term_level} > rule level {rule_level})"
    if term_level < rule_level:
        return (
            reduce_action,
            f"reduce ('{term}' level {term_level} < rule level {rule_level})",
        )

    # Equal precedence -> associativity decides.
    assoc = precedence.assoc(term)
    if assoc == LEFT:
        return reduce_action, f"reduce ('{term}' is left associative)"
    if assoc == RIGHT:
        return shift, f"shift ('{term}' is right associative)"
    return None, f"error ('{term}' is non-associative)"


def _resolve_reduce_reduce(
    conflict: Conflict, strategy: str, precedence: PrecedenceInfo
) -> Tuple[Optional[TableAction], str]:
    """Resolve a reduce-reduce conflict, returning ``(action, description)``."""
    reduces = [a for a in conflict.actions if a.action_type == "reduce"]
    if not reduces:
        return None, "no reduce action available"

    ordered = sorted(
        reduces,
        key=lambda a: a.rule_number if a.rule_number is not None else 1 << 30,
    )

    if strategy == FIRST:
        chosen = ordered[0]
        return chosen, f"first rule (R{chosen.rule_number})"

    # Precedence-based: prefer the higher-precedence production.
    best: Optional[TableAction] = None
    best_level: Optional[int] = None
    for action in ordered:
        level = precedence.production_level(action.production_rhs)
        if level is not None and (best_level is None or level > best_level):
            best = action
            best_level = level
    if best is None:
        chosen = ordered[0]
        return chosen, "no precedence declared; default to first rule"
    return best, f"higher precedence (R{best.rule_number}, level {best_level})"


def _describe_actions(conflict: Conflict) -> str:
    """Return a readable list of the competing actions."""
    parts: List[str] = []
    for action in conflict.actions:
        if action.action_type == "shift":
            parts.append(f"shift '{conflict.terminal}' (S{action.state})")
        elif action.action_type == "reduce":
            lhs = action.production_lhs or "?"
            rhs = " ".join(action.production_rhs or ()) or "ε"
            rule = (
                f"R{action.rule_number}"
                if action.rule_number is not None
                else "R?"
            )
            parts.append(f"reduce by {rule}: {lhs} -> {rhs}")
        elif action.action_type == "accept":
            parts.append("accept")
    return "\n".join(f"  • {part}" for part in parts)


def describe_conflict(conflict: Conflict, automaton, parser_type: str = "") -> str:
    """Return a teaching-oriented explanation of a conflict.

    Args:
        conflict: The conflict to describe.
        automaton: The automaton that produced the conflict (used to show the
            state's items).
        parser_type: The LR algorithm being used, for a tailored suggestion.

    Returns:
        A multi-line explanation with the conflict type, state items, the
        reason the parser cannot decide, and a suggested resolution.
    """
    lines: List[str] = [
        f"Conflict type: {conflict.conflict_type}",
        f"State: I{conflict.state}",
        f"Lookahead terminal: '{conflict.terminal}'",
        "",
        "Items:",
    ]
    state = automaton.get_state(conflict.state) if automaton is not None else None
    if state is not None:
        lines.append(state.get_items_string())
    else:
        lines.append("  (state items unavailable)")

    lines.append("")
    lines.append("Competing actions:")
    lines.append(_describe_actions(conflict))

    lines.append("")
    lines.append("Reason:")
    if conflict.conflict_type == "shift/reduce":
        lines.append(
            "  The parser can either shift the next token or reduce a "
            "completed production. It cannot decide which action is correct "
            "from the current state alone."
        )
        lines.append(
            "  LR(0) has no lookahead, so this conflict is expected whenever "
            "a completed item and a shift item coexist."
        )
    elif conflict.conflict_type == "reduce/reduce":
        lines.append(
            "  Two different completed items can be reduced by the same "
            "lookahead. The grammar does not determine which production was "
            "used."
        )
    elif conflict.conflict_type == "accept/reduce":
        lines.append(
            "  The parser can either accept or reduce. This usually means the "
            "grammar can derive the input in two ways."
        )
    else:
        lines.append("  The parser has multiple possible actions for one cell.")

    lines.append("")
    lines.append("Suggested solution:")
    suggestion = {
        "LR(0)": (
            "  Use SLR(1), CLR(1) or LALR(1). They add lookahead information "
            "that can decide this cell."
        ),
        "SLR(1)": (
            "  Use CLR(1) or LALR(1). FOLLOW sets are too coarse here; precise "
            "per-state lookaheads may resolve the conflict."
        ),
        "CLR(1)": (
            "  The canonical LR(1) automaton is itself ambiguous. Inspect the "
            "grammar for ambiguity; no conflict-free LR parser may exist."
        ),
        "LALR(1)": (
            "  Use CLR(1). LALR(1) merged states and lost distinct lookaheads; "
            "the unmerged automaton is conflict-free."
        ),
    }.get(
        parser_type,
        "  Use a more powerful LR algorithm, or resolve the conflict "
        "explicitly and document why the chosen action is correct.",
    )
    lines.append(suggestion)
    lines.append("")
    lines.append(
        "  Do not resolve this silently: any resolution must be an explicit, "
        "explained choice."
    )
    return "\n".join(lines)


def resolve_conflicts(
    table: ParseTable,
    conflicts: List[Conflict],
    config: ResolutionConfig,
    precedence: Optional[PrecedenceInfo] = None,
) -> List[Resolution]:
    """Apply conflict-resolution strategies to a table.

    The table is modified in place: each resolved cell receives the chosen
    action.

    Args:
        table: The parsing table to update.
        conflicts: The conflicts detected during table construction.
        config: The resolution strategy to apply.
        precedence: Precedence info (required for ``precedence`` strategies).

    Returns:
        A list of :class:`Resolution` records (one per resolved conflict).
    """
    if not config.enabled or not conflicts:
        return []

    config.validate()
    precedence = precedence or PrecedenceInfo()
    resolutions: List[Resolution] = []

    for conflict in conflicts:
        key = (conflict.state, conflict.terminal)

        if conflict.has_accept:
            chosen = next(
                (a for a in conflict.actions if a.action_type == "accept"), None
            )
            if chosen is not None:
                table.action[key] = chosen
                resolutions.append(
                    Resolution(conflict, chosen, "accept", "prefer accept")
                )
            continue

        if conflict.has_shift and conflict.has_reduce:
            chosen, description = _resolve_shift_reduce(
                conflict, config.shift_reduce, precedence
            )
            strategy = config.shift_reduce
        else:  # reduce-reduce
            chosen, description = _resolve_reduce_reduce(
                conflict, config.reduce_reduce, precedence
            )
            strategy = config.reduce_reduce

        if chosen is not None:
            table.action[key] = chosen
            resolutions.append(Resolution(conflict, chosen, strategy, description))
        else:
            logger.warning(
                "Unresolved %s conflict at state %d on '%s': %s",
                conflict.conflict_type,
                conflict.state,
                conflict.terminal,
                description,
            )

    logger.info("Resolved %d conflict(s)", len(resolutions))
    return resolutions