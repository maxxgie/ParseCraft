"""Tests for FIRST/FOLLOW, table generation, and the parsing simulator."""

from __future__ import annotations

import pytest

from core.automaton import LRAutomaton
from core.closure import closure
from core.engine import ALL_PARSER_TYPES, analyze, simulate_input
from core.first_follow import compute_first, compute_follow
from core.goto import goto
from core.grammar_engine import augment_grammar
from core.grammar_parser import parse_grammar
from core.lr1_automaton import LR1Automaton
from models.grammar import Grammar
from models.lr_item import LRItem

EXPRESSION = """E -> E + T | T
T -> T * F | F
F -> ( E ) | id"""

# LALR(1) but not SLR(1): SLR has a conflict on '='.
LALR_NOT_SLR = """S -> L = R | R
L -> * R | id
R -> L"""

EPSILON_GRAMMAR = """S -> A B
A -> a | ε
B -> b"""


# ----------------------------------------------------------------------
# FIRST / FOLLOW
# ----------------------------------------------------------------------
def test_first_sets():
    grammar = parse_grammar(EXPRESSION)
    first = compute_first(grammar)
    assert first["id"] == {"id"}
    assert first["("] == {"("}
    assert "ε" not in first["F"]
    # FIRST(E) = FIRST(T) = FIRST(F) = { (, id }
    assert first["E"] == {"(", "id"}


def test_follow_sets():
    grammar = parse_grammar(EXPRESSION)
    first = compute_first(grammar)
    follow = compute_follow(grammar, first)
    assert "$" in follow["E"]
    assert follow["E"] == {"$", "+", ")"}
    assert follow["T"] == {"$", "+", ")", "*"}
    assert follow["F"] == {"$", "+", ")", "*"}


# ----------------------------------------------------------------------
# Automaton / table generation
# ----------------------------------------------------------------------
@pytest.mark.parametrize("parser_type", ALL_PARSER_TYPES)
def test_all_parser_types_build(parser_type):
    result = analyze(EXPRESSION, parser_type)
    assert len(result.automaton.states) > 0
    assert result.table.num_states == len(result.automaton.states)


def test_lr0_has_conflicts_expression():
    result = analyze(EXPRESSION, "LR(0)")
    assert result.conflicts, "The expression grammar is not LR(0)"


@pytest.mark.parametrize("parser_type", ["SLR(1)", "CLR(1)", "LALR(1)"])
def test_expression_conflict_free(parser_type):
    result = analyze(EXPRESSION, parser_type)
    assert result.conflicts == []


def test_lalr_not_slr():
    slr = analyze(LALR_NOT_SLR, "SLR(1)")
    lalr = analyze(LALR_NOT_SLR, "LALR(1)")
    clr = analyze(LALR_NOT_SLR, "CLR(1)")
    assert slr.conflicts, "SLR should have a conflict on this grammar"
    assert lalr.conflicts == []
    assert clr.conflicts == []


def test_lalr_merges_to_same_size_as_slr():
    slr = analyze(EXPRESSION, "SLR(1)")
    lalr = analyze(EXPRESSION, "LALR(1)")
    clr = analyze(EXPRESSION, "CLR(1)")
    assert len(lalr.automaton.states) == len(slr.automaton.states)
    assert len(clr.automaton.states) > len(lalr.automaton.states)


def test_lr1_automaton_direct():
    grammar = parse_grammar(EXPRESSION)
    auto = LR1Automaton(grammar, merge=False)
    assert auto.merged is False
    lr0 = LRAutomaton(grammar)
    assert len(auto.states) >= len(lr0.states)


def test_dangling_else_conflict():
    grammar = """S -> if E then S | if E then S else S | other
E -> cond"""
    result = analyze(grammar, "SLR(1)")
    assert result.conflicts


# ----------------------------------------------------------------------
# Simulation
# ----------------------------------------------------------------------
@pytest.mark.parametrize("parser_type", ["SLR(1)", "CLR(1)", "LALR(1)"])
def test_simulate_accepts(parser_type):
    result = analyze(EXPRESSION, parser_type)
    sim = simulate_input(result, "id + id * id")
    assert sim.accepted
    assert sim.error is None
    assert sim.steps[-1].action == "accept"
    assert sim.parse_tree is not None
    assert sim.parse_tree.symbol == "E"


@pytest.mark.parametrize("parser_type", ["SLR(1)", "CLR(1)", "LALR(1)"])
def test_simulate_rejects(parser_type):
    result = analyze(EXPRESSION, parser_type)
    sim = simulate_input(result, "id +")
    assert not sim.accepted
    assert sim.error is not None
    assert sim.parse_tree is None


@pytest.mark.parametrize("parser_type", ["SLR(1)", "CLR(1)", "LALR(1)"])
def test_simulate_epsilon(parser_type):
    result = analyze(EPSILON_GRAMMAR, parser_type)
    assert simulate_input(result, "a b").accepted
    assert simulate_input(result, "b").accepted
    assert not simulate_input(result, "a").accepted


def test_parse_tree_structure():
    result = analyze(EXPRESSION, "SLR(1)")
    sim = simulate_input(result, "id")
    assert sim.accepted
    root = sim.parse_tree
    assert root.symbol == "E"
    # E -> T -> F -> id
    node = root
    depth = 0
    while node.children:
        node = node.children[0]
        depth += 1
    assert depth == 3
    assert node.symbol == "id"
    assert node.value == "id"


def test_simulation_steps_capture_stack_and_input():
    result = analyze(EXPRESSION, "SLR(1)")
    sim = simulate_input(result, "id + id")
    assert len(sim.steps) >= 2
    first = sim.steps[0]
    assert first.action == "start"
    assert first.stack_symbols == ["$"]
    assert first.input_remaining == ["id", "+", "id", "$"]


def test_unknown_parser_type_raises():
    with pytest.raises(ValueError):
        analyze(EXPRESSION, "LR(2)")


# ----------------------------------------------------------------------
# Tokenization
# ----------------------------------------------------------------------
def test_tokenize_splits_unspaced_operators():
    from core.parser_simulator import tokenize

    grammar = parse_grammar(EXPRESSION)
    assert tokenize("id+id", grammar) == ["id", "+", "id"]
    assert tokenize("(id)", grammar) == ["(", "id", ")"]
    assert tokenize("id+id*id", grammar) == ["id", "+", "id", "*", "id"]


def test_tokenize_respects_whitespace():
    from core.parser_simulator import tokenize

    grammar = parse_grammar(EXPRESSION)
    assert tokenize("id   +   id", grammar) == ["id", "+", "id"]


def test_tokenize_unknown_token():
    from core.parser_simulator import tokenize

    grammar = parse_grammar(EXPRESSION)
    assert tokenize("id @ id", grammar) == ["id", "@", "id"]


@pytest.mark.parametrize("parser_type", ["SLR(1)", "CLR(1)", "LALR(1)"])
def test_simulate_accepts_unspaced_input(parser_type):
    result = analyze(EXPRESSION, parser_type)
    assert simulate_input(result, "id+id").accepted
    assert simulate_input(result, "id+id*id").accepted
    assert simulate_input(result, "(id+id)*id").accepted
    assert not simulate_input(result, "id+").accepted
    assert not simulate_input(result, "").accepted


# ----------------------------------------------------------------------
# Textbook display ordering / formatting
# ----------------------------------------------------------------------
def test_lr0_state_items_grouped_by_production_order():
    automaton = LRAutomaton(parse_grammar(EXPRESSION))
    items = automaton.get_state(0).sorted_items()
    lhs_order: list[str] = []
    for item in items:
        if item.lhs not in lhs_order:
            lhs_order.append(item.lhs)
    # Definition order, augmented start first, never alphabetical.
    assert lhs_order == ["S'", "E", "T", "F"]


def test_lr0_items_render_with_bullet_and_alignment():
    automaton = LRAutomaton(parse_grammar(EXPRESSION))
    text = automaton.get_state(0).get_items_string()
    assert "S' -> •E" in text
    assert "E  -> •E + T" in text
    # Dots of the padded non-terminals line up in the same column.
    lines = text.splitlines()
    dot_columns = {line.index("•") for line in lines}
    assert len(dot_columns) == 1


def test_transition_rows_follow_grammar_symbol_order():
    automaton = LRAutomaton(parse_grammar(EXPRESSION))
    rows = automaton.get_state(0).get_transition_rows()
    consumed = [row[2] for row in rows]
    # Each item gets its own row (duplicates included), but the first
    # appearance of every symbol follows grammar order.
    distinct = list(dict.fromkeys(consumed))
    assert distinct == ["E", "T", "F", "(", "id"]
    # There is one row per non-completed item in the state.
    assert len(rows) == len(automaton.get_state(0).items)


def test_action_and_goto_columns_use_textbook_order():
    result = analyze(EXPRESSION, "SLR(1)")
    assert result.table.terminals == ["id", "+", "*", "(", ")", "$"]
    assert result.table.non_terminals == ["E", "T", "F"]


def test_accept_is_rendered_as_a_word():
    result = analyze(EXPRESSION, "SLR(1)")
    assert result.table.get_action(1, "$").to_string() == "Accept"


def test_production_numbers_start_with_augmented_rule():
    from core.table_builder import assign_production_numbers

    numbers, rules = assign_production_numbers(parse_grammar(EXPRESSION))
    assert rules[0] == ("S'", ("E",))
    assert numbers[("S'", ("E",))] == 0
    assert numbers[("E", ("E", "+", "T"))] == 1
    assert numbers[("E", ("T",))] == 2


# ----------------------------------------------------------------------
# LR dot movement (GOTO advances exactly one symbol)
# ----------------------------------------------------------------------
def _nested_grammar() -> Grammar:
    """A grammar mirroring ``C -> M A`` with ``A -> I | P | W``."""
    return Grammar(
        start_symbol="C",
        productions={
            "C": [["M", "A"]],
            "M": [["m"]],
            "A": [["I"], ["P"], ["W"]],
            "I": [["i"]],
            "P": [["p"]],
            "W": [["w"]],
        },
    )


def test_goto_moves_dot_one_symbol_only():
    grammar = _nested_grammar()
    seed = {LRItem(lhs="C", rhs=("M", "A"), dot=0)}
    result = goto(seed, "M", grammar)
    keys = {item.key() for item in result}

    # C -> • M A  GOTO(M)  =>  C -> M • A   (dot = 1)
    assert ("C", ("M", "A"), 1, "") in keys
    # It must NOT consume the whole remainder: C -> M A • (dot = 2) is wrong.
    assert ("C", ("M", "A"), 2, "") not in keys

    # Closure runs after the move: the dot before A pulls in A's productions.
    assert ("A", ("I",), 0, "") in keys
    assert ("A", ("P",), 0, "") in keys
    assert ("A", ("W",), 0, "") in keys


def test_goto_second_transition_moves_dot_one_more():
    grammar = _nested_grammar()
    first = goto({LRItem(lhs="C", rhs=("M", "A"), dot=0)}, "M", grammar)
    second = goto(first, "A", grammar)
    keys = {item.key() for item in second}
    # C -> M • A  GOTO(A)  =>  C -> M A •   (dot = 2)
    assert ("C", ("M", "A"), 2, "") in keys


def test_canonical_collection_matches_textbook_goto():
    grammar = parse_grammar(EXPRESSION)
    augmented = augment_grammar(grammar)
    automaton = LRAutomaton(grammar, augmented_grammar=augmented)

    # I0 = closure(start item).
    start_body = augmented.get_productions_for(augmented.start_symbol)[0]
    seed = {LRItem(lhs=augmented.start_symbol, rhs=tuple(start_body), dot=0)}
    assert automaton.get_state(0).items == closure(seed, augmented)

    # Every stored transition equals GOTO(source state, symbol).
    for state in automaton.states:
        for symbol, target in state.transitions.items():
            expected = goto(state.items, symbol, augmented)
            assert automaton.get_state(target).items == expected, (
                f"transition I{state.state_id} --{symbol}--> I{target} "
                "does not match GOTO(source, symbol)"
            )

    # No transition may skip symbols: every moved item advances by exactly one.
    for state in automaton.states:
        for item in state.items:
            symbol = item.next_symbol()
            if symbol is None:
                continue
            target = automaton.get_state(state.transitions[symbol])
            moved = item.advance_dot()
            assert moved in target.items


# ----------------------------------------------------------------------
# Textbook LR states for the "C -> MA" grammar (dot moves one symbol)
# ----------------------------------------------------------------------
NESTED_TEXT = """S -> C
C -> MA
C -> T
A -> I
A -> P
A -> W"""


def test_nested_grammar_i0_is_closure_of_start():
    automaton = analyze(NESTED_TEXT, "SLR(1)").automaton
    text = automaton.get_state(0).get_items_string()
    assert "S' -> •S" in text
    assert "S  -> •C" in text
    assert "C  -> •M A" in text
    assert "C  -> •T" in text


def test_nested_grammar_goto_m_moves_one_symbol():
    automaton = analyze(NESTED_TEXT, "SLR(1)").automaton
    state_m = automaton.get_state(automaton.get_state(0).transitions["M"])
    text = state_m.get_items_string()
    # Dot advanced over M only, never over "MA".
    assert "C -> M• A" in text
    assert "C -> M A•" not in text
    # Closure after the move pulls in A's productions.
    assert "A -> •I" in text
    assert "A -> •P" in text
    assert "A -> •W" in text


def test_nested_grammar_goto_a_completes_production():
    automaton = analyze(NESTED_TEXT, "SLR(1)").automaton
    state_m = automaton.get_state(automaton.get_state(0).transitions["M"])
    state_a = automaton.get_state(state_m.transitions["A"])
    assert "C -> M A•" in state_a.get_items_string()


def test_transition_consume_is_a_single_symbol():
    automaton = analyze(NESTED_TEXT, "SLR(1)").automaton
    consumes = {
        row[2] for state in automaton.states for row in state.get_transition_rows()
    }
    # Each transition consumes exactly one grammar symbol.
    assert "M" in consumes
    assert "A" in consumes
    assert "MA" not in consumes