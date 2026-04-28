#!/usr/bin/env python3

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from DPLL_heuristic import solve_file as solve_heuristic_file


@dataclass(frozen=True)
class Variant:
    name: str
    heuristic: str
    propagation: str


@dataclass
class Record:
    path: Path
    expected_sat: bool
    variant: Variant
    is_sat: bool
    decisions: int
    conflicts: int
    backtracks: int
    runtime: float


VARIANTS = [
    Variant("baseline", "baseline", "baseline"),
    Variant("watched", "baseline", "watched"),
    Variant("dlis+watched", "dlis", "watched"),
]


def collect_inputs(root: Path) -> list[Path]:
    if root.is_file():
        return [root]

    return sorted(path for path in root.rglob("*.cnf") if path.is_file())


def expected_result(path: Path) -> bool:
    return "unsat" not in path.parts


def run_variant(input_path: Path, variant: Variant) -> Record:
    result = solve_heuristic_file(
        input_path,
        heuristic=variant.heuristic,
        propagation=variant.propagation,
    )

    stats = result.stats
    return Record(
        path=input_path,
        expected_sat=expected_result(input_path),
        variant=variant,
        is_sat=result.is_sat,
        decisions=stats.decisions,
        conflicts=stats.conflicts,
        backtracks=stats.backtracks,
        runtime=stats.elapsed_seconds,
    )


def average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def summarize(records: list[Record]) -> dict[str, dict[str, float | str]]:
    summary: dict[str, dict[str, float | str]] = {}

    for variant in VARIANTS:
        rows = [record for record in records if record.variant.name == variant.name]
        correct = sum(record.is_sat == record.expected_sat for record in rows)
        summary[variant.name] = {
            "correct": f"{correct}/{len(rows)}",
            "avg_decisions": average([record.decisions for record in rows]),
            "avg_conflicts": average([record.conflicts for record in rows]),
            "avg_backtracks": average([record.backtracks for record in rows]),
            "avg_runtime": average([record.runtime for record in rows]),
        }

    return summary


def change_text(baseline_value: float, other_value: float) -> str:
    if baseline_value == 0:
        return "n/a"

    delta = ((other_value - baseline_value) / baseline_value) * 100.0
    if abs(delta) < 0.05:
        return "same"
    if other_value < baseline_value:
        return f"{abs(delta):.1f}% lower"
    return f"{abs(delta):.1f}% higher"


def print_summary(title: str, records: list[Record]) -> None:
    if not records:
        return

    summary = summarize(records)
    baseline = summary["baseline"]

    print()
    print(title)
    print("-" * len(title))
    print(
        f"{'Variant':<16}{'Correct':<10}{'Avg Decisions':<16}"
        f"{'Avg Conflicts':<16}{'Avg Backtracks':<18}{'Avg Runtime(s)':<16}"
    )

    for variant in VARIANTS:
        row = summary[variant.name]
        print(
            f"{variant.name:<16}{row['correct']:<10}"
            f"{row['avg_decisions']:<16.2f}{row['avg_conflicts']:<16.2f}"
            f"{row['avg_backtracks']:<18.2f}{row['avg_runtime']:<16.6f}"
        )

    print()
    print("Change vs baseline")
    print(
        f"{'Variant':<16}{'Decisions':<18}{'Conflicts':<18}"
        f"{'Backtracks':<18}{'Runtime':<18}"
    )

    for variant in VARIANTS[1:]:
        row = summary[variant.name]
        print(
            f"{variant.name:<16}"
            f"{change_text(float(baseline['avg_decisions']), float(row['avg_decisions'])):<18}"
            f"{change_text(float(baseline['avg_conflicts']), float(row['avg_conflicts'])):<18}"
            f"{change_text(float(baseline['avg_backtracks']), float(row['avg_backtracks'])):<18}"
            f"{change_text(float(baseline['avg_runtime']), float(row['avg_runtime'])):<18}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DPLL benchmark variants and print a comparison summary.")
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

    all_records: list[Record] = []

    for input_path in inputs:
        print()
        print(f"Running {input_path}")
        expected = "SAT" if expected_result(input_path) else "UNSAT"
        print(f"Expected: {expected}")

        for variant in VARIANTS:
            record = run_variant(input_path, variant)
            all_records.append(record)
            status = "SAT" if record.is_sat else "UNSAT"
            correct = "OK" if record.is_sat == record.expected_sat else "WRONG"
            print(
                f"{variant.name:<16}"
                f"result={status:<5} "
                f"check={correct:<5} "
                f"decisions={record.decisions:<4} "
                f"conflicts={record.conflicts:<4} "
                f"backtracks={record.backtracks:<4} "
                f"runtime={record.runtime:.6f}s"
            )

    sat_records = [record for record in all_records if record.expected_sat]
    unsat_records = [record for record in all_records if not record.expected_sat]

    print_summary("Overall Summary", all_records)
    print_summary("SAT Summary", sat_records)
    print_summary("UNSAT Summary", unsat_records)

    print()
    print("Done.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
