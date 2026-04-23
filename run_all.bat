@echo off
echo Running SAT Solver Benchmarks...

echo ==============================
echo Baseline Solver
echo ==============================
for %%f in (benchmarks\sat\uf50*.cnf) do (
    python3 DPLL_baseline.py %%f
)
for %%f in (benchmarks\unsat\uuf50*.cnf) do (
    python3 DPLL_baseline.py %%f
)

echo ==============================
echo Heuristic Solver (DLIS + Watched)
echo ==============================
for %%f in (benchmarks\sat\uf50*.cnf) do (
    echo Running %%f
    python3 DPLL_heuristic.py %%f --heuristic dlis --propagation watched
)

for %%f in (benchmarks\unsat\uuf50*.cnf) do (
    echo Running %%f
    python3 DPLL_heuristic.py %%f --heuristic dlis --propagation watched
)

echo Done.
pause