# Compiler Construction Parser Simulator

A desktop application for visualizing top-down and bottom-up parsing techniques used in compiler construction.

## Features

- Grammar input in BNF format (multiple productions, ε-productions, `#` comments)
- Grammar validation with precise, line-numbered errors: empty grammar,
  invalid operator, missing left/right side, duplicate productions (warning),
  undefined non-terminals, unreachable and unproductive symbols
- Left-recursion removal (immediate and indirect)
- Left factoring (common-prefix extraction)
- Grammar normalization: useless-symbol removal, ε-production removal,
  unit-production removal
- FIRST and FOLLOW set computation

### Top-down parsers

- Recursive Descent (function-per-nonterminal, with call trace and derivation)
- Backtracking Recursive Descent (shows failed attempts and decision points)
- Predictive (LL(1)) and LL(1) parsing (LL(1) table, conflict highlighting,
  stack-based simulation)
- Left-recursion and left-factoring detection for top-down compatibility

### Bottom-up parsers

- LR(0), SLR(1), CLR(1), and LALR(1) parser generation
- ACTION and GOTO table generation
- Conflict detection (shift-reduce, reduce-reduce)
- Conflict resolution: prefer shift, prefer reduce, precedence/associativity
  (`%left`/`%right`/`%nonassoc`), and reduce/reduce by first rule or precedence

### Analysis and tooling

- Grammar Analyzer: undefined symbols, duplicate productions, unreachable and
  non-productive non-terminals, unit cycles, left recursion, left factoring,
  and LL(1) ambiguity warnings
- Abstract Syntax Tree (AST) generation from any parse tree
- Parser Comparison: LL(1) vs LR(0)/SLR(1)/CLR(1)/LALR(1) (states, table size,
  conflicts, compatibility)
- Error recovery simulation: panic-mode and phrase-level (error location,
  expected tokens, recovery actions)
- Standalone parser code generation (`generate_lr_parser`)
- Step-by-step parsing simulation
- Parse tree generation and visualization (zoom/pan, collapse single-child
  nodes, export as PNG)
- DFA visualization with zoom, pan, and state selection
- Deterministic output: identical tables and automata across runs
- Export to CSV, Markdown, HTML, and Graphviz DOT
- SQLite persistent storage for grammars, history, and settings
- Application logging

## Technology Stack

- Python 3.13+
- PyQt6 for GUI
- SQLite for persistent storage
- pytest for testing
- logging module for application logs

## Installation

### Prerequisites

Python 3.13 or higher is required.

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run the Application

```bash
python main.py
```

### Build Windows Executable

```bash
pyinstaller --onefile main.py
```

## Project Structure

```
bottom_up_parser_simulator/
├── main.py
├── requirements.txt
├── README.md
├── core/
│   ├── __init__.py
│   ├── database.py
│   ├── logging_config.py
│   └── ...
├── gui/
│   ├── __init__.py
│   ├── main_window.py
│   ├── settings.py
│   └── ...
├── models/
├── tests/
└── logs/
```

## Usage

1. Launch the application with `python main.py`.
2. Enter a grammar in the Grammar panel using BNF format.
3. Choose a **parser** from the drop-down: the bottom-up methods
   (`LR(0)`, `SLR(1)`, `CLR(1)`, `LALR(1)`) or a top-down method
   (`Recursive Descent`, `Backtracking Recursive Descent`,
   `Predictive (LL(1))`, `LL(1)`).
4. Optionally tick **Remove Left Recursion**, **Left Factoring**,
   **Remove Useless Symbols**, **Remove ε-Productions**, and/or
   **Remove Unit Productions** to normalise the grammar before analysis. These
   apply to both top-down and bottom-up methods — e.g. enable **Remove Left
   Recursion** to make a left-recursive grammar usable by a top-down parser.
   The **Grammar used** preview shows the transformed grammar, and the feature
   note reports whether the input grammar contains left recursion or common
   prefixes.
5. View FIRST/FOLLOW sets, LR states, and DFA in their respective panels
   (bottom-up). The **Grammar Analyzer** tab always shows validation and
   ambiguity findings, and the **Parser Comparison** tab compares LL(1) with the
   LR family.
6. For bottom-up methods, generate ACTION/GOTO tables and inspect the
   **Conflicts** tab. Tick **Resolve Conflicts** and pick a strategy (Prefer
   Shift, Prefer Reduce, or Use Precedence for shift/reduce; First Rule or Use
   Precedence for reduce/reduce). Precedence-based resolution uses yacc-style
   declarations, e.g. `%left '+'` then `%left '*'`.
7. Run a simulation:
   - **Top-down**: open the **Top-Down** tab, enter an input string, and press
     **Run**/**Step** to trace calls, matches, backtracks, and (for LL(1))
     predictions.
   - **Bottom-up**: use the **Simulation** tab. Choose an **Error recovery**
     mode (Panic-mode or Phrase-level) to see how the parser recovers from
     syntax errors (error location, expected tokens, recovery actions).
   Spacing is optional: `id+id` and `id + id` both work.
8. View the parse tree (**Parse Tree** tab) and its abstract syntax tree
   (**AST** tab).
9. For bottom-up methods, open the **Generated Parser** tab for a standalone
   Python LR parser, and use **File > Export** to save the table as CSV or the
   report/automaton as Markdown, HTML, or Graphviz DOT.

## Example Grammars

Bottom-up (left-recursive, not usable by top-down parsers):

```
E -> E + T | T
T -> T * F | F
F -> ( E ) | id
```

Top-down (left-factored, LL(1)):

```
E -> T E'
E' -> + T E' | ε
T -> F T'
T' -> * F T' | ε
F -> ( E ) | id
```

## Testing

Run the test suite with:

```bash
pytest
```

## Logging

Application logs are written to `logs/application.log`.

## License

MIT
