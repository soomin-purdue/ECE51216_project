#!/usr/bin/env python3

import argparse
import time
from collections import deque
from pathlib import Path


UNSET = -1


class SolverStats:
    def __init__(self):
        self.decisions = 0
        self.propagations = 0
        self.conflicts = 0
        self.backtracks = 0
        self.recursive_calls = 0
        self.max_depth = 0
        self.elapsed_seconds = 0.0


class SolverOutput:
    def __init__(self, is_sat, assignment, stats):
        self.is_sat = is_sat
        self.assignment = assignment
        self.stats = stats


def parse_dimacs(path):
    clauses = []
    clause_buf = []
    num_vars = 0
    saw_header = False

    # Read DIMACS file line by line. We keep one temporary clause because
    # sometimes the clause can continue on next line.
    with open(path, "r", encoding="utf-8") as fh:
        for line_no, raw in enumerate(fh, 1):
            line = raw.strip()

            if not line:
                continue
            if line.startswith("c"):
                continue
            if line.startswith("%"):
                break
            if line.startswith("p"):
                parts = line.split()
                if len(parts) < 4 or parts[1] != "cnf":
                    raise ValueError(f"{path}:{line_no}: bad DIMACS header")
                num_vars = int(parts[2])
                saw_header = True
                #print(f"parse: header variables={parts[2]}, clauses={parts[3]}")
                continue

            # Real DIMACS files are rarely pretty: a clause might span lines,
            # and some generators pack several clauses onto one line.
            for token in line.split():
                try:
                    lit = int(token)
                except ValueError as exc:
                    raise ValueError(f"{path}:{line_no}: bad token {token!r}") from exc

                if lit == 0:
                    if clause_buf:
                        clause = tuple(clause_buf)
                        clauses.append(clause)
                        for item in clause:
                            num_vars = max(num_vars, abs(item))
                        #print(f"parse: clause={clause}")
                        clause_buf = []
                    continue

                clause_buf.append(lit)

    if not saw_header:
        raise ValueError(f"{path}: missing DIMACS header")
    if clause_buf:
        raise ValueError(f"{path}: unterminated clause at end of file")

    #print(f"parse: parsed num_vars={num_vars}, clauses={len(clauses)}")
    return num_vars, tuple(clauses)


class SATSolver:
    def __init__(self, num_vars, clauses, heuristic="baseline", propagation="baseline"):
        self.num_vars = num_vars
        self.clauses = clauses
        self.heuristic = heuristic
        self.propagation = propagation
        self.stats = SolverStats()

        # Assignment is stored by variable number. -1 means we did not set it.
        self.vals = [UNSET] * (num_vars + 1)
        self.trail = []

        # Watched literal buckets are flat list. Literal x is stored at
        # x + offset, so negative literals also can be array index.
        self.watch_pos = []
        self.watch_offset = num_vars
        self.watch_buckets = [[] for _ in range(2 * num_vars + 1)]
        self.watch_moves = []
        self.root_units = deque()

        if propagation == "watched":
            self._init_watches()

    def solve(self):
        started_at = time.perf_counter()
        #print(f"solve: heuristic={self.heuristic}, propagation={self.propagation}")

        if self.propagation == "watched":
            result = self._solve_watched()
        else:
            result = self._search_baseline(self.clauses, depth=0)

        self.stats.elapsed_seconds = time.perf_counter() - started_at

        if result is None:
            return SolverOutput(False, {}, self.stats)

        return SolverOutput(True, result, self.stats)

    def _solve_watched(self):
        if not self._bcp_watched(deque(self.root_units)):
            return None

        return self._search_watched(depth=0)

    def _init_watches(self):
        for cid, clause in enumerate(self.clauses):
            if len(clause) == 1:
                # Unit clause only has one literal, so both watches point same.
                lit = clause[0]
                self.watch_pos.append((0, 0))
                self.watch_buckets[lit + self.watch_offset].append(cid)
                self.root_units.append(lit)
                #print(f"init: clause {cid} unit {lit}")
                continue

            # For longer clause we start by watching first two literals.
            left = clause[0]
            right = clause[1]
            self.watch_pos.append((0, 1))
            self.watch_buckets[left + self.watch_offset].append(cid)
            self.watch_buckets[right + self.watch_offset].append(cid)
            #print(f"init: clause {cid} watches {left}, {right}")

    def _snapshot(self):
        out = {}

        for var in range(1, self.num_vars + 1):
            if self.vals[var] != UNSET:
                out[var] = bool(self.vals[var])

        return out

    def _lit_value(self, lit):
        raw = self.vals[abs(lit)]
        if raw == UNSET:
            return None
        if lit > 0:
            return bool(raw)
        return not bool(raw)

    def _clause_is_true(self, clause):
        for lit in clause:
            if self._lit_value(lit) is True:
                return True
        return False

    def _all_true(self, clauses):
        for clause in clauses:
            if not self._clause_is_true(clause):
                return False
        return True

    def _assign(self, lit):
        var = abs(lit)
        bit = 1 if lit > 0 else 0
        cur = self.vals[var]

        # If variable was already assigned, just check if it agrees.
        if cur != UNSET:
            return cur == bit, False

        self.vals[var] = bit
        self.trail.append(var)
        #print(f"assign: set x{var}={bit}")
        return True, True

    def _rollback_vals(self, trail_mark):
        while len(self.trail) > trail_mark:
            var = self.trail.pop()
            self.vals[var] = UNSET
            #print(f"rollback: unset x{var}")

    def _rollback_watch(self, trail_mark, watch_mark):
        # During search we mutate watch lists. This undo the watch moves when
        # recursive branch fails.
        while len(self.watch_moves) > watch_mark:
            cid, old_pos, old_lit, new_lit = self.watch_moves.pop()

            self.watch_buckets[new_lit + self.watch_offset].remove(cid)

            self.watch_pos[cid] = old_pos
            self.watch_buckets[old_lit + self.watch_offset].append(cid)

        self._rollback_vals(trail_mark)

    def _find_units(self, clauses):
        units = []

        for clause in clauses:
            if len(clause) == 1:
                units.append(clause[0])

        return units

    def _simplify(self, clauses, lit):
        out = []

        for clause in clauses:
            # If clause contains true literal, whole clause is already satisfied.
            if lit in clause:
                continue

            if -lit in clause:
                # Remove the false literal from clause for naive DPLL version.
                reduced = []
                for item in clause:
                    if item != -lit:
                        reduced.append(item)

                if not reduced:
                    return None

                #print(f"reduced {clause} -> {tuple(reduced)}")
                out.append(tuple(reduced))
                continue

            out.append(clause)

        #print(f"after {lit}, clauses={len(out)}")
        return tuple(out)

    def _pick_branch_lit(self, clauses):
        if self.heuristic == "dlis":
            return self._pick_dlis_lit(clauses)
        return self._pick_first_lit(clauses)

    def _pick_first_lit(self, clauses):
        for clause in clauses:
            if self._clause_is_true(clause):
                continue

            for lit in clause:
                if self._lit_value(lit) is None:
                    return lit

        raise ValueError("No branch literal available")

    def _pick_dlis_lit(self, clauses):
        counts = {}

        # DLIS counts only literals that are still not assigned in unsatisfied
        # clauses. The most frequent literal is used as next decision.
        for clause in clauses:
            if self._clause_is_true(clause):
                continue

            for lit in clause:
                if self._lit_value(lit) is None:
                    counts[lit] = counts.get(lit, 0) + 1

        if not counts:
            raise ValueError("No branch literal available")

        best_lit = None
        best_key = None

        for lit, freq in counts.items():
            # Tie-break on lower variable id so benchmarks stay deterministic.
            key = (freq, -abs(lit), lit > 0)
            if best_key is None or key > best_key:
                best_key = key
                best_lit = lit
        return best_lit

    def _bcp_baseline(self, clauses):
        cur = clauses

        # Keep applying unit propagation until no unit clauses remain.
        while True:
            units = self._find_units(cur)
            if not units:
                return cur

            #print(f"bcp baseline: units={units}")
            for lit in units:
                ok, fresh = self._assign(lit)
                if not ok:
                    self.stats.conflicts += 1
                    return None
                if not fresh:
                    continue

                self.stats.propagations += 1
                cur = self._simplify(cur, lit)
                if cur is None:
                    self.stats.conflicts += 1
                    return None

    def _search_baseline(self, clauses, depth=0):
        self.stats.recursive_calls += 1
        self.stats.max_depth = max(self.stats.max_depth, depth)
        #print(f"dpll baseline: depth={depth}, clauses={len(clauses)}, trail={self.trail}")

        frame_mark = len(self.trail)
        cur = self._bcp_baseline(clauses)
        if cur is None:
            self._rollback_vals(frame_mark)
            return None

        if not cur:
            return self._snapshot()

        lit = self._pick_branch_lit(cur)

        for choice in (lit, -lit):
            self.stats.decisions += 1
            #print(f"dpll: try {choice} at depth={depth}")

            trail_mark = len(self.trail)
            ok, _ = self._assign(choice)
            if not ok:
                self.stats.conflicts += 1
                self._rollback_vals(trail_mark)
                continue

            next_clauses = self._simplify(cur, choice)
            if next_clauses is None:
                self.stats.conflicts += 1
                self._rollback_vals(trail_mark)
                continue

            result = self._search_baseline(next_clauses, depth + 1)
            if result is not None:
                return result

            self._rollback_vals(trail_mark)
            self.stats.backtracks += 1
            #print(f"dpll: backtrack from {choice}")

        self._rollback_vals(frame_mark)
        return None

    def _assign_watched(self, lit, q):
        ok, fresh = self._assign(lit)
        if not ok or not fresh:
            return ok, fresh

        # Only clauses watching the opposite literal can become problematic.
        dead = -lit
        dead_bucket = self.watch_buckets[dead + self.watch_offset]
        touched = dead_bucket[:]
        #print(f"{lit}, checking clauses watching {dead}: {touched}")

        for cid in touched:
            clause = self.clauses[cid]
            w0, w1 = self.watch_pos[cid]

            if clause[w1] == dead and clause[w0] != dead:
                w0, w1 = w1, w0

            other_idx = w1
            other_lit = clause[other_idx]
            alt_idx = None

            # Try to move the dead watch to a literal that is not false.
            for idx, cand in enumerate(clause):
                if idx == w0 or idx == other_idx:
                    continue
                if self._lit_value(cand) is not False:
                    alt_idx = idx
                    break

            if alt_idx is not None:
                w_lit = clause[alt_idx]
                old_pos = self.watch_pos[cid]
                self.watch_pos[cid] = (alt_idx, other_idx)
                dead_bucket.remove(cid)
                self.watch_buckets[w_lit + self.watch_offset].append(cid)
                self.watch_moves.append((cid, old_pos, dead, w_lit))
                #print(f"clause {cid}, {dead} -> {w_lit}")
                continue

            other_val = self._lit_value(other_lit)
            if other_val is False:
                #print(f"watched conflict: clause {cid}")
                return False, fresh
            if other_val is None:
                # No replacement found, so other watch becomes new unit literal.
                q.append(other_lit)
                #print(f"clause {cid} forces {other_lit}")

        return True, fresh

    def _bcp_watched(self, q):
        # Queue contains literals that must be propagated by watched-literal BCP.
        while q:
            lit = q.popleft()
            ok, fresh = self._assign_watched(lit, q)
            if not ok:
                self.stats.conflicts += 1
                return False
            if fresh:
                self.stats.propagations += 1

        return True

    def _search_watched(self, depth=0):
        self.stats.recursive_calls += 1
        self.stats.max_depth = max(self.stats.max_depth, depth)
        #print(f"dpll: depth={depth}, assigned={len(self.trail)}")

        # If all clauses are already true, current partial assignment is enough.
        if self._all_true(self.clauses):
            return self._snapshot()

        lit = self._pick_branch_lit(self.clauses)

        for choice in (lit, -lit):
            self.stats.decisions += 1
            #print(f"dpll: try {choice} at depth={depth}")

            trail_mark = len(self.trail)
            watch_mark = len(self.watch_moves)
            q = deque()

            ok, _ = self._assign_watched(choice, q)
            if not ok:
                self.stats.conflicts += 1
                self._rollback_watch(trail_mark, watch_mark)
                continue

            if not self._bcp_watched(q):
                self._rollback_watch(trail_mark, watch_mark)
                self.stats.backtracks += 1
                continue

            result = self._search_watched(depth + 1)
            if result is not None:
                return result

            self._rollback_watch(trail_mark, watch_mark)
            self.stats.backtracks += 1
            #print(f"dpll: backtrack from {choice}")

        return None


def solve_formula(clauses, heuristic="baseline", propagation="baseline", num_vars=None):
    if num_vars is None:
        num_vars = 0
        for clause in clauses:
            for lit in clause:
                num_vars = max(num_vars, abs(lit))

    solver = SATSolver(num_vars, clauses, heuristic=heuristic, propagation=propagation)
    return solver.solve()


def solve_file(path, heuristic="baseline", propagation="baseline"):
    num_vars, clauses = parse_dimacs(path)
    return solve_formula(clauses, heuristic, propagation, num_vars=num_vars)


def format_assignment(assignment, num_vars, clauses):
    seen = set()

    for clause in clauses:
        for lit in clause:
            seen.add(abs(lit))

    if not seen:
        seen = set(range(1, num_vars + 1))

    parts = []
    for var in sorted(seen):
        value = 1 if assignment.get(var, False) else 0
        parts.append(f"{var}={value}")

    return " ".join(parts)


def build_cli():
    parser = argparse.ArgumentParser(description="DPLL SAT solver with DLIS and watched literals.")
    parser.add_argument("inputs", nargs="+", help="DIMACS CNF input files")
    parser.add_argument(
        "--heuristic",
        choices=("baseline", "dlis"),
        default="dlis",
        help="Decision heuristic for branch selection",
    )
    parser.add_argument(
        "--propagation",
        choices=("baseline", "watched"),
        default="watched",
        help="Propagation method to use inside DPLL",
    )
    parser.add_argument(
        "--print-stats",
        action="store_true",
        help="Print solver statistics for benchmarking",
    )
    return parser


def main():
    parser = build_cli()
    args = parser.parse_args()

    for raw_path in args.inputs:
        path = Path(raw_path)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")

        num_vars, clauses = parse_dimacs(path)
        result = solve_formula(
            clauses,
            heuristic=args.heuristic,
            propagation=args.propagation,
            num_vars=num_vars,
        )

        if result.is_sat:
            print("RESULT:SAT")
            print(f"ASSIGNMENT:{format_assignment(result.assignment, num_vars, clauses)}")
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


if __name__ == "__main__":
    main()
