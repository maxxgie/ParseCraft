"""Reusable zoomable/pannable graph canvas built on QGraphicsView.

Both the DFA view and the parse-tree view render their diagrams through this
widget. Callers compute node positions (layered layout for the DFA, tidy tree
layout for parse trees) and hand a list of :class:`GraphNode` / :class:`GraphEdge`
objects to :meth:`GraphCanvas.render`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPainter,
    QPen,
    QPolygonF,
    QTransform,
)
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

NODE_COLORS = {
    "state": QColor("#FFF3CD"),
    "accept": QColor("#D4EDDA"),
    "error": QColor("#F8D7DA"),
    "root": QColor("#CFE2FF"),
    "nonterminal": QColor("#E2D9F3"),
    "terminal": QColor("#D1ECF1"),
}

NODE_BORDER = QColor("#555555")


@dataclass
class GraphNode:
    """A positioned node in a diagram.

    Attributes:
        id: Unique identifier used to resolve edges.
        label: Text drawn inside the node.
        x: Center x coordinate in scene units.
        y: Center y coordinate in scene units.
        kind: One of ``state``, ``accept``, ``root``, ``nonterminal``,
            ``terminal`` (drives the fill colour).
        width: Optional explicit width; auto-sized from the label if omitted.
        height: Optional explicit height.
    """

    id: object
    label: str
    x: float
    y: float
    kind: str = "state"
    width: Optional[float] = None
    height: Optional[float] = None


@dataclass
class GraphEdge:
    """A directed edge between two nodes.

    Attributes:
        src: Source node id.
        dst: Destination node id.
        label: Optional transition label drawn near the edge.
    """

    src: object
    dst: object
    label: str = ""


class _NodeItem(QGraphicsRectItem):
    """Rounded rectangle node that draws its label centred."""

    def __init__(self, node: GraphNode) -> None:
        width = node.width or max(70.0, 9.0 * len(node.label) + 24.0)
        height = node.height or 34.0
        super().__init__(-width / 2, -height / 2, width, height)
        self.node = node
        self.setPos(QPointF(node.x, node.y))
        self.setBrush(QBrush(NODE_COLORS.get(node.kind, QColor("#FFFFFF"))))
        self.setPen(QPen(NODE_BORDER, 1.5))
        self.setZValue(1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        self.text = QGraphicsSimpleTextItem(node.label, self)
        font = QFont("Segoe UI", 9)
        self.text.setFont(font)
        self.text.setBrush(QBrush(QColor("#222222")))
        brect = self.text.boundingRect()
        self.text.setPos(-brect.width() / 2, -brect.height() / 2)


class GraphCanvas(QGraphicsView):
    """A QGraphicsView with wheel zoom and drag panning."""

    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(
            QGraphicsView.ViewportAnchor.AnchorUnderMouse
        )
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#FAFAFA"))
        self.setMinimumSize(200, 200)
        self._zoom = 1.0
        self._positions: Dict[object, Tuple[float, float]] = {}

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def render(
        self,
        nodes: List[GraphNode],
        edges: List[GraphEdge],
        fit: bool = True,
    ) -> None:
        """Clear the scene and draw the given graph.

        Args:
            nodes: Node descriptors with positions.
            edges: Edge descriptors referencing node ids.
            fit: Whether to fit the whole graph into the viewport.
        """
        self._scene.clear()
        self._zoom = 1.0
        self.setTransform(QTransform())

        positions: Dict[object, QPointF] = {
            n.id: QPointF(n.x, n.y) for n in nodes
        }

        # Edges first so nodes draw on top.
        for edge in edges:
            if edge.src not in positions or edge.dst not in positions:
                continue
            self._draw_edge(positions[edge.src], positions[edge.dst], edge.label)

        for node in nodes:
            self._scene.addItem(_NodeItem(node))

        if fit and nodes:
            self._scene.setSceneRect(self._scene.itemsBoundingRect())
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _draw_edge(self, src: QPointF, dst: QPointF, label: str) -> None:
        """Draw a straight arrowed edge between two points with a label."""
        # Shorten the line so it starts/ends at the node borders.
        dx = dst.x() - src.x()
        dy = dst.y() - src.y()
        length = max((dx * dx + dy * dy) ** 0.5, 1e-6)
        ux, uy = dx / length, dy / length
        pad = 34.0
        start = QPointF(src.x() + ux * pad, src.y() + uy * pad)
        end = QPointF(dst.x() - ux * pad, dst.y() - uy * pad)

        pen = QPen(QColor("#444444"), 1.5)
        line = self._scene.addLine(start.x(), start.y(), end.x(), end.y(), pen)
        line.setZValue(0)

        # Arrow head.
        head_len = 10.0
        head_w = 6.0
        left = QPointF(
            end.x() - ux * head_len - uy * head_w,
            end.y() - uy * head_len + ux * head_w,
        )
        right = QPointF(
            end.x() - ux * head_len + uy * head_w,
            end.y() - uy * head_len - ux * head_w,
        )
        arrow = self._scene.addPolygon(
            QPolygonF([end, left, right]), QPen(Qt.PenStyle.NoPen), QBrush(QColor("#444444"))
        )
        arrow.setZValue(0)

        if label:
            mid = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
            text = QGraphicsSimpleTextItem(label)
            text.setBrush(QBrush(QColor("#0B5394")))
            text.setFont(QFont("Segoe UI", 8))
            text.setZValue(2)
            brect = text.boundingRect()
            text.setPos(mid.x() - brect.width() / 2, mid.y() - brect.height() / 2 - 8)

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def wheelEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Zoom with the mouse wheel (Ctrl not required)."""
        if event.angleDelta().y() > 0:
            factor = 1.15
        else:
            factor = 1 / 1.15
        self._zoom = max(0.1, min(self._zoom * factor, 8.0))
        self.scale(factor, factor)

    def reset_zoom(self) -> None:
        """Reset zoom to 100% and centre the view."""
        self.setTransform(QTransform())
        self._zoom = 1.0
        if self._scene.sceneRect().width() > 0:
            self.fitInView(
                self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio
            )

    def render_to_png(self, path: str, background: str = "#FAFAFA") -> bool:
        """Render the current scene to a PNG file.

        Args:
            path: Destination file path.
            background: Background fill colour.

        Returns:
            ``True`` if the image was written, ``False`` if the scene is empty.
        """
        rect = self._scene.itemsBoundingRect()
        if rect.isEmpty():
            return False
        margin = 20.0
        width = int(rect.width()) + 2 * int(margin)
        height = int(rect.height()) + 2 * int(margin)
        image = QImage(max(width, 1), max(height, 1), QImage.Format.Format_ARGB32)
        image.fill(QColor(background))
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        target = QRectF(0, 0, image.width(), image.height())
        self._scene.render(painter, target, rect)
        painter.end()
        return image.save(path)