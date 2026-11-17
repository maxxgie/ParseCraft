"""Main application window.

Hosts every view (grammar editor, FIRST/FOLLOW, LR states, DFA, ACTION/GOTO,
simulation, parse tree) inside a central tabbed workspace, provides menu and
toolbar actions, a status bar, and a dockable application log.
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QStatusBar,
    QTabWidget,
    QTextEdit,
    QToolBar,
    QWidget,
)

from core.codegen import generate_lr_parser
from core.comparison import compare_parsers
from core.database import get_database
from core.engine import analyze, grammar_features
from core.exporter import (
    analysis_to_html,
    analysis_to_markdown,
    automaton_to_dot,
    table_to_csv,
)
from core.grammar_analyzer import analyze_grammar
from core.grammar_parser import GrammarParseError, parse_grammar
from core.logging_config import get_logger
from core.topdown import TOPDOWN_METHODS, analyze_topdown
from gui.ast_view import AstView
from gui.code_view import CodeView
from gui.conflict_view import ConflictView
from gui.dfa_view import DFAView
from gui.first_follow_view import FirstFollowView
from gui.closure_goto_steps_view import ClosureGotoStepsView
from gui.grammar_analyzer_view import GrammarAnalyzerView
from gui.grammar_editor import GenerateOptions, GrammarEditor
from gui.ll1_table_view import LL1TableView
from gui.lr_items_transitions_view import LRItemsTransitionsView
from gui.lr_states_view import LRStatesView
from gui.parse_tree_view import ParseTreeView
from gui.parser_comparison_view import ParserComparisonView
from gui.settings import APP_NAME, APP_ORGANIZATION, APP_VERSION
from gui.simulation_view import SimulationView
from gui.table_view import CombinedTableView
from gui.topdown_view import TopDownView
from gui.validation_view import ValidationView

logger = get_logger(__name__)

# ----------------------------------------------------------------------
# Parser-specific tab layout
# ----------------------------------------------------------------------
# Each central tab has a stable key. A parser type maps to an ordered list of
# the keys it should display, so selecting a parser rebuilds the tab bar with
# only the relevant tabs (no horizontal scrolling, no unrelated panels).

TAB_GRAMMAR = "grammar"
TAB_FIRST_FOLLOW = "first_follow"
TAB_LR_ITEMS = "lr_items"
TAB_CLOSURE = "closure"
TAB_GOTO = "goto"
TAB_STATES = "states"
TAB_TRANSITIONS = "transitions"
TAB_VALIDATION = "validation"
TAB_DFA = "dfa"
TAB_TABLE = "table"
TAB_CONFLICTS = "conflicts"
TAB_SIMULATION = "simulation"
TAB_TOPDOWN = "topdown"
TAB_LL_TABLE = "ll_table"
TAB_PARSE_TREE = "parse_tree"
TAB_AST = "ast"
TAB_ANALYZER = "analyzer"
TAB_COMPARISON = "comparison"
TAB_CODE = "code"

# Bottom-up (LR) tabs. ``first_follow`` is inserted for the parsers that need
# FIRST/FOLLOW sets (SLR, CLR, LALR); LR(0) does not.
_LR_TABS = [
    TAB_GRAMMAR,
    TAB_LR_ITEMS,
    TAB_CLOSURE,
    TAB_STATES,
    TAB_TABLE,
    TAB_SIMULATION,
    TAB_PARSE_TREE,
    TAB_CODE,
    TAB_CONFLICTS,
    TAB_DFA,
    TAB_VALIDATION,
]
_LR_TABS_WITH_FIRST = [
    TAB_GRAMMAR,
    TAB_FIRST_FOLLOW,
    TAB_LR_ITEMS,
    TAB_CLOSURE,
    TAB_STATES,
    TAB_TABLE,
    TAB_SIMULATION,
    TAB_PARSE_TREE,
    TAB_CODE,
    TAB_CONFLICTS,
    TAB_DFA,
    TAB_VALIDATION,
]
# Top-down (LL / recursive descent) tabs.
_TOPDOWN_TABS = [
    TAB_GRAMMAR,
    TAB_FIRST_FOLLOW,
    TAB_TOPDOWN,
    TAB_PARSE_TREE,
    TAB_AST,
    TAB_ANALYZER,
    TAB_CODE,
]
# LL(1)/predictive parsers additionally expose the LL(1) table.
_TOPDOWN_LL1_TABS = [
    TAB_GRAMMAR,
    TAB_FIRST_FOLLOW,
    TAB_LL_TABLE,
    TAB_TOPDOWN,
    TAB_PARSE_TREE,
    TAB_AST,
    TAB_ANALYZER,
    TAB_CODE,
]

# Ordered tabs shown for each selectable parser type.
PARSER_TABS: dict[str, list[str]] = {
    "Shift Reduce": _LR_TABS,
    "LR(0)": _LR_TABS,
    "SLR(1)": _LR_TABS_WITH_FIRST,
    "CLR(1)": _LR_TABS_WITH_FIRST,
    "LALR(1)": _LR_TABS_WITH_FIRST,
    "Recursive Descent": _TOPDOWN_TABS,
    "Backtracking Recursive Descent": _TOPDOWN_TABS,
    "Predictive (LL(1))": _TOPDOWN_LL1_TABS,
    "LL(1)": _TOPDOWN_LL1_TABS,
}


class _GUILogHandler(logging.Handler):
    """A logging handler that appends records to a GUI text widget."""

    def __init__(self, callback) -> None:
        super().__init__()
        self._callback = callback
        self.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._callback(self.format(record))
        except Exception:  # pragma: no cover - logging must never crash the UI
            pass


class MainWindow(QMainWindow):
    """Main window for the Bottom-Up Parser Simulator."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1280, 840)

        self._analysis = None
        self._status_bar: Optional[QStatusBar] = None
        self._logs_view: Optional[QTextEdit] = None
        self._logs_dock: Optional[QDockWidget] = None

        self._build_central_tabs()
        self._setup_menu_bar()
        self._setup_toolbar()
        self._setup_status_bar()
        self._setup_logs_dock()

        logger.info("Main window initialized")

    # ------------------------------------------------------------------
    # Central workspace
    # ------------------------------------------------------------------
    def _build_central_tabs(self) -> None:
        self.grammar_editor = GrammarEditor()
        self.first_follow_view = FirstFollowView()
        self.lr_items_view = LRItemsTransitionsView()
        self.closure_view = ClosureGotoStepsView()
        self.lr_states_view = LRStatesView()
        self.validation_view = ValidationView()
        self.dfa_view = DFAView()
        self.combined_view = CombinedTableView()
        self.conflict_view = ConflictView()
        self.simulation_view = SimulationView()
        self.parse_tree_view = ParseTreeView()
        self.code_view = CodeView()
        self.topdown_view = TopDownView()
        self.ll1_table_view = LL1TableView()
        self.ast_view = AstView()
        self.analyzer_view = GrammarAnalyzerView()
        self.comparison_view = ParserComparisonView()

        self._tab_titles = {
            TAB_GRAMMAR: "Grammar",
            TAB_FIRST_FOLLOW: "FIRS/FOLLOW",
            TAB_LR_ITEMS: "LR Items/Transitions",
            TAB_CLOSURE: "Closure/GOTO Steps",
            TAB_STATES: "Canonical Collection",
            TAB_VALIDATION: "State Validation",
            TAB_DFA: "DFA",
            TAB_TABLE: "ACTION/GOTO Table",
            TAB_CONFLICTS: "Conflict Report",
            TAB_SIMULATION: "Simulation",
            TAB_TOPDOWN: "Top-Down",
            TAB_LL_TABLE: "LL(1) Table",
            TAB_PARSE_TREE: "Parse Tree",
            TAB_AST: "AST",
            TAB_ANALYZER: "Grammar Analyzer",
            TAB_COMPARISON: "Grammar Compatibility",
            TAB_CODE: "Generated Parser",
        }
        self._tab_widgets = {
            TAB_GRAMMAR: self.grammar_editor,
            TAB_FIRST_FOLLOW: self.first_follow_view,
            TAB_LR_ITEMS: self.lr_items_view,
            TAB_CLOSURE: self.closure_view,
            TAB_STATES: self.lr_states_view,
            TAB_VALIDATION: self.validation_view,
            TAB_DFA: self.dfa_view,
            TAB_TABLE: self.combined_view,
            TAB_CONFLICTS: self.conflict_view,
            TAB_SIMULATION: self.simulation_view,
            TAB_TOPDOWN: self.topdown_view,
            TAB_LL_TABLE: self.ll1_table_view,
            TAB_PARSE_TREE: self.parse_tree_view,
            TAB_AST: self.ast_view,
            TAB_ANALYZER: self.analyzer_view,
            TAB_COMPARISON: self.comparison_view,
            TAB_CODE: self.code_view,
        }

        self._central_tabs = QTabWidget()
        self.setCentralWidget(self._central_tabs)

        # Cross-widget wiring.
        self.grammar_editor.generate_requested.connect(self._on_generate)
        self.simulation_view.parse_tree_ready.connect(self.parse_tree_view.show_tree)
        self.simulation_view.parse_tree_ready.connect(self._on_parse_tree_ready)
        self.simulation_view.simulation_finished.connect(self._on_simulation_finished)
        self.topdown_view.parse_tree_ready.connect(self.parse_tree_view.show_tree)
        self.topdown_view.ast_ready.connect(self.ast_view.set_ast)
        self.topdown_view.parse_finished.connect(self._on_topdown_finished)

        # Rebuild the visible tabs whenever the parser type changes, and apply
        # the initial (default) parser's tab set.
        self.grammar_editor.parser_combo.currentTextChanged.connect(
            self._on_parser_selected
        )
        self._apply_parser_tabs(self.grammar_editor.selected_parser_type())

    # ------------------------------------------------------------------
    # Parser-specific tabs
    # ------------------------------------------------------------------
    def _apply_parser_tabs(self, parser_type: str) -> None:
        """Show only the tabs relevant to ``parser_type``.

        The tab widgets are kept alive as attributes; this method detaches them
        from the tab bar and re-adds only the relevant ones in the order defined
        by :data:`PARSER_TABS`, so no widget state is lost when switching.

        Args:
            parser_type: The selected parser type (e.g. ``"SLR(1)"``).
        """
        keys = PARSER_TABS.get(parser_type, _LR_TABS_WITH_FIRST)
        tabs = self._central_tabs

        # Detach every page without destroying the widgets.
        while tabs.count():
            tabs.removeTab(0)

        for key in keys:
            widget = self._tab_widgets.get(key)
            if widget is None:
                continue
            tabs.addTab(widget, self._tab_titles[key])

        if tabs.count():
            tabs.setCurrentIndex(0)

        logger.debug("Applied %d tabs for parser %s", tabs.count(), parser_type)

    def _on_parser_selected(self, parser_type: str) -> None:
        """Slot for parser-type changes: rebuild the visible tabs."""
        self._apply_parser_tabs(parser_type)
        if self._status_bar is not None:
            self._status_bar.showMessage(f"Parser: {parser_type}", 3000)

    # ------------------------------------------------------------------
    # Menu bar
    # ------------------------------------------------------------------
    def _setup_menu_bar(self) -> None:
        menu_bar = self.menuBar()

        file_menu = menu_bar.addMenu("&File")

        new_action = QAction("&New Grammar", self)
        new_action.setShortcut(QKeySequence.StandardKey.New)
        new_action.triggered.connect(self._on_new_grammar)
        file_menu.addAction(new_action)

        open_action = QAction("&Open Grammar...", self)
        open_action.setShortcut(QKeySequence.StandardKey.Open)
        open_action.triggered.connect(self._on_open_grammar)
        file_menu.addAction(open_action)

        save_action = QAction("&Save Grammar...", self)
        save_action.setShortcut(QKeySequence.StandardKey.Save)
        save_action.triggered.connect(self._on_save_grammar)
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        export_menu = file_menu.addMenu("&Export")

        csv_action = QAction("Tables as &CSV...", self)
        csv_action.triggered.connect(self._on_export_csv)
        export_menu.addAction(csv_action)

        md_action = QAction("Report as &Markdown...", self)
        md_action.triggered.connect(self._on_export_markdown)
        export_menu.addAction(md_action)

        html_action = QAction("Report as &HTML...", self)
        html_action.triggered.connect(self._on_export_html)
        export_menu.addAction(html_action)

        dot_action = QAction("DFA as &DOT...", self)
        dot_action.triggered.connect(self._on_export_dot)
        export_menu.addAction(dot_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.StandardKey.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menu_bar.addMenu("&Edit")

        clear_action = QAction("&Clear Grammar", self)
        clear_action.triggered.connect(self._on_clear_grammar)
        edit_menu.addAction(clear_action)

        view_menu = menu_bar.addMenu("&View")
        show_logs = QAction("Show &Logs", self)
        show_logs.setCheckable(True)
        show_logs.setChecked(True)
        show_logs.triggered.connect(self._toggle_logs)
        view_menu.addAction(show_logs)

        tools_menu = menu_bar.addMenu("&Tools")

        generate_action = QAction("&Generate Parsing Table", self)
        generate_action.setShortcut("Ctrl+G")
        generate_action.triggered.connect(self._on_generate_menu)
        tools_menu.addAction(generate_action)

        simulate_action = QAction("&Run Simulation", self)
        simulate_action.setShortcut("Ctrl+R")
        simulate_action.triggered.connect(self._on_run_simulation)
        tools_menu.addAction(simulate_action)

        help_menu = menu_bar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # ------------------------------------------------------------------
    # Toolbar
    # ------------------------------------------------------------------
    def _setup_toolbar(self) -> None:
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        self.addToolBar(toolbar)

        for label, tooltip, slot in [
            ("New", "New grammar", self._on_new_grammar),
            ("Open", "Open grammar from library", self._on_open_grammar),
            ("Save", "Save grammar to library", self._on_save_grammar),
        ]:
            action = QAction(QIcon(), label, self)
            action.setToolTip(tooltip)
            action.triggered.connect(slot)
            toolbar.addAction(action)

        toolbar.addSeparator()

        for label, tooltip, slot in [
            ("Generate", "Generate ACTION/GOTO parsing table", self._on_generate_menu),
            ("Simulate", "Run parsing simulation", self._on_run_simulation),
        ]:
            action = QAction(QIcon(), label, self)
            action.setToolTip(tooltip)
            action.triggered.connect(slot)
            toolbar.addAction(action)

    # ------------------------------------------------------------------
    # Status bar & logs dock
    # ------------------------------------------------------------------
    def _setup_status_bar(self) -> None:
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

    def _setup_logs_dock(self) -> None:
        self._logs_view = QTextEdit()
        self._logs_view.setReadOnly(True)
        self._logs_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self._logs_dock = QDockWidget("Logs", self)
        self._logs_dock.setWidget(self._logs_view)
        self._logs_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._logs_dock)

        # Route application logs into the dock.
        handler = _GUILogHandler(self._append_log)
        handler.setLevel(logging.INFO)
        logging.getLogger().addHandler(handler)

    def _append_log(self, line: str) -> None:
        if self._logs_view is not None:
            self._logs_view.append(line)

    def _toggle_logs(self) -> None:
        if self._logs_dock is not None:
            self._logs_dock.setVisible(not self._logs_dock.isVisible())

    # ------------------------------------------------------------------
    # Analysis / simulation handlers
    # ------------------------------------------------------------------
    def _on_generate(self, text: str, options: GenerateOptions) -> None:
        # Describe the input grammar so the user knows what the toggles can do.
        try:
            features = grammar_features(text)
            note = "Grammar: " + features["note"] + "."
            self.grammar_editor.set_feature_note(note)
        except Exception:  # pragma: no cover - feature note is best-effort
            self.grammar_editor.set_feature_note("")

        # Grammar analysis and parser comparison are always available.
        self._update_analyzer(text)
        self._update_comparison(text)

        if options.parser_type in TOPDOWN_METHODS:
            self._generate_topdown(text, options)
        else:
            self._generate_bottomup(text, options)

    def _update_analyzer(self, text: str) -> None:
        try:
            report = analyze_grammar(parse_grammar(text))
            self.analyzer_view.set_report(report)
        except Exception:  # pragma: no cover - analysis is best-effort
            self.analyzer_view.clear()

    def _update_comparison(self, text: str) -> None:
        try:
            self.comparison_view.set_report(compare_parsers(text))
        except Exception:  # pragma: no cover - comparison is best-effort
            self.comparison_view.clear()

    def _generate_topdown(self, text: str, options: GenerateOptions) -> None:
        try:
            result = analyze_topdown(
                text,
                options.parser_type,
                remove_left_recursion=options.remove_left_recursion,
                left_factoring=options.left_factoring,
                remove_epsilon=options.remove_epsilon,
                remove_unit=options.remove_unit,
                remove_useless=options.remove_useless,
            )
        except GrammarParseError as exc:
            self.grammar_editor.set_status(str(exc), is_error=True)
            self._status_bar.showMessage("Grammar error", 5000)
            QMessageBox.critical(self, "Grammar Error", str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Top-down analysis failed")
            self.grammar_editor.set_status(f"Error: {exc}", is_error=True)
            QMessageBox.critical(self, "Error", f"Analysis failed:\n{exc}")
            return

        self._analysis = None
        self.topdown_view.set_analysis(result)
        self.ll1_table_view.set_analysis(result)
        self.first_follow_view.update_from(result)
        self.grammar_editor.set_grammar_variants(result.stages)

        # Clear bottom-up-only views.
        self.lr_items_view.clear()
        self.closure_view.clear()
        self.lr_states_view.clear()
        self.validation_view.clear()
        self.dfa_view.clear()
        self.combined_view.clear()
        self.conflict_view.clear()
        self.simulation_view.clear()
        self.parse_tree_view.clear()
        self.ast_view.clear()
        self.code_view.clear()

        notes = []
        if result.left_recursion:
            notes.append(
                "left recursion remains — enable 'Remove Left Recursion'"
            )
        if result.left_factoring:
            notes.append(
                "common prefixes — enable 'Left Factoring' for LL(1)"
            )
        if result.conflicts:
            notes.append(f"{len(result.conflicts)} LL(1) conflict(s)")
        suffix = (" — " + "; ".join(notes)) if notes else " — LL(1) clean"
        transform_note = (
            f" [transforms: {', '.join(result.transforms)}]"
            if result.transforms
            else ""
        )
        message = (
            f"{options.parser_type} ready{suffix}{transform_note}. "
            "Enter input in the Top-Down tab."
        )
        self.grammar_editor.set_status(
            message, is_error=bool(result.left_recursion or result.conflicts)
        )
        self._status_bar.showMessage(message, 6000)

    def _generate_bottomup(self, text: str, options: GenerateOptions) -> None:
        try:
            analysis = analyze(
                text,
                options.parser_type,
                remove_left_recursion=options.remove_left_recursion,
                left_factoring=options.left_factoring,
                remove_epsilon=options.remove_epsilon,
                remove_unit=options.remove_unit,
                remove_useless=options.remove_useless,
                resolution=options.resolution,
            )
        except GrammarParseError as exc:
            self.grammar_editor.set_status(str(exc), is_error=True)
            self._status_bar.showMessage("Grammar error", 5000)
            QMessageBox.critical(self, "Grammar Error", str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Analysis failed")
            self.grammar_editor.set_status(f"Error: {exc}", is_error=True)
            QMessageBox.critical(self, "Error", f"Analysis failed:\n{exc}")
            return

        self._analysis = analysis
        self.first_follow_view.update_from(analysis)
        self.lr_items_view.update_from(analysis)
        self.closure_view.update_from(analysis)
        self.lr_states_view.update_from(analysis)
        self.validation_view.update_from(analysis)
        self.dfa_view.update_from(analysis)
        self.combined_view.update_from(analysis, show_errors=options.show_error_cells)
        self.conflict_view.update_from(analysis)
        self.simulation_view.set_analysis(analysis)
        self.topdown_view.clear()
        self.ll1_table_view.clear()
        self.ast_view.clear()
        self.parse_tree_view.clear()

        # Show the grammar that was actually analysed (post-transform).
        self.grammar_editor.set_grammar_variants(analysis.stages)

        # Generate a runnable parser only when every conflict was explicitly
        # resolved. A grammar whose conflicts are not mathematically resolved
        # must not produce a parser that silently picks an arbitrary action.
        unresolved = analysis.unresolved_conflicts
        sample = self.simulation_view.input_edit.text().split() or None
        if unresolved:
            self.code_view.set_code(
                "# Parser generation blocked: unresolved conflicts.\n"
                "#\n"
                + "\n".join(
                    f"# - state {c.state} on '{c.terminal}': {c.conflict_type}"
                    for c in unresolved
                )
                + "\n#\n"
                "# Resolve the conflicts explicitly, or rebuild the table with a "
                "more powerful\nalgorithm (SLR(1), CLR(1) or LALR(1)) that can "
                "mathematically decide the cell.",
                note=(
                    f"Parser not generated — {len(unresolved)} unresolved "
                    "conflict(s). See the Conflicts tab."
                ),
            )
        else:
            try:
                code = generate_lr_parser(analysis, sample_input=sample)
                self.code_view.set_code(
                    code,
                    note=f"Generated {analysis.parser_type} parser "
                    f"({analysis.table.num_states} states). Save or copy it.",
                )
            except Exception:  # pragma: no cover - codegen is best-effort
                logger.exception("Code generation failed")
                self.code_view.clear()

        transform_note = (
            f" [transforms: {', '.join(analysis.transforms)}]"
            if analysis.transforms
            else ""
        )
        message = (
            f"{options.parser_type} generated: {len(analysis.automaton.states)} states, "
            f"{len(analysis.conflicts)} conflict(s)"
            f"{self._conflict_summary(analysis)}{transform_note}"
        )
        self.grammar_editor.set_status(
            message, is_error=bool(analysis.unresolved_conflicts)
        )
        self._status_bar.showMessage(message, 6000)

    def _on_parse_tree_ready(self, tree) -> None:
        """Compute and show an AST whenever a bottom-up parse succeeds."""
        from core.ast import parse_tree_to_ast

        self.ast_view.set_ast(parse_tree_to_ast(tree))

    def _on_topdown_finished(self, accepted: bool, message: str) -> None:
        self._status_bar.showMessage(message, 8000)
        if not accepted:
            self.parse_tree_view.show_message(message)

    @staticmethod
    def _conflict_summary(analysis) -> str:
        """Return a short note about conflict resolution for the status line."""
        if not analysis.conflicts:
            return ""
        if analysis.resolution_config.enabled:
            return (
                f" ({len(analysis.resolutions)} resolved, "
                f"{len(analysis.unresolved_conflicts)} unresolved)"
            )
        return " (unresolved)"

    def _on_generate_menu(self) -> None:
        self._on_generate(
            self.grammar_editor.grammar_text(),
            self.grammar_editor.current_options(),
        )

    def _on_run_simulation(self) -> None:
        if self._analysis is None:
            self._on_generate(
                self.grammar_editor.grammar_text(),
                self.grammar_editor.current_options(),
            )
            if self._analysis is None:
                return
        self._central_tabs.setCurrentWidget(self.simulation_view)
        self.simulation_view.run()

    def _on_simulation_finished(self, accepted: bool, message: str) -> None:
        self._status_bar.showMessage(message, 8000)
        if not accepted:
            self.parse_tree_view.show_message(message)
        self._record_history(accepted)

    def _record_history(self, accepted: bool) -> None:
        if self._analysis is None:
            return
        try:
            db = get_database()
            result = self.simulation_view._result
            steps = len(result.steps) if result is not None else 0
            db.execute(
                "INSERT INTO parsing_history "
                "(grammar_name, parser_type, input_string, accepted, steps_count) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    self._analysis.grammar.start_symbol,
                    self._analysis.parser_type,
                    self.simulation_view.input_edit.text(),
                    1 if accepted else 0,
                    steps,
                ),
            )
        except Exception:  # pragma: no cover - history is best-effort
            logger.exception("Failed to record parsing history")

    # ------------------------------------------------------------------
    # File handlers
    # ------------------------------------------------------------------
    def _on_new_grammar(self) -> None:
        self.grammar_editor.set_grammar_text("")
        self._analysis = None
        self._reset_views()
        self.grammar_editor.set_status("New grammar")
        self._status_bar.showMessage("New grammar", 3000)

    def _on_clear_grammar(self) -> None:
        self.grammar_editor.set_grammar_text("")
        self._analysis = None
        self._reset_views()
        self.grammar_editor.set_status("Grammar cleared")
        self._status_bar.showMessage("Grammar cleared", 3000)

    def _reset_views(self) -> None:
        self.first_follow_view.clear()
        self.lr_items_view.clear()
        self.closure_view.clear()
        self.lr_states_view.clear()
        self.validation_view.clear()
        self.dfa_view.clear()
        self.combined_view.clear()
        self.conflict_view.clear()
        self.simulation_view.clear()
        self.topdown_view.clear()
        self.ll1_table_view.clear()
        self.parse_tree_view.clear()
        self.ast_view.clear()
        self.analyzer_view.clear()
        self.comparison_view.clear()
        self.code_view.clear()

    def _on_open_grammar(self) -> None:
        try:
            db = get_database()
            rows = db.fetch_all(
                "SELECT id, name, grammar_text, updated_at FROM saved_grammars "
                "ORDER BY updated_at DESC"
            )
        except Exception:
            logger.exception("Failed to load saved grammars")
            rows = []

        if not rows:
            QMessageBox.information(
                self, "Open Grammar", "No saved grammars yet. Use Save to store one."
            )
            return

        names = [f"{row['name']}  ({row['updated_at']})" for row in rows]
        choice, ok = QInputDialog.getItem(
            self, "Open Grammar", "Select a grammar:", names, 0, False
        )
        if not ok:
            return
        index = names.index(choice)
        row = rows[index]
        self.grammar_editor.set_grammar_text(row["grammar_text"])
        self.grammar_editor.set_status(f"Loaded '{row['name']}'")
        self._central_tabs.setCurrentWidget(self.grammar_editor)
        self._status_bar.showMessage(f"Loaded '{row['name']}'", 4000)

    def _on_save_grammar(self) -> None:
        text = self.grammar_editor.grammar_text()
        if not text.strip():
            QMessageBox.information(self, "Save Grammar", "The grammar is empty.")
            return
        name, ok = QInputDialog.getText(
            self, "Save Grammar", "Grammar name:", text="My Grammar"
        )
        if not ok or not name.strip():
            return
        try:
            db = get_database()
            existing = db.fetch_one(
                "SELECT id FROM saved_grammars WHERE name = ?", (name.strip(),)
            )
            if existing is not None:
                db.execute(
                    "UPDATE saved_grammars SET grammar_text = ?, updated_at = CURRENT_TIMESTAMP "
                    "WHERE id = ?",
                    (text, existing["id"]),
                )
            else:
                db.execute(
                    "INSERT INTO saved_grammars (name, grammar_text) VALUES (?, ?)",
                    (name.strip(), text),
                )
            self.grammar_editor.set_status(f"Saved as '{name.strip()}'")
            self._status_bar.showMessage(f"Saved as '{name.strip()}'", 4000)
        except Exception:
            logger.exception("Failed to save grammar")
            QMessageBox.critical(self, "Save Grammar", "Failed to save the grammar.")

    # ------------------------------------------------------------------
    # Export handlers
    # ------------------------------------------------------------------
    def _export(self, generator, default_name: str, file_filter: str) -> None:
        if self._analysis is None:
            QMessageBox.information(
                self, "Export", "Generate a grammar before exporting."
            )
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export", default_name, file_filter
        )
        if not path:
            return
        try:
            content = generator(self._analysis)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(content)
            self._status_bar.showMessage(f"Exported to {path}", 6000)
        except OSError as exc:  # pragma: no cover - filesystem dependent
            logger.error("Export failed: %s", exc)
            QMessageBox.critical(self, "Export", f"Failed to export: {exc}")

    def _on_export_csv(self) -> None:
        self._export(table_to_csv, "tables.csv", "CSV Files (*.csv)")

    def _on_export_markdown(self) -> None:
        self._export(analysis_to_markdown, "analysis.md", "Markdown Files (*.md)")

    def _on_export_html(self) -> None:
        self._export(analysis_to_html, "analysis.html", "HTML Files (*.html)")

    def _on_export_dot(self) -> None:
        self._export(automaton_to_dot, "automaton.dot", "DOT Files (*.dot)")

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------
    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "About",
            f"{APP_NAME} v{APP_VERSION}\n{APP_ORGANIZATION}\n\n"
            "A desktop application for visualizing parsing techniques:\n"
            "Top-down: Recursive Descent, Backtracking Recursive Descent, "
            "Predictive/LL(1).\n"
            "Bottom-up: LR(0), SLR(1), CLR(1), and LALR(1).\n\n"
            "Includes grammar analysis, AST generation, parser comparison, "
            "error recovery, and export.",
        )

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------
    def closeEvent(self, event) -> None:  # noqa: N802 (Qt naming)
        try:
            get_database().close()
        except Exception:  # pragma: no cover
            pass
        super().closeEvent(event)