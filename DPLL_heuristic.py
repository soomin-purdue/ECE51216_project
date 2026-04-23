#!/usr/bin/env python3

from __future__ import annotations

import argparse
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Deque, Dict, Iterable, List, Optional, Sequence, Set, Tuple


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


@dataclass
class WatchedState:
    formula: Formula
    assignment: Assignment
    watch_positions: List[Tuple[int, int]]
    watch_lists: Dict[Literal, List[int]]
    unit_queue: Deque[Literal]

    def copy(self) -> "WatchedState":
        return WatchedState(
            formula=self.formula,
            assignment=self.assignment.copy(),
            watch_positions=self.watch_positions.copy(),
            watch_lists={literal: clause_ids[:] for literal, clause_ids in self.watch_lists.items()},
            unit_queue=deque(self.unit_queue),
        )


def parse_dimacs(path: Path) -> Tuple[int, Formula]:
    clauses: List[Clause] = []
    num_vars = 0
    current_clause: List[int] = []

    with path.open("r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("c"):
                continue
            if line.startswith("%"):
                break
            if line.startswith("p"):
                parts = line.split()
                if len(parts) >= 4:
                    num_vars = int(parts[2])
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

    return num_vars, tuple(clauses)


def simplify_formula(formula: Formula, literal: Literal) -> Optional[Formula]:
    simplified: List[Clause] = []

    for clause in formula:
        if literal in clause:
            continue
        if -literal in clause:
            reduced = tuple(item for item in clause if item != -literal)
            if not reduced:
                return None
            simplified.append(reduced)
            continue
        simplified.append(clause)

    return tuple(simplified)


def find_unit_literals(formula: Formula) -> List[Literal]:
    return [clause[0] for clause in formula if len(clause) == 1]


def literal_value(literal: Literal, assignment: Assignment) -> Optional[bool]:
    variable = abs(literal)
    if variable not in assignment:
        return None

    value = assignment[variable]
    return value if literal > 0 else not value


def clause_is_satisfied(clause: Clause, assignment: Assignment) -> bool:
    return any(literal_value(literal, assignment) is True for literal in clause)


def choose_baseline_literal(formula: Formula, assignment: Assignment) -> Literal:
    for clause in formula:
        if clause_is_satisfied(clause, assignment):
            continue
        for literal in clause:
            if literal_value(literal, assignment) is None:
                return literal
    raise ValueError("No unassigned literal available for branching")


def choose_dlis_literal(formula: Formula, assignment: Assignment) -> Literal:
    literal_counts: Dict[Literal, int] = {}

    for clause in formula:
        if clause_is_satisfied(clause, assignment):
            continue
        for literal in clause:
            if literal_value(literal, assignment) is None:
                literal_counts[literal] = literal_counts.get(literal, 0) + 1

    if not literal_counts:
        raise ValueError("No unassigned literal available for branching")

    return max(
        literal_counts.items(),
        key=lambda item: (item[1], -abs(item[0]), item[0] > 0),
    )[0]


def choose_branch_literal(formula: Formula, assignment: Assignment, heuristic: str) -> Literal:
    if heuristic == "dlis":
        return choose_dlis_literal(formula, assignment)
    return choose_baseline_literal(formula, assignment)


def propagate_units_naive(
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


def dpll_naive(
    formula: Formula,
    assignment: Assignment,
    stats: SolverStats,
    heuristic: str,
    depth: int = 0,
) -> Optional[Assignment]:
    stats.recursive_calls += 1
    stats.max_depth = max(stats.max_depth, depth)

    propagated_formula, propagated_assignment = propagate_units_naive(formula, assignment, stats)
    if propagated_formula is None:
        return None
    if not propagated_formula:
        return propagated_assignment

    branch_literal = choose_branch_literal(propagated_formula, propagated_assignment, heuristic)

    for decision_literal in (branch_literal, -branch_literal):
        stats.decisions += 1
        next_assignment = dict(propagated_assignment)
        next_assignment[abs(decision_literal)] = decision_literal > 0
        next_formula = simplify_formula(propagated_formula, decision_literal)

        if next_formula is None:
            stats.conflicts += 1
            continue

        result = dpll_naive(next_formula, next_assignment, stats, heuristic, depth + 1)
        if result is not None:
            return result

        stats.backtracks += 1

    return None


def build_watched_state(formula: Formula) -> WatchedState:
    watch_positions: List[Tuple[int, int]] = []
    watch_lists: Dict[Literal, List[int]] = {}
    unit_queue: Deque[Literal] = deque()

    for clause_index, clause in enumerate(formula):
        if len(clause) == 1:
            watch_positions.append((0, 0))
            watched_literal = clause[0]
            watch_lists.setdefault(watched_literal, []).append(clause_index)
            unit_queue.append(watched_literal)
            continue

        watch_positions.append((0, 1))
        first_literal = clause[0]
        second_literal = clause[1]
        watch_lists.setdefault(first_literal, []).append(clause_index)
        watch_lists.setdefault(second_literal, []).append(clause_index)

    return WatchedState(
        formula=formula,
        assignment={},
        watch_positions=watch_positions,
        watch_lists=watch_lists,
        unit_queue=unit_queue,
    )


def assign_watched_literal(state: WatchedState, literal: Literal) -> Tuple[bool, bool]:
    variable = abs(literal)
    value = literal > 0

    if variable in state.assignment:
        return state.assignment[variable] == value, False

    state.assignment[variable] = value
    falsified_literal = -literal

    for clause_index in list(state.watch_lists.get(falsified_literal, [])):
        clause = state.formula[clause_index]
        watch_a, watch_b = state.watch_positions[clause_index]

        if clause[watch_b] == falsified_literal and clause[watch_a] != falsified_literal:
            watch_a, watch_b = watch_b, watch_a

        other_index = watch_b
        other_literal = clause[other_index]

        replacement_index: Optional[int] = None
        for index, candidate in enumerate(clause):
            if index == watch_a or index == other_index:
                continue
            if literal_value(candidate, state.assignment) is not False:
                replacement_index = index
                break

        if replacement_index is not None:
            new_literal = clause[replacement_index]
            state.watch_positions[clause_index] = (replacement_index, other_index)
            state.watch_lists[falsified_literal].remove(clause_index)
            state.watch_lists.setdefault(new_literal, []).append(clause_index)
            continue

        other_value = literal_value(other_literal, state.assignment)
        if other_value is False:
            return False, True
        if other_value is None:
            state.unit_queue.append(other_literal)

    return True, True


def propagate_units_watched(state: WatchedState, stats: SolverStats) -> bool:
    while state.unit_queue:
        unit_literal = state.unit_queue.popleft()
        success, assigned_new = assign_watched_literal(state, unit_literal)
        if assigned_new:
            stats.propagations += 1
        if not success:
            stats.conflicts += 1
            return False

    return True


def all_clauses_satisfied(formula: Formula, assignment: Assignment) -> bool:
    return all(clause_is_satisfied(clause, assignment) for clause in formula)


def dpll_watched(
    state: WatchedState,
    stats: SolverStats,
    heuristic: str,
    depth: int = 0,
) -> Optional[Assignment]:
    stats.recursive_calls += 1
    stats.max_depth = max(stats.max_depth, depth)

    if not propagate_units_watched(state, stats):
        return None

    if all_clauses_satisfied(state.formula, state.assignment):
        return state.assignment

    branch_literal = choose_branch_literal(state.formula, state.assignment, heuristic)

    for decision_literal in (branch_literal, -branch_literal):
        stats.decisions += 1
        next_state = state.copy()
        success, _ = assign_watched_literal(next_state, decision_literal)

        if not success:
            stats.conflicts += 1
            continue

        result = dpll_watched(next_state, stats, heuristic, depth + 1)
        if result is not None:
            return result

        stats.backtracks += 1

    return None


def solve_formula(
    formula: Formula,
    heuristic: str = "baseline",
    propagation: str = "naive",
) -> SolveResult:
    stats = SolverStats()
    start = time.perf_counter()

    if propagation == "watched":
        assignment = dpll_watched(build_watched_state(formula), stats, heuristic)
    else:
        assignment = dpll_naive(formula, {}, stats, heuristic)

    stats.elapsed_seconds = time.perf_counter() - start

    return SolveResult(
        is_sat=assignment is not None,
        assignment=assignment or {},
        stats=stats,
    )


def solve_file(path: Path, heuristic: str = "baseline", propagation: str = "naive") -> SolveResult:
    _, formula = parse_dimacs(path)
    return solve_formula(formula, heuristic, propagation)


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
    parser = argparse.ArgumentParser(description="DPLL SAT solver with DLIS and watched literals.")
    parser.add_argument("inputs", nargs="+", help="DIMACS CNF input files")
    parser.add_argument(
        "--heuristic",
        choices=("baseline", "dlis"),
        default="baseline",
        help="Decision heuristic for branch selection",
    )
    parser.add_argument(
        "--propagation",
        choices=("naive", "watched"),
        default="naive",
        help="Propagation method to use inside DPLL",
    )
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

        _, formula = parse_dimacs(path)
        result = solve_formula(formula, heuristic=args.heuristic, propagation=args.propagation)

        variables = collect_variables(formula)

        if result.is_sat:
            print("RESULT:SAT")
            print(f"ASSIGNMENT:{format_assignment(result.assignment, variables)}")
        else:
            print("RESULT:UNSAT")

        if args.print_stats:
            print(
                "STATS:"
                f"heuristic={args.heuristic},"
                f"propagation={args.propagation},"
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
