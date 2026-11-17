"""Error recovery simulation for the LR parser.

Implements panic-mode and phrase-level recovery on top of an LR parsing table,
reporting the error location, expected tokens, and the recovery actions taken.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from core.logging_config import get_logger
from core.parse_tree import make_internal, make_leaf
from core.parser_simulator import (
    END_MARKER,
    MAX_STEPS,
    SimulationStep,
    _format_rule,
    tokenize,
)
from models.grammar import Grammar
from models.parse_tree import ParseTreeNode

logger = get_logger(__name__)

RECOVERY_MODES = ["panic-mode", "phrase-level"]


@dataclass
class RecoveryEvent:
    """A single recovery action taken by the parser.

    Attributes:
        position: Token index where the error was detected.
        token: The offending token.
        expected: Terminals that had a valid action at the error point.
        action: Description of the recovery action.
        deleted: Number of tokens deleted.
        inserted: Symbols inserted.
    """

    position: int
    token: str
    expected: List[str]
    action: str
    deleted: int = 0
    inserted: List[str] = field(default_factory=list)

    def summary(self) -> str:
        """Return a one-line description of the event."""
        expected = ", ".join(self.expected) if self.expected else "nothing"
        return (
            f"pos {self.position}: unexpected '{self.token}' "
            f"(expected: {expected}) -> {self.action}"
        )


@dataclass
class RecoveryReport:
    """The outcome of a recovery-enabled parse.

    Attributes:
        accepted: Whether the parser reached an accept state.
        mode: The recovery mode used.
        events: Recovery actions taken.
        steps: Full parse trace including recovery steps.
        error: A fatal error message, if the input was unrecoverable.
        remaining_tokens: Tokens not consumed (empty on success).
        parse_tree: The parse tree on success.
        tokens_consumed: Number of input tokens consumed.
        tokens_total: Total number of input tokens.
        recovered: Whether at least one error was recovered.
    """

    accepted: bool
    mode: str
    events: List[RecoveryEvent] = field(default_factory=list)
    steps: List[SimulationStep] = field(default_factory=list)
    error: Optional[str] = None
    remaining_tokens: List[str] = field(default_factory=list)
    parse_tree: Optional[ParseTreeNode] = None
    tokens_consumed: int = 0
    tokens_total: int = 0
    recovered: bool = False

    def report_text(self) -> str:
        """Return a human-readable summary of the recovery."""
        lines = [
            f"Recovery mode: {self.mode}",
            f"Tokens: {self.tokens_consumed}/{self.tokens_total} consumed",
            f"Result: {'accepted' if self.accepted else 'rejected'}",
        ]
        if self.events:
            lines.append(f"Recovery actions ({len(self.events)}):")
            lines.extend(f"  - {e.summary()}" for e in self.events)
        if self.error:
            lines.append(f"Error: {self.error}")
        return "\n".join(lines)


def _expected_terminals(table, state: int) -> List[str]:
    terminals = list(dict.fromkeys(list(table.terminals) + [END_MARKER]))
    return [t for t in terminals if table.get_action(state, t) is not None]


def _try_insert(table, state: int, lookahead: str):
    """Return ``(token, target_state)`` for a viable single-token insertion."""
    for expected in _expected_terminals(table, state):
        action = table.get_action(state, expected)
        if action is None or action.action_type != "shift":
            continue
        if table.get_action(action.state, lookahead) is not None:
            return expected, action.state
    return None


def recover_input(
    table,
    grammar: Grammar,
    input_string: str,
    mode: str = "panic-mode",
) -> RecoveryReport:
    """Parse ``input_string`` with error recovery enabled.

    Args:
        table: The LR parsing table.
        grammar: The grammar (for tokenization and FOLLOW sets).
        input_string: The raw input.
        mode: One of :data:`RECOVERY_MODES`.

    Returns:
        A :class:`RecoveryReport`.
    """
    if mode not in RECOVERY_MODES:
        raise ValueError(
            f"Unknown recovery mode '{mode}'. Expected one of {RECOVERY_MODES}."
        )

    tokens = tokenize(input_string, grammar)
    inputs = tokens + [END_MARKER]
    total = len(tokens)

    state_stack: List[int] = [0]
    symbol_stack: List[str] = [END_MARKER]
    node_stack: List[Optional[ParseTreeNode]] = [None]
    events: List[RecoveryEvent] = []
    steps: List[SimulationStep] = []
    ip = 0

    def rec(action: str, text: str, rule_number=None, rule_text: str = "") -> None:
        steps.append(
            SimulationStep(
                index=len(steps),
                stack_symbols=list(symbol_stack),
                stack_states=list(state_stack),
                input_remaining=list(inputs[ip:]),
                action=action,
                action_text=text,
                rule_number=rule_number,
                rule_text=rule_text,
            )
        )

    def finish(accepted: bool, error: Optional[str], tree) -> RecoveryReport:
        return RecoveryReport(
            accepted=accepted,
            mode=mode,
            events=events,
            steps=steps,
            error=error,
            remaining_tokens=list(inputs[ip:]) if not accepted else [],
            parse_tree=tree,
            tokens_consumed=min(ip, total),
            tokens_total=total,
            recovered=bool(events),
        )

    rec("start", "Initial configuration")
    iterations = 0
    inserts_at = 0
    last_ip = -1

    while iterations < MAX_STEPS:
        iterations += 1
        state = state_stack[-1]
        token = inputs[ip]
        action = table.get_action(state, token)

        if action is None:
            expected = _expected_terminals(table, state)

            if mode == "phrase-level" and ip == last_ip:
                inserts_at += 1
            elif ip != last_ip:
                last_ip = ip
                inserts_at = 0

            # Phrase-level: attempt a single-token insertion.
            if mode == "phrase-level" and inserts_at < 5:
                insertion = _try_insert(table, state, token)
                if insertion is not None:
                    new_token, target = insertion
                    state_stack.append(target)
                    symbol_stack.append(new_token)
                    node_stack.append(make_leaf(new_token, new_token))
                    events.append(
                        RecoveryEvent(
                            position=ip,
                            token=token,
                            expected=expected,
                            action=f"inserted '{new_token}'",
                            inserted=[new_token],
                        )
                    )
                    rec("recover", f"Inserted '{new_token}' (expected {expected})")
                    continue

            # Phrase-level: attempt a single-token deletion if the next token
            # is acceptable in the current state.
            if (
                mode == "phrase-level"
                and ip + 1 < len(inputs)
                and table.get_action(state, inputs[ip + 1]) is not None
            ):
                bad = token
                events.append(
                    RecoveryEvent(
                        position=ip,
                        token=bad,
                        expected=expected,
                        action=f"deleted '{bad}'",
                        deleted=1,
                    )
                )
                rec("recover", f"Deleted unexpected '{bad}' (expected {expected})")
                ip += 1
                continue

            # Panic-mode (or phrase-level fallback): delete tokens until the
            # current state has an action for the lookahead (do not pop states,
            # which could otherwise hide errors behind a false accept).
            start_ip = ip
            while (
                ip < len(inputs)
                and inputs[ip] != END_MARKER
                and table.get_action(state, inputs[ip]) is None
            ):
                ip += 1
            deleted = ip - start_ip
            if deleted == 0:
                rec(
                    "error",
                    f"Cannot recover at '{token}' (expected {expected})",
                )
                return finish(
                    False,
                    f"Unrecoverable syntax error at '{token}'; "
                    f"expected one of {expected}",
                    None,
                )
            events.append(
                RecoveryEvent(
                    position=start_ip,
                    token=token,
                    expected=expected,
                    action=f"deleted {deleted} token(s) to resynchronise",
                    deleted=deleted,
                )
            )
            rec(
                "recover",
                f"Deleted {deleted} token(s); resynchronising (expected {expected})",
            )
            continue

        if action.action_type == "shift":
            target = action.state
            state_stack.append(target)
            symbol_stack.append(token)
            node_stack.append(make_leaf(token, token))
            ip += 1
            rec("shift", f"Shift '{token}' to state {target}")

        elif action.action_type == "reduce":
            lhs = action.production_lhs
            rhs = tuple(action.production_rhs or ())
            n = len(rhs)
            if n == 0:
                children: List[ParseTreeNode] = []
            else:
                children = [node for node in node_stack[-n:] if node is not None]
                del state_stack[-n:]
                del symbol_stack[-n:]
                del node_stack[-n:]
            target = table.get_goto(state_stack[-1], lhs)
            if target is None:
                text = f"Lost GOTO for '{lhs}' after reduction"
                rec("error", text)
                return finish(False, text, None)
            node_stack.append(make_internal(lhs, children))
            state_stack.append(target)
            symbol_stack.append(lhs)
            rec(
                "reduce",
                f"Reduce by {_format_rule(lhs, rhs)} (R{action.rule_number}), "
                f"goto {target}",
                rule_number=action.rule_number,
                rule_text=_format_rule(lhs, rhs),
            )

        elif action.action_type == "accept":
            rec("accept", "Accept")
            return finish(True, None, node_stack[-1])

        else:  # pragma: no cover - defensive
            text = f"Unknown action type '{action.action_type}'"
            rec("error", text)
            return finish(False, text, None)

    rec("error", "Exceeded maximum steps")
    return finish(False, "Exceeded maximum of %d steps" % MAX_STEPS, None)