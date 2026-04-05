# Python SAT Project

This folder contains a fresh baseline implementation for the ECE51216 SAT solver project.

Current scope:

- DIMACS CNF parser
- Recursive DPLL solver
- Unit propagation / Boolean Constraint Propagation (BCP)
- Basic solver statistics for report writing

Example:

```bash
python3 sat_solver.py ../DPLL-SAT-Solver-master/example-1.cnf --print-model
python3 sat_solver.py ../SAT_solver/uf20-04.cnf
```

Planned next steps:

- Add watched literals
- Add VSIDS decision heuristic
- Compare baseline DPLL vs watched literals vs watched literals + VSIDS
