# ECE51216 SAT Solver Project

This repository contains a Python implementation of a DPLL-based SAT solver for the ECE51216 course project.

## Current Files

- `DPLL_baseline.py`
  - plain recursive DPLL
  - DIMACS parser
  - naive unit propagation
- `DPLL_heuristic.py`
  - standalone DPLL solver used for experiments
  - baseline branching or DLIS branching
  - naive propagation or watched-literal propagation
- `benchmarks/`
  - small SAT and UNSAT DIMACS inputs kept in the repo for quick testing

## Implemented Variants

The current comparison setup uses these three solver variants:

1. `Baseline DPLL`
2. `DPLL + Watched Literals`
3. `DPLL + Watched Literals + DLIS`

Inside `DPLL_heuristic.py`, the two configurable parts are:

- `--heuristic baseline|dlis`
- `--propagation naive|watched`

`watched literals` is not a decision heuristic. It replaces the propagation method, while `DLIS` changes how the next branch literal is selected.

## Example Commands

Run the baseline solver:

```bash
python3 DPLL_baseline.py benchmarks/sat/example-1.cnf
```

Run the three comparison modes:

```bash
python3 DPLL_heuristic.py benchmarks/sat/example-1.cnf --heuristic baseline --propagation naive --print-stats
python3 DPLL_heuristic.py benchmarks/sat/example-1.cnf --heuristic baseline --propagation watched --print-stats
python3 DPLL_heuristic.py benchmarks/sat/example-1.cnf --heuristic dlis --propagation watched --print-stats
```

Run an UNSAT check:

```bash
python3 DPLL_heuristic.py benchmarks/unsat/unsat.cnf --heuristic baseline --propagation watched --print-stats
```

## Output Format

The solver prints:

- `RESULT:SAT` or `RESULT:UNSAT`
- `ASSIGNMENT:...` when a satisfying assignment is found
- `STATS:...` when `--print-stats` is enabled

The stats line reports decisions, propagations, conflicts, backtracks, recursive calls, search depth, and runtime.

## Notes

- `DPLL_baseline.py` is kept separate so the original baseline stays untouched.
- `DPLL_heuristic.py` does not depend on `DPLL_baseline.py`; it can be run on its own.
- The current code is aimed at clean comparison of algorithmic ideas rather than aggressive SAT-solver engineering.
