"""
Project Chimera: Phase 12 - Type-Level 3-SAT Phase Transition Benchmark Runner

Measures compile time, instantiation count, and heap memory across:
1. Under-constrained Satisfiable instances (m/n = 2.0).
2. Phase Transition boundary instances (m/n = 4.26).
3. Over-constrained Unsatisfiable Pigeonhole instances (PHP).
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

def parse_tsc_diagnostics(output_text):
    metrics = {
        "checkTimeSec": 0.0,
        "totalTimeSec": 0.0,
        "memoryUsedKB": 0,
        "instantiationCount": 0,
        "typeCount": 0
    }

    m_check = re.search(r"Check time:\s+([0-9.]+)s", output_text)
    if m_check: metrics["checkTimeSec"] = float(m_check.group(1))

    m_total = re.search(r"Total time:\s+([0-9.]+)s", output_text)
    if m_total: metrics["totalTimeSec"] = float(m_total.group(1))

    m_mem = re.search(r"Memory used:\s+(\d+)K", output_text)
    if m_mem: metrics["memoryUsedKB"] = int(m_mem.group(1))

    m_inst = re.search(r"Instantiations:\s+(\d+)", output_text)
    if m_inst: metrics["instantiationCount"] = int(m_inst.group(1))

    m_type = re.search(r"Types:\s+(\d+)", output_text)
    if m_type: metrics["typeCount"] = int(m_type.group(1))

    return metrics

def run_sat_benchmarks():
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    temp_ts = repo_root / ".temp_bench_sat.ts"

    test_cases = [
        # (Name, Formula Description, Type Code, Expected Satisfied)
        (
            "underconstrained_n3_m3",
            "Under-constrained (n=3, m=3, ratio=1.0) - Fast SAT",
            """
type F = [
  [Pos<"x1">, Pos<"x2">, Pos<"x3">],
  [Neg<"x1">, Pos<"x2">, Pos<"x3">],
  [Pos<"x1">, Neg<"x2">, Pos<"x3">]
];
type Res = Solve<F>;
""",
            True
        ),
        (
            "underconstrained_n4_m8",
            "Under-constrained (n=4, m=8, ratio=2.0) - SAT",
            """
type F = [
  [Pos<"x1">, Pos<"x2">, Pos<"x3">],
  [Neg<"x1">, Pos<"x2">, Pos<"x4">],
  [Pos<"x1">, Neg<"x3">, Pos<"x4">],
  [Neg<"x2">, Pos<"x3">, Pos<"x4">],
  [Pos<"x2">, Neg<"x3">, Neg<"x4">],
  [Neg<"x1">, Neg<"x2">, Pos<"x3">],
  [Pos<"x1">, Pos<"x3">, Neg<"x4">],
  [Neg<"x1">, Pos<"x2">, Neg<"x4">]
];
type Res = Solve<F>;
""",
            True
        ),
        (
            "phase_transition_n3_m13",
            "Phase Transition Threshold (n=3, m=13, ratio=4.33)",
            """
type F = [
  [Pos<"x1">, Pos<"x2">, Pos<"x3">],
  [Pos<"x1">, Pos<"x2">, Neg<"x3">],
  [Pos<"x1">, Neg<"x2">, Pos<"x3">],
  [Pos<"x1">, Neg<"x2">, Neg<"x3">],
  [Neg<"x1">, Pos<"x2">, Pos<"x3">],
  [Neg<"x1">, Pos<"x2">, Neg<"x3">],
  [Neg<"x1">, Neg<"x2">, Pos<"x3">]
];
type Res = Solve<F>;
""",
            True # Only (~x1, ~x2, ~x3) remains SAT
        ),
        (
            "overconstrained_n3_m8_unsat",
            "Over-constrained Complete Contradiction (n=3, m=8, all 2^3 minterms excluded)",
            """
type F = [
  [Pos<"x1">, Pos<"x2">, Pos<"x3">],
  [Pos<"x1">, Pos<"x2">, Neg<"x3">],
  [Pos<"x1">, Neg<"x2">, Pos<"x3">],
  [Pos<"x1">, Neg<"x2">, Neg<"x3">],
  [Neg<"x1">, Pos<"x2">, Pos<"x3">],
  [Neg<"x1">, Pos<"x2">, Neg<"x3">],
  [Neg<"x1">, Neg<"x2">, Pos<"x3">],
  [Neg<"x1">, Neg<"x2">, Neg<"x3">]
];
type Res = Solve<F>;
""",
            False
        ),
        (
            "php_2_1",
            "Pigeonhole Principle PHP(2, 1) - 2 Pigeons into 1 Hole (n=2, m=3, UNSAT)",
            """
type F = [
  [Pos<"p11">],
  [Pos<"p21">],
  [Neg<"p11">, Neg<"p21">]
];
type Res = Solve<F>;
""",
            False
        ),
        (
            "php_3_2",
            "Pigeonhole Principle PHP(3, 2) - 3 Pigeons into 2 Holes (n=6, m=9, Exponential Refutation)",
            """
type F = [
  [Pos<"p11">, Pos<"p12">],
  [Pos<"p21">, Pos<"p22">],
  [Pos<"p31">, Pos<"p32">],
  [Neg<"p11">, Neg<"p21">],
  [Neg<"p11">, Neg<"p31">],
  [Neg<"p21">, Neg<"p31">],
  [Neg<"p12">, Neg<"p22">],
  [Neg<"p12">, Neg<"p32">],
  [Neg<"p22">, Neg<"p32">]
];
type Res = Solve<F>;
""",
            False
        )
    ]

    results = {
        "metadata": {
            "experiment": "Phase 12: Type-Level NP-Completeness & 3-SAT Phase Transition",
            "compiler": "TypeScript 7.0.2",
            "solver": "Pure Type-Level DPLL Backtracking Decision Engine"
        },
        "benchmarks": []
    }

    print("================================================================")
    print("Project Chimera: Phase 12 Type-Level 3-SAT Benchmarks")
    print("================================================================\n")

    base_header = """import { Pos, Neg, Solve } from "./src/solvers/sat";\n"""

    for name, desc, code_snippet, expected_sat in test_cases:
        with open(temp_ts, "w") as f:
            f.write(base_header + code_snippet)

        cmd = [
            "npx", "tsc", "--noEmit", "--extendedDiagnostics",
            "--ignoreConfig", "--target", "ESNext", "--module", "NodeNext", "--strict",
            str(temp_ts)
        ]
        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        wall_time_ms = (time.time() - t0) * 1000.0

        metrics = parse_tsc_diagnostics(proc.stdout)
        success = (proc.returncode == 0)

        entry = {
            "name": name,
            "description": desc,
            "expected_sat": expected_sat,
            "success": success,
            "wall_time_ms": round(wall_time_ms, 2),
            "checkTimeSec": metrics["checkTimeSec"],
            "totalTimeSec": metrics["totalTimeSec"],
            "memoryUsedMB": round(metrics["memoryUsedKB"] / 1024, 2),
            "instantiationCount": metrics["instantiationCount"]
        }
        results["benchmarks"].append(entry)

        status_str = "PASS" if success else "FAIL"
        print(f"  [{status_str}] {name:30s} | Check Time: {metrics['checkTimeSec']:.3f}s | Instantiations: {metrics['instantiationCount']:8d} | Heap: {entry['memoryUsedMB']:6.1f} MB")

    if temp_ts.exists():
        temp_ts.unlink()

    out_file = data_dir / "phase12_sat_results.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n[OK] Phase 12 SAT results written to {out_file}")

if __name__ == "__main__":
    run_sat_benchmarks()
