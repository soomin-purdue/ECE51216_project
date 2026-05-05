#!/usr/bin/env python3

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


Literal = int
Clause = Tuple[Literal, ...]
Formula = Tuple[Clause, ...]
Assignment = Dict[int, bool]


@dataclass
class SolverStats:
    decisions: int = 0
    propagations: int = 0
    conflicts: int = 0
    backtracks: int = 0
    recursive_calls: int = 0
    max_depth: int = 0
    elapsed_seconds: float = 0.0


@dataclass
class SolveResult:
    is_sat: bool
    assignment: Assignment
    stats: SolverStats


def parse_dimacs(path: Path) -> Tuple[int, Formula]:
    clauses: List[Clause] = []
    num_vars = 0
    current_clause: List[int] = []

    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("c"):
                continue
            if line.startswith("%"):
                break
            if line.startswith("p"):
                parts = line.split()
                if len(parts) >= 4:
                    num_vars = int(parts[2])
                    #print(f"parse: header variables={parts[2]}, clauses={parts[3]}")
                continue

            for token in line.split():
                literal = int(token)
                if literal == 0:
                    clause = tuple(current_clause)
                    if clause:
                        clauses.append(clause)
                        for item in clause:
                            num_vars = max(num_vars, abs(item))
                    current_clause = []
                else:
                    current_clause.append(literal)

    if current_clause:
        raise ValueError(f"Unterminated DIMACS clause in {path}")

    #print(f"parse: parsed num_vars={num_vars}, clauses={len(clauses)}")
    return num_vars, tuple(clauses)


def simplify_formula(
    formula: Formula,
    literal: Literal,
) -> Optional[Formula]:
    simplified: List[Clause] = []

    for clause in formula:
        if literal in clause:
            continue
        if -literal in clause:
            reduced = tuple(item for item in clause if item != -literal)
            if not reduced:
                return None
            #print(f"reduced {clause} -> {reduced}")
            simplified.append(reduced)
            continue
        simplified.append(clause)

    #print(f"output has {len(simplified)} clauses")
    return tuple(simplified)


def find_unit_literals(formula: Formula) -> List[Literal]:
    unit_literals = [clause[0] for clause in formula if len(clause) == 1]
    return unit_literals


def choose_branch_literal(
    formula: Formula,
    assignment: Assignment,
) -> Literal:
    for clause in formula:
        for literal in clause:
            if abs(literal) not in assignment:
                return literal
    raise ValueError("No unassigned literal available for branching")


def propagate_units(
    formula: Formula,
    assignment: Assignment,
    stats: SolverStats,
) -> Tuple[Optional[Formula], Assignment]:
    working_formula = formula
    working_assignment = dict(assignment)

    while True:
        unit_literals = find_unit_literals(working_formula)
        if not unit_literals:
            return working_formula, working_assignment

        for literal in unit_literals:
            variable = abs(literal)
            value = literal > 0

            if variable in working_assignment:
                if working_assignment[variable] != value:
                    stats.conflicts += 1
                    return None, working_assignment
                continue

            working_assignment[variable] = value
            stats.propagations += 1
            updated_formula = simplify_formula(working_formula, literal)
            if updated_formula is None:
                stats.conflicts += 1
                return None, working_assignment
            working_formula = updated_formula


def dpll(
    formula: Formula,
    assignment: Assignment,
    stats: SolverStats,
    depth: int = 0,
) -> Optional[Assignment]:
    stats.recursive_calls += 1
    stats.max_depth = max(stats.max_depth, depth)

    #print(f"dpll: clauses={len(formula)}, assignment={assignment}")

    propagated_formula, propagated_assignment = propagate_units(formula, assignment, stats)
    if propagated_formula is None:
        return None
    if not propagated_formula:
        return propagated_assignment

    branch_literal = choose_branch_literal(propagated_formula, propagated_assignment)

    for decision_literal in (branch_literal, -branch_literal):
        stats.decisions += 1
        #print(f"dpll: decision try {decision_literal}=True")
        next_assignment = dict(propagated_assignment)
        next_assignment[abs(decision_literal)] = decision_literal > 0
        next_formula = simplify_formula(propagated_formula, decision_literal)

        if next_formula is None:
            stats.conflicts += 1
            continue

        result = dpll(next_formula, next_assignment, stats, depth + 1)
        if result is not None:
            return result

        stats.backtracks += 1
    return None

def solve_formula(formula: Formula) -> SolveResult:
    stats = SolverStats()
    start = time.perf_counter()
    #print(f"{len(formula)} clauses")
    assignment = dpll(formula, {}, stats)
    stats.elapsed_seconds = time.perf_counter() - start
    #print(f"Done is_sat={assignment is not None}")

    return SolveResult(
        is_sat=assignment is not None,
        assignment=assignment or {},
        stats=stats,
    )


def solve_file(path: Path) -> SolveResult:
    _, formula = parse_dimacs(path)
    return solve_formula(formula)


def format_assignment(assignment: Assignment, variables: Iterable[int]) -> str:
    output: List[str] = []
    for variable in sorted(set(variables)):
        value = 1 if assignment.get(variable, False) else 0
        output.append(f"{variable}={value}")
    return " ".join(output)


def collect_variables(formula: Sequence[Clause]) -> Set[int]:
    variables: Set[int] = set()
    for clause in formula:
        for literal in clause:
            variables.add(abs(literal))
    return variables


def build_cli() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Baseline Python DPLL SAT solver.")
    parser.add_argument("inputs", nargs="+", help="DIMACS CNF input files")
    parser.add_argument(
        "--print-stats",
        action="store_true",
        help="Print solver statistics for benchmarking",
    )
    return parser


def main() -> int:
    parser = build_cli()
    args = parser.parse_args()

    for raw_path in args.inputs:
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")

        num_vars, formula = parse_dimacs(path)
        result = solve_formula(formula)

        variables = collect_variables(formula)

        if result.is_sat:
            print("RESULT:SAT")
            print(f"ASSIGNMENT:{format_assignment(result.assignment, variables)}")
        else:
            print("RESULT:UNSAT")

        if args.print_stats:
            print(
                "STATS:"
                f"solver=baseline,"
                f"decisions={result.stats.decisions},"
                f"propagations={result.stats.propagations},"
                f"conflicts={result.stats.conflicts},"
                f"backtracks={result.stats.backtracks},"
                f"recursive_calls={result.stats.recursive_calls},"
                f"max_depth={result.stats.max_depth},"
                f"runtime={result.stats.elapsed_seconds:.6f}s"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
