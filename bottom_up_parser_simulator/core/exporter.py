"""Export analysis results to CSV, Markdown, HTML and DOT."""

from __future__ import annotations

from typing import List

from core.logging_config import get_logger

logger = get_logger(__name__)


def _format_set(values) -> str:
    if not values:
        return "{ }"
    return "{ " + ", ".join(sorted(values)) + " }"


def table_to_csv(analysis) -> str:
    """Return ACTION and GOTO entries as a single CSV document.

    Columns: ``Table,State,Symbol,Entry``.
    """
    table = analysis.table
    rows: List[str] = ["Table,State,Symbol,Entry"]
    for (state, terminal), action in sorted(table.action.items()):
        rows.append(f"ACTION,{state},{terminal},{action.to_string()}")
    for (state, non_terminal), target in sorted(table.goto.items()):
        rows.append(f"GOTO,{state},{non_terminal},{target}")
    return "\n".join(rows) + "\n"


def _action_cell(analysis, state: int, terminal: str) -> str:
    action = analysis.table.get_action(state, terminal)
    return action.to_string() if action else ""


def _goto_cell(analysis, state: int, non_terminal: str) -> str:
    target = analysis.table.get_goto(state, non_terminal)
    return str(target) if target is not None else ""


def analysis_to_markdown(analysis) -> str:
    """Return a Markdown report of the whole analysis."""
    table = analysis.table
    lines: List[str] = []
    lines.append(f"# Analysis Report — {analysis.parser_type}")
    lines.append("")
    lines.append(f"- States: **{table.num_states}**")
    lines.append(f"- Terminals: {', '.join(table.terminals) if table.terminals else '(none)'}")
    lines.append(
        f"- Non-terminals: {', '.join(table.non_terminals) if table.non_terminals else '(none)'}"
    )
    lines.append(f"- Conflicts: **{len(analysis.conflicts)}** "
                 f"(resolved {len(analysis.resolutions)}, "
                 f"unresolved {len(analysis.unresolved_conflicts)})")
    if analysis.transforms:
        lines.append(f"- Transforms applied: {', '.join(analysis.transforms)}")
    if len(analysis.precedence) > 0:
        lines.append(f"- Precedence declarations: {len(analysis.precedence)}")
    lines.append("")

    lines.append("## Grammar")
    lines.append("")
    lines.append("```")
    lines.append(analysis.grammar_text)
    lines.append("```")
    lines.append("")

    lines.append("## FIRST / FOLLOW")
    lines.append("")
    lines.append("| Symbol | FIRST | FOLLOW |")
    lines.append("| --- | --- | --- |")
    for nt in sorted(analysis.grammar.non_terminals):
        first = analysis.first.get(nt, set())
        follow = analysis.follow.get(nt, set())
        lines.append(f"| {nt} | {_format_set(first)} | {_format_set(follow)} |")
    for terminal in sorted(analysis.grammar.terminals):
        first = analysis.first.get(terminal, {terminal})
        lines.append(f"| {terminal} | {_format_set(first)} | - |")
    lines.append("")

    if analysis.conflicts:
        lines.append("## Conflicts")
        lines.append("")
        resolved = {(r.state, r.terminal): r for r in analysis.resolutions}
        lines.append("| State | Terminal | Type | Actions | Resolution |")
        lines.append("| --- | --- | --- | --- | --- |")
        for conflict in analysis.conflicts:
            resolution = resolved.get((conflict.state, conflict.terminal))
            resolution_text = (
                f"{resolution.chosen.to_string()} ({resolution.description})"
                if resolution
                else "unresolved"
            )
            lines.append(
                f"| {conflict.state} | {conflict.terminal} | {conflict.conflict_type} "
                f"| {conflict.actions_summary()} | {resolution_text} |"
            )
        lines.append("")

    lines.append("## ACTION Table")
    lines.append("")
    header = "| State | " + " | ".join(table.terminals) + " |"
    lines.append(header)
    lines.append("| --- | " + " | ".join(["---"] * len(table.terminals)) + " |")
    for state in range(table.num_states):
        cells = [_action_cell(analysis, state, t) for t in table.terminals]
        lines.append(f"| {state} | " + " | ".join(cells) + " |")
    lines.append("")

    lines.append("## GOTO Table")
    lines.append("")
    header = "| State | " + " | ".join(table.non_terminals) + " |"
    lines.append(header)
    lines.append("| --- | " + " | ".join(["---"] * len(table.non_terminals)) + " |")
    for state in range(table.num_states):
        cells = [_goto_cell(analysis, state, nt) for nt in table.non_terminals]
        lines.append(f"| {state} | " + " | ".join(cells) + " |")
    lines.append("")

    return "\n".join(lines)


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def analysis_to_html(analysis) -> str:
    """Return a styled HTML report of the analysis."""
    table = analysis.table
    parts: List[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append("<html><head><meta charset='utf-8'>")
    parts.append(f"<title>{_html_escape(analysis.parser_type)} Analysis</title>")
    parts.append(
        "<style>"
        "body{font-family:Segoe UI,Arial,sans-serif;margin:24px;color:#222;}"
        "table{border-collapse:collapse;margin:12px 0;}"
        "th,td{border:1px solid #bbb;padding:4px 8px;text-align:center;font-size:13px;}"
        "th{background:#f0f0f0;}"
        "pre{background:#f7f7f7;padding:12px;border:1px solid #ddd;border-radius:4px;}"
        ".shift{background:#CFE2FF;}.reduce{background:#D9EAD3;}.accept{background:#93C47D;}"
        ".resolved{background:#D9EAD3;}.unresolved{background:#F4C7C3;}"
        "</style></head><body>"
    )
    parts.append(f"<h1>Analysis Report — {_html_escape(analysis.parser_type)}</h1>")
    parts.append(
        f"<p>States: <b>{table.num_states}</b> &nbsp; "
        f"Conflicts: <b>{len(analysis.conflicts)}</b> "
        f"(resolved {len(analysis.resolutions)}, "
        f"unresolved {len(analysis.unresolved_conflicts)})</p>"
    )

    parts.append("<h2>Grammar</h2>")
    parts.append(f"<pre>{_html_escape(analysis.grammar_text)}</pre>")

    parts.append("<h2>ACTION Table</h2>")
    parts.append("<table><tr><th>State</th>")
    for terminal in table.terminals:
        parts.append(f"<th>{_html_escape(terminal)}</th>")
    parts.append("</tr>")
    for state in range(table.num_states):
        parts.append(f"<tr><td>{state}</td>")
        for terminal in table.terminals:
            action = table.get_action(state, terminal)
            cls = action.action_type if action else ""
            text = action.to_string() if action else ""
            parts.append(f"<td class='{cls}'>{_html_escape(text)}</td>")
        parts.append("</tr>")
    parts.append("</table>")

    parts.append("<h2>GOTO Table</h2>")
    parts.append("<table><tr><th>State</th>")
    for nt in table.non_terminals:
        parts.append(f"<th>{_html_escape(nt)}</th>")
    parts.append("</tr>")
    for state in range(table.num_states):
        parts.append(f"<tr><td>{state}</td>")
        for nt in table.non_terminals:
            target = table.get_goto(state, nt)
            parts.append(f"<td>{target if target is not None else '.'}</td>")
        parts.append("</tr>")
    parts.append("</table>")

    parts.append("</body></html>")
    return "\n".join(parts)


def automaton_to_dot(analysis) -> str:
    """Return the Graphviz DOT representation of the automaton."""
    return analysis.automaton.to_dot()