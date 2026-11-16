# Compiler Construction Bottom-Up Parser Simulator

A desktop application for visualizing bottom-up parsing techniques used in compiler construction.

## Features

- Grammar input in BNF format
- Grammar validation with meaningful error messages
- Left-recursion removal (immediate and indirect)
- Left factoring (common-prefix extraction)
- Grammar normalization: useless-symbol removal, ε-production removal,
  unit-production removal
- FIRST and FOLLOW set computation
- LR(0), SLR(1), CLR(1), and LALR(1) parser generation
- ACTION and GOTO table generation
- Conflict detection (shift-reduce, reduce-reduce)
- Conflict resolution: prefer shift, prefer reduce, precedence/associativity
  (`%left`/`%right`/`%nonassoc`), and reduce/reduce by first rule or precedence
- Standalone parser code generation (`generate_lr_parser`)
- Step-by-step parsing simulation
- Parse tree generation and visualization
- DFA visualization with zoom, pan, and state selection
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
3. Optionally tick **Remove Left Recursion**, **Left Factoring**,
   **Remove Useless Symbols**, **Remove ε-Productions**, and/or
   **Remove Unit Productions** to normalise the grammar before analysis. The
   **Grammar used** preview shows the transformed grammar that will actually be
   analysed, and the feature note reports whether the input grammar contains
   left recursion or common prefixes.
4. View FIRST/FOLLOW sets, LR states, and DFA in their respective panels.
5. Generate ACTION/GOTO tables for your chosen parser type.
6. If the grammar has conflicts, open the **Conflicts** tab to inspect them.
   Tick **Resolve Conflicts** and pick a strategy (Prefer Shift, Prefer Reduce,
   or Use Precedence for shift/reduce; First Rule or Use Precedence for
   reduce/reduce) before generating. Precedence-based resolution uses yacc-style
   declarations in the grammar, e.g. `%left '+'` then `%left '*'`.
7. Run a step-by-step parsing simulation on an input string. Spacing is
   optional: `id+id` and `id + id` both work because tokens are split at
   grammar-terminal boundaries.
8. View the generated parse tree.
9. Open the **Generated Parser** tab to see a standalone Python LR parser for
   the analysed grammar (class `LRParser` with `parse(tokens)` and `trace`), and
   use **File > Export** to save the table as CSV, or the report/automaton as
   Markdown, HTML, or Graphviz DOT.

## Example Grammar

```
E -> E + T | T
T -> T * F | F
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
