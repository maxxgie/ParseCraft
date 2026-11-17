"""Reusable zoomable/pannable graph canvas built on QGraphicsView.

Both the DFA view and the parse-tree view render their diagrams through this
widget. Callers compute node positions (layered layout for the DFA, tidy tree
layout for parse trees) and hand a list of :class:`GraphNode` / :class:`GraphEdge`
objects to :meth:`GraphCanvas.render`.

On top of basic rendering the canvas offers:

* rounded ``card`` nodes with distinct borders per :attr:`GraphNode.kind`;
* click selection via the :attr:`GraphCanvas.node_selected` signal;
* subtree highlighting via :meth:`GraphCanvas.set_highlight`;
* zoom controls (:meth:`zoom_in`, :meth:`zoom_out`, :meth:`fit_view`,
  :meth:`center_view`); and
* high-resolution export to PNG / SVG / PDF via :meth:`render_to_file`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QImage,
    QPageSize,
    QPainter,
    QPainterPath,
    QPdfWriter,
    QPen,
    QPolygonF,
    QTransform,
)
from PyQt6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsSimpleTextItem,
    QGraphicsView,
)

NODE_COLORS = {
    "state": QColor("#FFF3CD"),
    "accept": QColor("#D4EDDA"),
    "error": QColor("#F8D7DA"),
    "root": QColor("#CFE2FF"),
    "nonterminal": QColor("#E7E0F7"),
    "terminal": QColor("#D5F0E3"),
}

NODE_BORDER = QColor("#64748B")
NODE_BORDER_HL = QColor("#2563EB")
HIGHLIGHT_FILL = QColor("#DBEAFE")


@dataclass
class GraphNode:
    """A positioned node in a diagram.

    Attributes:
        id: Unique identifier used to resolve edges and clicks.
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
    tip: str = ""


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


class _NodeItem(QGraphicsPathItem):
    """Rounded card node that draws its label centred."""

    RADIUS = 8.0

    def __init__(self, node: GraphNode) -> None:
        width = node.width or max(70.0, 8.5 * len(node.label) + 26.0)
        height = node.height or 34.0
        path = QPainterPath()
        path.addRoundedRect(QRectF(-width / 2, -height / 2, width, height), self.RADIUS, self.RADIUS)
        super().__init__(path)
        self.node = node
        self.base_fill = NODE_COLORS.get(node.kind, QColor("#FFFFFF"))
        self.setPos(QPointF(node.x, node.y))
        self.setBrush(QBrush(self.base_fill))
        self.setPen(QPen(NODE_BORDER, 1.5))
        self.setZValue(1)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)

        self.text = QGraphicsSimpleTextItem(node.label, self)
        self.text.setFont(QFont("Segoe UI", 9))
        self.text.setBrush(QBrush(QColor("#1F2937")))
        brect = self.text.boundingRect()
        self.text.setPos(-brect.width() / 2, -brect.height() / 2)
        if node.tip:
            self.setToolTip(node.tip)

    def set_highlighted(self, on: bool) -> None:
        if on:
            self.setBrush(QBrush(HIGHLIGHT_FILL))
            self.setPen(QPen(NODE_BORDER_HL, 2.6))
            self.setZValue(2)
        else:
            self.setBrush(QBrush(self.base_fill))
            self.setPen(QPen(NODE_BORDER, 1.5))
            self.setZValue(1)


class GraphCanvas(QGraphicsView):
    """A QGraphicsView with wheel zoom, drag panning and export helpers."""

    #: Emitted with the ``GraphNode.id`` of the node the user clicked.
    node_selected = pyqtSignal(object)

    def __init__(self) -> None:
        super().__init__()
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QColor("#FAFAFA"))
        self.setMinimumSize(200, 200)
        self._zoom = 1.0
        self._positions: Dict[object, Tuple[float, float]] = {}
        self._items_by_id: Dict[object, _NodeItem] = {}
        self._highlighted: Set[object] = set()
        self._scene.selectionChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def render(
        self,
        nodes: List[GraphNode],
        edges: List[GraphEdge],
        fit: bool = True,
    ) -> None:
        """Clear the scene and draw the given graph."""
        self._scene.clear()
        self._zoom = 1.0
        self.setTransform(QTransform())
        self._items_by_id = {}
        self._highlighted = set()

        positions: Dict[object, QPointF] = {n.id: QPointF(n.x, n.y) for n in nodes}

        # Edges first so nodes draw on top.
        for edge in edges:
            if edge.src not in positions or edge.dst not in positions:
                continue
            self._draw_edge(positions[edge.src], positions[edge.dst], edge.label)

        for node in nodes:
            item = _NodeItem(node)
            self._scene.addItem(item)
            self._items_by_id[node.id] = item

        if fit and nodes:
            self._scene.setSceneRect(self._scene.itemsBoundingRect())
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _draw_edge(self, src: QPointF, dst: QPointF, label: str) -> None:
        """Draw a straight arrowed edge between two points with a label."""
        dx = dst.x() - src.x()
        dy = dst.y() - src.y()
        length = max((dx * dx + dy * dy) ** 0.5, 1e-6)
        ux, uy = dx / length, dy / length
        pad = 30.0
        start = QPointF(src.x() + ux * pad, src.y() + uy * pad)
        end = QPointF(dst.x() - ux * pad, dst.y() - uy * pad)

        pen = QPen(QColor("#64748B"), 1.4)
        line = self._scene.addLine(start.x(), start.y(), end.x(), end.y(), pen)
        line.setZValue(0)

        head_len = 9.0
        head_w = 5.5
        left = QPointF(
            end.x() - ux * head_len - uy * head_w,
            end.y() - uy * head_len + ux * head_w,
        )
        right = QPointF(
            end.x() - ux * head_len + uy * head_w,
            end.y() - uy * head_len - ux * head_w,
        )
        arrow = self._scene.addPolygon(
            QPolygonF([end, left, right]), QPen(Qt.PenStyle.NoPen), QBrush(QColor("#64748B"))
        )
        arrow.setZValue(0)

        if label:
            mid = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
            text = QGraphicsSimpleTextItem(label)
            text.setBrush(QBrush(QColor("#0B5394")))
            text.setFont(QFont("Segoe UI", 8))
            text.setZValue(3)
            brect = text.boundingRect()
            text.setPos(mid.x() - brect.width() / 2, mid.y() - brect.height() / 2 - 8)

    # ------------------------------------------------------------------
    # Highlighting
    # ------------------------------------------------------------------
    def set_highlight(self, ids: Set[object]) -> None:
        """Highlight the nodes whose id is in ``ids`` (and clear the rest)."""
        self._highlighted = set(ids)
        for node_id, item in self._items_by_id.items():
            item.set_highlighted(node_id in self._highlighted)

    def node_id_at(self, viewport_pos) -> Optional[object]:
        """Return the :attr:`GraphNode.id` under a viewport position, if any."""
        item = self.itemAt(viewport_pos)
        while item is not None:
            node = getattr(item, "node", None)
            if node is not None:
                return node.id
            item = item.parentItem()
        return None

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------
    def _on_selection_changed(self) -> None:
        items = self._scene.selectedItems()
        if not items:
            return
        item = items[0]
        node = getattr(item, "node", None)
        if node is not None:
            self.node_selected.emit(node.id)

    def wheelEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        """Zoom with the mouse wheel (Ctrl not required)."""
        if event.angleDelta().y() > 0:
            factor = 1.15
        else:
            factor = 1 / 1.15
        self._zoom = max(0.1, min(self._zoom * factor, 8.0))
        self.scale(factor, factor)

    def zoom_in(self) -> None:
        self._apply_zoom(1.2)

    def zoom_out(self) -> None:
        self._apply_zoom(1 / 1.2)

    def _apply_zoom(self, factor: float) -> None:
        self._zoom = max(0.1, min(self._zoom * factor, 8.0))
        self.scale(factor, factor)

    def center_view(self) -> None:
        """Centre the view on the scene without changing the zoom level."""
        rect = self._scene.sceneRect()
        if not rect.isEmpty():
            self.centerOn(rect.center())

    def fit_view(self) -> None:
        """Fit the whole graph into the viewport and reset zoom to 100%."""
        self.reset_zoom()

    def reset_zoom(self) -> None:
        """Reset zoom to 100% and fit the graph."""
        self.setTransform(QTransform())
        self._zoom = 1.0
        if self._scene.sceneRect().width() > 0:
            self.fitInView(self._scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _source_rect(self) -> QRectF:
        rect = self._scene.itemsBoundingRect()
        if rect.isEmpty():
            return QRectF()
        m = 24.0
        return rect.adjusted(-m, -m, m, m)

    def render_to_png(self, path: str, background: str = "#FAFAFA") -> bool:
        """Render the current scene to a PNG file (backward compatible)."""
        return self.render_to_file(path, "png", background=background)

    def render_to_file(
        self,
        path: str,
        fmt: str = "png",
        dpi: int = 300,
        background: str = "#FFFFFF",
    ) -> bool:
        """Render the scene to ``path`` as PNG, SVG or PDF at high resolution.

        Args:
            path: Destination file path.
            fmt: One of ``"png"``, ``"svg"``, ``"pdf"``.
            dpi: Raster/PDF resolution (ignored for SVG, which is vector).
            background: Fill colour behind the drawing.

        Returns:
            ``True`` if the file was written, ``False`` if the scene is empty.
        """
        src = self._source_rect()
        if src.isEmpty():
            return False
        fmt = fmt.lower()

        if fmt == "png":
            scale = max(dpi, 96) / 96.0
            width = max(1, int(src.width() * scale))
            height = max(1, int(src.height() * scale))
            image = QImage(width, height, QImage.Format.Format_ARGB32)
            image.fill(QColor(background))
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            self._scene.render(painter, QRectF(0, 0, width, height), src)
            painter.end()
            return image.save(path, "PNG")

        if fmt == "svg":
            try:
                from PyQt6.QtSvg import QSvgGenerator
            except Exception:  # pragma: no cover - QtSvg not available
                return False
            generator = QSvgGenerator()
            generator.setFileName(path)
            generator.setSize(image_size(src))
            generator.setViewBox(QRectF(0, 0, src.width(), src.height()))
            generator.setTitle("Diagram")
            painter = QPainter(generator)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            self._scene.render(
                painter, QRectF(0, 0, src.width(), src.height()), src
            )
            painter.end()
            return True

        if fmt == "pdf":
            writer = QPdfWriter(path)
            writer.setPageSize(QPageSize(QPageSize.PageSizeId.A3))
            writer.setResolution(dpi)
            painter = QPainter(writer)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            vp = QRectF(0, 0, writer.width(), writer.height())
            s = min(vp.width() / src.width(), vp.height() / src.height())
            target = QRectF(0, 0, src.width() * s, src.height() * s)
            target.moveCenter(vp.center())
            self._scene.render(painter, target, src)
            painter.end()
            return True

        return False


def image_size(rect: QRectF):
    """Return a QSize large enough to hold ``rect`` (used for SVG sizing)."""
    from PyQt6.QtCore import QSize

    return QSize(max(1, int(rect.width())), max(1, int(rect.height())))