# ECE51216 SAT Solver Project

This project implements a DPLL-based SAT solver in Python and compares three solver variants:

1. `baseline`
2. `baseline + watched literals`
3. `DLIS + watched literals`

The goal is to keep a plain baseline solver and then measure how watched literals and DLIS change search behavior and runtime.

## Project Files

- `DPLL_baseline.py`
  - baseline recursive DPLL solver
  - DIMACS parser
  - naive unit propagation
  - optional stats output with `--print-stats`
- `DPLL_heuristic.py`
  - standalone experimental solver
  - `baseline` or `dlis` branching
  - `naive` or `watched` propagation
  - optional stats output with `--print-stats`
- `run_benchmarks.py`
  - runs the comparison variants on one CNF file or an entire benchmark directory
  - prints per-file results and final summary tables
- `run_all.sh`
  - Unix/macOS wrapper for `run_benchmarks.py`
- `run_all.bat`
  - Windows wrapper for `run_benchmarks.py`
- `benchmarks/`
  - SAT benchmarks: `uf50-*`
  - UNSAT benchmarks: `uuf50-*`
  - small example files for quick checks

## Implemented Variants

`DPLL_heuristic.py` exposes two independent options:

- `--heuristic baseline|dlis`
- `--propagation naive|watched`

For the project comparison, the main variants are:

1. `baseline`
   - `DPLL_baseline.py`
2. `watched`
   - `DPLL_heuristic.py --heuristic baseline --propagation watched`
3. `dlis+watched`
   - `DPLL_heuristic.py --heuristic dlis --propagation watched`

`watched literals` changes propagation.
`DLIS` changes decision selection.

## Quick Commands

Run the baseline solver on a single file:

```bash
python3 DPLL_baseline.py benchmarks/sat/example-1.cnf
```

Run the heuristic solver with stats:

```bash
python3 DPLL_heuristic.py benchmarks/sat/example-1.cnf --heuristic baseline --propagation watched --print-stats
python3 DPLL_heuristic.py benchmarks/sat/example-1.cnf --heuristic dlis --propagation watched --print-stats
```

Run an UNSAT test:

```bash
python3 DPLL_heuristic.py benchmarks/unsat/uuf50-01.cnf --heuristic dlis --propagation watched --print-stats
```

## Full Benchmark Run

Run every benchmark and print the comparison summary:

```bash
python3 run_benchmarks.py benchmarks
```

Or use the wrapper scripts:

```bash
./run_all.sh
```

On Windows:

```bat
run_all.bat
```

You can also run a single benchmark file or a smaller subset:

```bash
python3 run_benchmarks.py benchmarks/sat/uf50-01.cnf
python3 run_benchmarks.py benchmarks/unsat
```

## Output

Single-file solver runs print:

- `RESULT:SAT` or `RESULT:UNSAT`
- `ASSIGNMENT:...` for SAT instances
- `STATS:...` when `--print-stats` is enabled

The stats include:

- `decisions`
- `propagations`
- `conflicts`
- `backtracks`
- `recursive_calls`
- `max_depth`
- `runtime`

`run_benchmarks.py` prints:

- one comparison block per CNF file
- `Overall Summary`
- `SAT Summary`
- `UNSAT Summary`
- `Change vs baseline`

The summary tables report average:

- `decisions`
- `conflicts`
- `backtracks`
- `runtime`

so it is easy to check whether watched literals and DLIS improved over the baseline.

## Expected Interpretation

- `watched` often keeps decisions, conflicts, and backtracks similar to baseline, but reduces runtime by making propagation cheaper.
- `dlis+watched` can reduce runtime and also lower decisions, conflicts, and backtracks by choosing better branch literals.
- SAT assignments may differ between solvers. That is normal as long as the reported result is correct.

## Notes

- `DPLL_baseline.py` is kept separate so the original baseline remains easy to inspect.
- `DPLL_heuristic.py` is standalone and does not depend on `DPLL_baseline.py` for execution.
- `run_benchmarks.py` is the main script for project-level comparison and reporting.
