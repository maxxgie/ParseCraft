"""High-level analysis engine.

Ties the grammar parser, FIRST/FOLLOW computation, automaton construction,
and table generation together behind a single :func:`analyze` call, plus a
convenience :func:`simulate_input` wrapper used by the GUI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Set

from core.automaton import LRAutomaton
from core.conflict_resolution import (
    Resolution,
    ResolutionConfig,
    resolve_conflicts,
)
from core.first_follow import compute_first, compute_follow
from core.grammar_parser import GrammarParseError, parse_grammar, validate_grammar
from core.grammar_transform import (
    build_grammar_stages,
    describe_features,
    has_common_prefixes,
    has_left_recursion,
)
from core.logging_config import get_logger
from core.lr1_automaton import LR1Automaton
from core.parser_simulator import SimulationResult, simulate
from core.precedence import PrecedenceInfo, parse_precedence
from core.table_builder import MODES, assign_production_numbers, build_parsing_table
from models.grammar import Grammar
from models.parsing_table import Conflict, ParseTable

logger = get_logger(__name__)

ALL_PARSER_TYPES = ["Shift Reduce", "LR(0)", "SLR(1)", "CLR(1)", "LALR(1)"]


@dataclass
class AnalysisResult:
    """Everything computed for a grammar under a chosen parser type."""

    grammar: Grammar
    parser_type: str
    mode: str
    first: Dict[str, Set[str]]
    follow: Dict[str, Set[str]]
    automaton: object
    table: ParseTable
    conflicts: List[Conflict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    transforms: List[str] = field(default_factory=list)
    original_text: str = ""
    precedence: PrecedenceInfo = field(default_factory=PrecedenceInfo)
    resolutions: List[Resolution] = field(default_factory=list)
    resolution_config: ResolutionConfig = field(default_factory=ResolutionConfig)
    stages: Dict[str, str] = field(default_factory=dict)

    @property
    def is_conflict_free(self) -> bool:
        """Return ``True`` when no conflicts were detected."""
        return not self.conflicts

    @property
    def unresolved_conflicts(self) -> List[Conflict]:
        """Return conflicts that were not resolved by the chosen strategy."""
        if not self.resolution_config.enabled:
            return list(self.conflicts)
        resolved = {
            (r.conflict.state, r.conflict.terminal) for r in self.resolutions
        }
        return [c for c in self.conflicts if (c.state, c.terminal) not in resolved]

    @property
    def grammar_text(self) -> str:
        """Return the grammar actually used (after any transformations)."""
        return self.grammar.to_text()


def grammar_features(text: str) -> Dict[str, bool]:
    """Inspect raw grammar text without building an automaton.

    Args:
        text: Grammar text in BNF format.

    Returns:
        A dict with ``left_recursion`` and ``common_prefixes`` flags, plus
        ``note`` describing the shape of the grammar.
    """
    try:
        grammar = parse_grammar(text)
    except GrammarParseError:
        return {
            "left_recursion": False,
            "common_prefixes": False,
            "note": "invalid grammar",
        }
    return {
        "left_recursion": has_left_recursion(grammar),
        "common_prefixes": has_common_prefixes(grammar),
        "note": describe_features(grammar),
    }


def build_automaton(grammar: Grammar, mode: str):
    """Construct the correct automaton for the given mode.

    Args:
        grammar: The original grammar.
        mode: One of ``lr0``, ``slr1``, ``clr1``, ``lalr1``.

    Returns:
        An automaton exposing ``states``, ``transitions`` and ``start_state``.
    """
    if mode in ("lr0", "slr1"):
        return LRAutomaton(grammar)
    return LR1Automaton(grammar, merge=(mode == "lalr1"))


def analyze(
    text: str,
    parser_type: str,
    remove_left_recursion: bool = False,
    left_factoring: bool = False,
    remove_epsilon: bool = False,
    remove_unit: bool = False,
    remove_useless: bool = False,
    resolution: ResolutionConfig | None = None,
) -> AnalysisResult:
    """Parse ``text`` and compute the full analysis for ``parser_type``.

    LR parsers always operate on the **original** grammar. The grammar
    transformation flags are accepted for API compatibility but are
    deliberately ignored by this bottom-up pipeline: applying left-recursion
    removal or left factoring to an LR grammar would change the automaton and
    is not valid compiler-construction practice. Transformation belongs to the
    top-down pipeline (:func:`core.topdown.engine.analyze_topdown`).

    Args:
        text: Grammar text in BNF format (may include ``%left``/``%right``/
            ``%nonassoc`` precedence declarations).
        parser_type: One of :data:`ALL_PARSER_TYPES`.
        remove_left_recursion: Ignored for LR parsers (original grammar is used).
        left_factoring: Ignored for LR parsers (original grammar is used).
        remove_epsilon: Ignored for LR parsers (original grammar is used).
        remove_unit: Ignored for LR parsers (original grammar is used).
        remove_useless: Ignored for LR parsers (original grammar is used).
        resolution: Conflict-resolution strategy. When enabled, conflicts are
            resolved after the table is built (with an explanation).

    Returns:
        A fully populated :class:`AnalysisResult`. Its ``grammar`` attribute is
        always the original grammar; ``transforms`` is therefore empty.

    Raises:
        ValueError: If ``parser_type`` is unknown.
        GrammarParseError: If the grammar text cannot be parsed.
    """
    if parser_type not in MODES:
        raise ValueError(
            f"Unknown parser type '{parser_type}'. Expected one of {ALL_PARSER_TYPES}."
        )

    mode = MODES[parser_type]
    original = parse_grammar(text)
    warnings = validate_grammar(original)
    precedence = parse_precedence(text)
    resolution = resolution or ResolutionConfig()

    # LR parsers must operate on the original grammar. Any transform requested
    # by the caller is intentionally not applied and is reported instead of
    # being silently honoured.
    ignored: List[str] = []
    if remove_left_recursion:
        ignored.append("left-recursion removal")
    if left_factoring:
        ignored.append("left factoring")
    if remove_epsilon:
        ignored.append("ε-production removal")
    if remove_unit:
        ignored.append("unit-production removal")
    if remove_useless:
        ignored.append("useless-symbol removal")
    if ignored:
        logger.info(
            "%s parser uses the original grammar; ignoring transforms: %s",
            parser_type,
            ", ".join(ignored),
        )

    transforms: List[str] = []
    grammar = original

    first = compute_first(grammar)
    follow = compute_follow(grammar, first)

    automaton = build_automaton(grammar, mode)
    table, conflicts = build_parsing_table(automaton, grammar, mode, follow)

    # Resolve conflicts if requested.
    resolutions: List[Resolution] = []
    if resolution.enabled and conflicts:
        resolutions = resolve_conflicts(table, conflicts, resolution, precedence)

    # Sanity: make sure rule numbers line up with the table.
    assign_production_numbers(grammar)

    result = AnalysisResult(
        grammar=grammar,
        parser_type=parser_type,
        mode=mode,
        first=first,
        follow=follow,
        automaton=automaton,
        table=table,
        conflicts=conflicts,
        warnings=warnings,
        transforms=transforms,
        original_text=text,
        precedence=precedence,
        resolutions=resolutions,
        resolution_config=resolution,
        stages=build_grammar_stages(original, grammar),
    )
    logger.info(
        "Analysis complete: %s, %d states, %d conflicts, %d resolved, %d warnings%s",
        parser_type,
        len(automaton.states),
        len(conflicts),
        len(resolutions),
        len(warnings),
        f", transforms: {', '.join(transforms)}" if transforms else "",
    )
    return result


def simulate_input(
    analysis: AnalysisResult, input_string: str
) -> SimulationResult:
    """Run a simulation against a previously computed analysis.

    Args:
        analysis: A result from :func:`analyze`.
        input_string: Whitespace-separated input terminals.

    Returns:
        The :class:`SimulationResult`.
    """
    return simulate(analysis.table, analysis.grammar, input_string)