# Python SAT Project

This folder contains a fresh baseline implementation for the ECE51216 SAT solver project.

Current scope:

- DIMACS CNF parser
- Recursive DPLL solver
- Unit propagation / Boolean Constraint Propagation (BCP)
- Basic solver statistics for report writing
- Local benchmark inputs stored inside the repository

Example:

```bash
python3 sat_solver.py benchmarks/sat/example-1.cnf --print-model
python3 sat_solver.py benchmarks/sat/uf20-04.cnf
python3 run_benchmarks.py
```

Planned next steps:

- Add watched literals
- Add VSIDS decision heuristic
- Compare baseline DPLL vs watched literals vs watched literals + VSIDS
