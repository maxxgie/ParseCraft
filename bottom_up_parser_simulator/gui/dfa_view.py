"""DFA visualisation of the LR automaton."""

from __future__ import annotations

from typing import Dict, List

from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

from core.logging_config import get_logger
from gui.graph_canvas import GraphCanvas, GraphEdge, GraphNode

logger = get_logger(__name__)

AUGMENTED_START = "S'"
X_GAP = 240.0
Y_GAP = 96.0


class DFAView(QWidget):
    """Renders the LR automaton as a layered, zoomable graph."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.header = QLabel("Generate a grammar to see the DFA.")
        self.header.setStyleSheet("color: #555;")
        layout.addWidget(self.header)

        self.canvas = GraphCanvas()
        layout.addWidget(self.canvas, 1)

    def clear(self) -> None:
        """Reset the view."""
        self.canvas.render([], [])
        self.header.setText("Generate a grammar to see the DFA.")
        self.header.setStyleSheet("color: #555;")

    def update_from(self, analysis) -> None:
        """Build and render the automaton graph."""
        automaton = analysis.automaton
        states = automaton.states
        start = automaton.start_state
        augmented_start = getattr(
            getattr(automaton, "augmented_grammar", None),
            "start_symbol",
            AUGMENTED_START,
        )

        # Group states into BFS layers starting from the start state.
        layers: Dict[int, List[int]] = {}
        visited = {start: 0}
        queue = [start]
        while queue:
            current = queue.pop(0)
            layer = visited[current]
            layers.setdefault(layer, []).append(current)
            for symbol, target in states[current].transitions.items():
                if target not in visited:
                    visited[target] = layer + 1
                    queue.append(target)

        # Any unreachable states (defensive) go into layer 0.
        for state in states:
            if state.state_id not in visited:
                layers.setdefault(0, []).append(state.state_id)

        nodes: List[GraphNode] = []
        for layer, members in layers.items():
            for idx, state_id in enumerate(sorted(members)):
                state = states[state_id]
                y = (idx - (len(members) - 1) / 2) * Y_GAP + layer * 28
                kind = "accept" if self._is_accept(state.items, augmented_start) else "state"
                nodes.append(
                    GraphNode(
                        id=state_id,
                        label=f"I{state_id}",
                        x=layer * X_GAP,
                        y=y,
                        kind=kind,
                    )
                )

        # Merge parallel transitions between the same pair of states.
        merged: Dict[tuple, List[str]] = {}
        for (from_id, symbol), to_id in automaton.transitions.items():
            merged.setdefault((from_id, to_id), []).append(symbol)

        edges: List[GraphEdge] = [
            GraphEdge(src=frm, dst=to, label=", ".join(sorted(labels)))
            for (frm, to), labels in merged.items()
        ]

        self.canvas.render(nodes, edges)
        self.header.setText(
            f"{analysis.parser_type}: {len(states)} states, "
            f"{len(automaton.transitions)} transitions. "
            "Scroll to zoom, drag to pan."
        )
        self.header.setStyleSheet("color: #333;")

    @staticmethod
    def _is_accept(items, augmented_start: str = AUGMENTED_START) -> bool:
        for item in items:
            if item.lhs == augmented_start and item.is_complete():
                return True
        return False