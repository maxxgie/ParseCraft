"""Startup dashboard for Computer Science Laboratory."""
_DASHBOARD = None


def show_dashboard():
    global _DASHBOARD
    if _DASHBOARD is None:
        _DASHBOARD = Dashboard()
    _DASHBOARD.show()
    _DASHBOARD.raise_()
    return _DASHBOARD


from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout
from gui.main_window import MainWindow


class Dashboard(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Computer Science Laboratory")
        self.resize(800, 600)
        layout = QVBoxLayout(self)
        title = QLabel("Computer Science Laboratory")
        title.setStyleSheet("font-size: 28px; font-weight: bold;")
        subtitle = QLabel("Interactive Learning and Simulation Platform")
        subtitle.setStyleSheet("font-size: 14px; color: gray;")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(20)

        # Compiler card
        c = QWidget()
        cl = QVBoxLayout(c)
        cl.addWidget(QLabel("Compiler Construction"))
        cl.addWidget(QLabel("Grammar Analysis\nParser Simulation\nFIRST/FOLLOW\nLR Parsing"))
        b = QPushButton("Open Module")
        b.clicked.connect(self.open_compiler)
        cl.addWidget(b)
        layout.addWidget(c)

        # Theory card
        t = QWidget()
        tl = QVBoxLayout(t)
        tl.addWidget(QLabel("Theory of Computation"))
        tl.addWidget(QLabel("Finite Automata\nRegular Expressions\nPushdown Automata\nTuring Machines"))
        b2 = QPushButton("Coming Soon")
        b2.clicked.connect(self.open_theory)
        tl.addWidget(b2)
        layout.addWidget(t)

        # Home buttons
        row = QHBoxLayout()
        settings = QPushButton("Settings")
        about = QPushButton("About")
        exitb = QPushButton("Exit")
        exitb.clicked.connect(self.close)
        row.addWidget(settings)
        row.addWidget(about)
        row.addWidget(exitb)
        layout.addLayout(row)

    def open_compiler(self):
        global _DASHBOARD
        _DASHBOARD = self
        self._win = MainWindow()
        self._win.show()
        self.hide()

    def open_theory(self):
        from modules.theory_of_computation.workspace import TheoryWorkspace
        self._tw = TheoryWorkspace()
        self._tw.show()
        self.hide()
