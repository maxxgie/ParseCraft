"""Per-cell explanations for ACTION and GOTO table entries.

Each explanation names the LR item responsible for the entry, the grammar
symbol that was consumed (or the completed production), and the resulting DFA
transition, so a student can see exactly why the table contains ``SHIFT``,
``REDUCE``, ``ACCEPT``, ``ERROR`` or a GOTO target.
"""

from __future__ import annotations

from typing import List

END_MARKER = "$"


def _production(lhs: str, body) -> str:
    """Render ``lhs -> body`` with ``ε`` for the empty body."""
    return f"{lhs} -> {' '.join(body) if body else 'ε'}"


def _aug_start(automaton) -> str:
    """Return the augmented start symbol of an automaton."""
    aug = getattr(automaton, "augmented_grammar", None)
    return aug.start_symbol if aug is not None else "S'"


def _indent(text: str, prefix: str = "  ") -> str:
    """Indent every line of ``text`` by ``prefix``."""
    return "\n".join(prefix + line for line in text.splitlines())


def _reduce_rule(parser_type: str, lhs: str) -> str:
    """Describe the reduction rule a parser type uses for ``lhs``."""
    if parser_type == "LR(0)":
        return "LR(0): reduce on every terminal"
    if parser_type == "SLR(1)":
        return f"SLR(1): reduce only when lookahead ∈ FOLLOW({lhs})"
    if parser_type == "CLR(1)":
        return "CLR(1): reduce on the item's own lookahead"
    if parser_type == "LALR(1)":
        return "LALR(1): reduce on the merged state's lookahead"
    return f"{parser_type}: reduce on the item's lookahead"


def explain_action(analysis, state_id: int, terminal: str) -> str:
    """Explain the ACTION-table entry for ``(state_id, terminal)``.

    Args:
        analysis: The :class:`~core.engine.AnalysisResult` being displayed.
        state_id: The LR state.
        terminal: The terminal column.

    Returns:
        A multi-line, human-readable explanation.
    """
    table = analysis.table
    automaton = analysis.automaton
    action = table.get_action(state_id, terminal)
    state = automaton.get_state(state_id)
    items = state.sorted_items()
    header = f"ACTION[{state_id}, {terminal}]"
    lines: List[str] = []

    if action is None:
        lines.append(f"{header} = ERROR (empty cell)")
        lines.append("")
        lines.append(f"State I{state_id} contains:")
        lines.append(_indent(state.get_items_string()))
        lines.append("")
        lines.append(
            f"No item has the terminal '{terminal}' immediately after the dot, "
            f"and no completed item reduces on '{terminal}'."
        )
        lines.append("Therefore: ERROR.")
        return "\n".join(lines)

    if action.action_type == "shift":
        responsible = [it for it in items if it.next_symbol() == terminal]
        lines.append(f"{header} = SHIFT {action.state}")
        lines.append("")
        lines.append(f"State I{state_id} contains:")
        for it in responsible:
            lines.append(f"  {it.to_string()}")
        lines.append("")
        lines.append(f"'{terminal}' is a terminal immediately after the dot.")
        lines.append(
            f"DFA transition: GOTO(I{state_id}, {terminal}) = I{action.state}."
        )
        lines.append(f"Therefore: SHIFT {action.state}.")
        return "\n".join(lines)

    if action.action_type == "reduce":
        body = action.production_rhs or ()
        responsible = [
            it
            for it in items
            if it.is_complete()
            and it.lhs == action.production_lhs
            and it.rhs == body
        ]
        lines.append(
            f"{header} = REDUCE {_production(action.production_lhs, body)} "
            f"(r{action.rule_number})"
        )
        lines.append("")
        lines.append("State contains the completed item:")
        for it in responsible:
            lines.append(f"  {it.to_string()}")
        lines.append("")
        lines.append("The dot is at the end, so the production can be reduced.")
        lines.append(
            f"Lookahead rule: {_reduce_rule(analysis.parser_type, action.production_lhs)}."
        )
        lines.append(f"Therefore: REDUCE by production {action.rule_number}.")
        return "\n".join(lines)

    if action.action_type == "accept":
        aug_start = _aug_start(automaton)
        responsible = [
            it
            for it in items
            if it.is_complete() and it.lhs == aug_start
        ]
        lines.append(f"{header} = ACCEPT")
        lines.append("")
        lines.append("State contains the completed augmented start item:")
        for it in responsible:
            lines.append(f"  {it.to_string()}")
        lines.append("")
        lines.append(
            "The augmented start production is complete and the end marker "
            "'$' is next, so the input is fully recognised."
        )
        lines.append("Therefore: ACCEPT.")
        return "\n".join(lines)

    return f"{header} = {action.to_string()}"


def explain_goto(analysis, state_id: int, non_terminal: str) -> str:
    """Explain the GOTO-table entry for ``(state_id, non_terminal)``.

    Args:
        analysis: The :class:`~core.engine.AnalysisResult` being displayed.
        state_id: The LR state.
        non_terminal: The non-terminal column.

    Returns:
        A multi-line, human-readable explanation.
    """
    table = analysis.table
    automaton = analysis.automaton
    target = table.get_goto(state_id, non_terminal)
    state = automaton.get_state(state_id)
    items = state.sorted_items()
    lines: List[str] = [f"GOTO[{state_id}, {non_terminal}] = {target}"]
    lines.append("")
    lines.append(f"State I{state_id} contains:")
    responsible = [it for it in items if it.next_symbol() == non_terminal]
    for it in responsible:
        moved = it.advance_dot()
        lines.append(f"  {it.to_string()}")
        lines.append(f"    move dot over {non_terminal}: {moved.to_string()}")
    lines.append("")
    if target is None:
        lines.append(f"No transition on '{non_terminal}' exists from I{state_id}.")
        lines.append("Therefore: empty cell.")
    else:
        lines.append(f"Destination: I{target}.")
        lines.append(f"Therefore: GOTO[{state_id}, {non_terminal}] = {target}.")
    return "\n".join(lines)