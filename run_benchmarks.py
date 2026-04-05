#!/usr/bin/env python3

from __future__ import annotations

import argparse
from pathlib import Path

from sat_solver import solve_file


def collect_inputs(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    return sorted(path for path in root.rglob("*.cnf") if path.is_file())


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local benchmark set for the SAT solver.")
    parser.add_argument(
        "path",
        nargs="?",
        default="benchmarks",
        help="A benchmark directory or a single CNF file",
    )
    args = parser.parse_args()

    root = Path(args.path)
    if not root.exists():
        raise FileNotFoundError(f"Benchmark path not found: {root}")

    inputs = collect_inputs(root)
    if not inputs:
        raise FileNotFoundError(f"No CNF files found under: {root}")

    print("file,result,decisions,propagations,conflicts,backtracks,recursive_calls,max_depth,runtime_s")
    for input_path in inputs:
        result = solve_file(input_path)
        stats = result.stats
        status = "SAT" if result.is_sat else "UNSAT"
        print(
            f"{input_path},{status},{stats.decisions},{stats.propagations},"
            f"{stats.conflicts},{stats.backtracks},{stats.recursive_calls},"
            f"{stats.max_depth},{stats.elapsed_seconds:.6f}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
