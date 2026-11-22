from __future__ import annotations

from typing import Dict, List, Set

from core.logging_config import get_logger
from models.grammar import Grammar

logger = get_logger(__name__)

def compute_first(grammar: Grammar) -> Dict[str, Set[str]]:
    first: Dict[str, Set[str]] = {}
    for terminal in grammar.terminals:
        first[terminal] = {terminal}

    first["ɛ"] = {"ɛ"}

    for non_terminal in grammar.non_terminals:
        first[non_terminal] = set()

    changed = True
    while changed:
        changed = False
        for nt, rhs_list in grammar.productions.items():
            for rhs in rhs_list:
                if not rhs:
                    if "ɛ" not in first[nt]:
                        first[nt].add("ɛ")
                        changed = True
                    continue

                all_derive_epsilon = True
                for sym in rhs:
                    if sym == "ɛ":
                        if "ɛ" not in first[nt]:
                            first[nt].add("ɛ")
                            changed = True
                        break

                    for s in first.get(sym, set()):
                        if s != "ɛ" and s not in first[nt]:
                            first[nt].add(s)
                            changed = True

                    if "ɛ" not in first.get(sym, set()):
                        all_derive_epsilon = False

                if all_derive_epsilon:
                    if "ɛ" not in first[nt]:
                        first[nt].add("ɛ")
                        changed = True

    logger.info("FIRST sets computed for %d symbols", len(first))
    return first

def compute_follow(grammar: Grammar, first: Dict[str, Set[str]] | None = None) -> Dict[str, Set[str]]:
    if first is None:
        first = compute_first(grammar)

    follow: Dict[str, Set[str]] = {nt: set() for nt in grammar.non_terminals}

    follow[grammar.start_symbol].add("$")

    changed = True
    while changed:
        changed = False
        for nt, rhs_list in grammar.productions.items():
            for rhs in rhs_list:
                for i, sym in enumerate(rhs):
                    if sym not in grammar.non_terminals:
                        continue

                    rest = rhs[i + 1:]
                    if rest:
                        first_of_rest = set()
                        all_derive_epsilon = True
                        for s in rest:
                            first_of_rest.update(first.get(s, set()) - {"ɛ"})
                            if "ɛ" not in first.get(s, set()):
                                all_derive_epsilon = False
                                break

                        for s in first_of_rest:
                            if s not in follow[sym]:
                                follow[sym].add(s)
                                changed = True

                        if all_derive_epsilon:
                            for terminal in follow.get(nt, set()):
                                if terminal not in follow[sym]:
                                    follow[sym].add(terminal)
                                    changed = True
                    
                    else:
                        for s in follow.get(nt, set()):
                            if s not in follow[sym]:
                                follow[sym].add(s)
                                changed = True
                                    
    logger.info("FOLLOW sets computed for %d none-terminals", len(follow))
    
def compute_first_of_string(
    symbols: List[str], first: Dict[str, Set[str]]
) -> Set[str]:
    
    result = set()
    all_derive_epsilon = True

    for sym in symbols:
        if sym == "ɛ":
            continue

        result.update(first.get(sym, set()) - {"ɛ"})

        if "ɛ" not in first.get(sym, set()):
            all_derive_epsilon = False
            break

    if all_derive_epsilon:
        result.add("ɛ")

    return result


                        
    