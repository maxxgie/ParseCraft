"""Step-by-step LR parsing simulator.

Drives an LR parser (LR(0)/SLR(1)/CLR(1)/LALR(1)) over an input string,
recording every configuration so the GUI can step through the parse and
reconstruct the parse tree on success.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from core.logging_config import get_logger
from core.parse_tree import make_internal, make_leaf
from models.parse_tree import ParseTreeNode

logger = get_logger(__name__)

END_MARKER = "$"
AUGMENTED_START = "S'"

# Safety valve so a broken grammar can never hang the UI.
MAX_STEPS = 100000


@dataclass
class SimulationStep:
    """A single parser configuration captured during simulation.

    Attributes:
        index: Zero-based step number.
        stack_symbols: Grammar symbols on the stack, bottom to top
            (the bottom entry is always ``$``).
        stack_states: Parser states parallel to ``stack_symbols``.
        input_remaining: Input tokens not yet consumed, including ``$``.
        action: One of ``start``, ``shift``, ``reduce``, ``accept``, ``error``.
        action_text: Human-readable description of the action.
        rule_number: Production number for reduce actions, else ``None``.
        rule_text: Production in ``A -> X Y`` form for reduce actions.
    """

    index: int
    stack_symbols: List[str]
    stack_states: List[int]
    input_remaining: List[str]
    action: str
    action_text: str
    rule_number: Optional[int] = None
    rule_text: str = ""

    def stack_string(self) -> str:
        """Return a compact ``state:symbol`` representation of the stack."""
        return " | ".join(
            f"{state}:{symbol}"
            for state, symbol in zip(self.stack_states, self.stack_symbols)
        )


@dataclass
class SimulationResult:
    """The outcome of a parse simulation.

    Attributes:
        accepted: Whether the input was accepted.
        steps: The ordered list of configurations.
        parse_tree: The parse tree root on success, else ``None``.
        error: An error message on failure, else ``None``.
    """

    accepted: bool
    steps: List[SimulationStep] = field(default_factory=list)
    parse_tree: Optional[ParseTreeNode] = None
    error: Optional[str] = None


def _format_rule(lhs: str, rhs) -> str:
    body = " ".join(rhs) if rhs else "ε"
    return f"{lhs} -> {body}"


def tokenize(input_string: str, grammar) -> List[str]:
    """Split ``input_string`` into terminal tokens.

    Whitespace separates tokens, but tokens are also split automatically at
    boundaries between grammar terminals so inputs such as ``id+id`` or
    ``(id)`` parse without manual spacing. Matching is greedy: at each position
    the longest grammar terminal wins. Any characters that match no terminal
    are collected into an unknown token so the simulator can report them.

    Args:
        input_string: The raw input text.
        grammar: The grammar providing the terminal alphabet.

    Returns:
        The list of tokens (without the end marker).
    """
    terminals = sorted(grammar.terminals, key=len, reverse=True)
    if not terminals:
        return input_string.split()

    tokens: List[str] = []
    i = 0
    n = len(input_string)
    while i < n:
        if input_string[i].isspace():
            i += 1
            continue
        matched = None
        for terminal in terminals:
            if input_string.startswith(terminal, i):
                matched = terminal
                break
        if matched is not None:
            tokens.append(matched)
            i += len(matched)
            continue
        # Unknown token: grab chars until whitespace or the next terminal starts.
        start = i
        while i < n and not input_string[i].isspace():
            if any(input_string.startswith(t, i) for t in terminals):
                break
            i += 1
        tokens.append(input_string[start:i])
    return tokens


def simulate(table, grammar, input_string: str) -> SimulationResult:
    """Run the LR parser over ``input_string``.

    Args:
        table: The :class:`~models.parsing_table.ParseTable` to drive the parse.
        grammar: The original grammar (provides production text for rules).
        input_string: Terminal string; whitespace is optional between tokens.

    Returns:
        A :class:`SimulationResult`.
    """
    tokens = tokenize(input_string, grammar)
    inputs = tokens + [END_MARKER]
    ip = 0

    # Parallel stacks: state, grammar symbol, parse-tree node.
    state_stack: List[int] = [0]
    symbol_stack: List[str] = [END_MARKER]
    node_stack: List[Optional[ParseTreeNode]] = [None]

    steps: List[SimulationStep] = []

    def record(action: str, text: str, rule_number=None, rule_text: str = "") -> None:
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

    record("start", "Initial configuration")

    while len(steps) <= MAX_STEPS:
        state = state_stack[-1]
        token = inputs[ip]
        action = table.get_action(state, token)

        if action is None:
            text = f"Syntax error: no action for state {state}, token '{token}'"
            record("error", text)
            logger.info("Parse rejected: %s", text)
            return SimulationResult(accepted=False, steps=steps, error=text)

        if action.action_type == "shift":
            target = action.state
            leaf = make_leaf(token, token)
            state_stack.append(target)
            symbol_stack.append(token)
            node_stack.append(leaf)
            ip += 1
            record("shift", f"Shift '{token}' to state {target}")

        elif action.action_type == "reduce":
            lhs = action.production_lhs
            rhs = tuple(action.production_rhs or ())
            n = len(rhs)
            rule_no = action.rule_number

            if n == 0:
                children: List[ParseTreeNode] = []
            else:
                children = [node for node in node_stack[-n:] if node is not None]
                del state_stack[-n:]
                del symbol_stack[-n:]
                del node_stack[-n:]

            target = table.get_goto(state_stack[-1], lhs)
            if target is None:
                text = (
                    f"Error: no GOTO for '{lhs}' from state {state_stack[-1]} "
                    f"after reducing by {lhs} -> {' '.join(rhs) if rhs else 'ε'}"
                )
                record("error", text)
                logger.info("Parse rejected: %s", text)
                return SimulationResult(accepted=False, steps=steps, error=text)

            new_node = make_internal(lhs, children)
            state_stack.append(target)
            symbol_stack.append(lhs)
            node_stack.append(new_node)

            rule_text = _format_rule(lhs, rhs)
            record(
                "reduce",
                f"Reduce by {rule_text} (R{rule_no}), goto state {target}",
                rule_number=rule_no,
                rule_text=rule_text,
            )

        elif action.action_type == "accept":
            record("accept", "Accept")
            root = node_stack[-1]
            logger.info("Parse accepted in %d steps", len(steps))
            return SimulationResult(accepted=True, steps=steps, parse_tree=root)

        else:  # pragma: no cover - defensive
            text = f"Error: unknown action type '{action.action_type}'"
            record("error", text)
            return SimulationResult(accepted=False, steps=steps, error=text)

    text = f"Error: exceeded maximum of {MAX_STEPS} steps (possible infinite loop)"
    record("error", text)
    return SimulationResult(accepted=False, steps=steps, error=text)