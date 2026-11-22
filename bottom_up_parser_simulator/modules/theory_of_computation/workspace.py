"""Theory of Computation workspace (UI only)."""
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QListWidget,
                            QLabel, QStackedWidget, QPushButton)


class TheoryWorkspace(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Theory of Computation")
        self.resize(1000, 700)
        layout = QHBoxLayout(self)
        self.sidebar = QListWidget()
        pages = ["Regular Expressions","Finite Automata","DFA","NFA","NFA to DFA",
                 "DFA Minimization","Context-Free Grammars","Pushdown Automata",
                 "Turing Machines","Pumping Lemma","Closure Properties",
                 "Decidability","Complexity Classes","Recent Projects","Examples"]
        for p in pages:
            self.sidebar.addItem(p)
        self.stack = QStackedWidget()
        for p in pages:
            w = QWidget()
            v = QVBoxLayout(w)
            v.addWidget(QLabel(p))
            v.addWidget(QLabel("This module is currently under development."))
            self.stack.addWidget(w)
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)
        layout.addWidget(self.sidebar, 1)
        layout.addWidget(self.stack, 4)
        home = QPushButton("Home")
        home.clicked.connect(self.go_home)
        layout.addWidget(home)

    def go_home(self):
        from app.dashboard import show_dashboard
        show_dashboard()
        self.hide()
