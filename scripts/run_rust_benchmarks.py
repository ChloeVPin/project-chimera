"""
Project Chimera: Phase 3 - Cross-Language Comparative Benchmark Runner (Rust vs TypeScript)

Automated telemetry runner for rustc's trait resolution engine:
- Evaluates Rule 110 evolution via Horn-clause trait resolution
- Systematically measures compile time, wall clock latency, and E0275 overflow limits
- Compares Rust's nominal Horn-clause unification against TypeScript's structural conditional engine
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

def run_rust_benchmarks():
    rust_src_dir = Path("rust_chimera").resolve()
    rlib_path = rust_src_dir / "target" / "debug" / "librust_chimera.rlib"
    deps_dir = rust_src_dir / "target" / "debug" / "deps"

    # Ensure library is compiled
    subprocess.run(["cargo", "build"], cwd=rust_src_dir, check=True, stdout=subprocess.DEVNULL)

    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    temp_rs = Path(".temp_bench_rust.rs")

    results = {
        "metadata": {
            "compiler": "rustc 1.97.0",
            "model": "Rule 110 Cellular Automaton via Horn-Clause Trait Resolution",
            "default_recursion_limit": 128
        },
        "default_limit_sweep": [],
        "extended_limit_sweep": []
    }

    print("================================================================")
    print("Project Chimera: Phase 3 Cross-Language Comparative Benchmarks")
    print("Language: Rust (Nominal Horn-Clause Trait Resolution)")
    print("================================================================\n")

    # 1. Sweep under default recursion limit (128)
    print(">>> Running Experiment 3A: Rust Default Limit Sweep (limit = 128)...")
    steps_default = [1, 5, 10, 25, 50, 75, 100, 110, 120, 125, 126, 127, 128]
    for s in steps_default:
        peano = "PeanoZero"
        for _ in range(s):
            peano = f"PeanoSucc<{peano}>"

        code = f"""
#![recursion_limit = "128"]
use rust_chimera::*;

pub fn probe() {{
    type T0 = Cons<Zero, Cons<One, Cons<One, Cons<Zero, Cons<One, Cons<One, Cons<One, Cons<Zero, Nil>>>>>>>>;
    type Out = <T0 as Evolve<{peano}>>::Output;
    let _ = std::marker::PhantomData::<Out>;
}}
"""
        with open(temp_rs, "w") as f:
            f.write(code)

        cmd = [
            "rustc",
            "--edition=2021",
            "--crate-type=lib",
            "--crate-name=bench_probe",
            f"--extern=rust_chimera={rlib_path}",
            f"-Ldependency={deps_dir}",
            str(temp_rs),
            "-o", ".temp_bench_rust.rmeta"
        ]

        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        wall_time_ms = (time.time() - t0) * 1000.0

        success = (proc.returncode == 0)
        e0275 = "E0275" in proc.stderr

        entry = {
            "steps": s,
            "recursion_limit": 128,
            "success": success,
            "wall_time_ms": wall_time_ms,
            "error_e0275": e0275
        }
        results["default_limit_sweep"].append(entry)
        status_str = "PASS" if success else ("FAIL (E0275 Overflow)" if e0275 else "FAIL (Other)")
        print(f"  S = {s:3d} | WallTime: {wall_time_ms:6.1f}ms | Status: {status_str}")

    # 2. Sweep under extended recursion limit (2048)
    print("\n>>> Running Experiment 3B: Rust Extended Limit Sweep (limit = 2048)...")
    steps_extended = [10, 50, 100, 250, 500, 750, 1000, 1250, 1500, 1750, 2000, 2046, 2047]
    for s in steps_extended:
        peano = "PeanoZero"
        for _ in range(s):
            peano = f"PeanoSucc<{peano}>"

        code = f"""
#![recursion_limit = "2048"]
use rust_chimera::*;

pub fn probe() {{
    type T0 = Cons<Zero, Cons<One, Cons<One, Cons<Zero, Cons<One, Cons<One, Cons<One, Cons<Zero, Nil>>>>>>>>;
    type Out = <T0 as Evolve<{peano}>>::Output;
    let _ = std::marker::PhantomData::<Out>;
}}
"""
        with open(temp_rs, "w") as f:
            f.write(code)

        cmd = [
            "rustc",
            "--edition=2021",
            "--crate-type=lib",
            "--crate-name=bench_probe",
            f"--extern=rust_chimera={rlib_path}",
            f"-Ldependency={deps_dir}",
            str(temp_rs),
            "-o", ".temp_bench_rust.rmeta"
        ]

        t0 = time.time()
        proc = subprocess.run(cmd, capture_output=True, text=True)
        wall_time_ms = (time.time() - t0) * 1000.0

        success = (proc.returncode == 0)
        e0275 = "E0275" in proc.stderr

        entry = {
            "steps": s,
            "recursion_limit": 2048,
            "success": success,
            "wall_time_ms": wall_time_ms,
            "error_e0275": e0275
        }
        results["extended_limit_sweep"].append(entry)
        status_str = "PASS" if success else ("FAIL (E0275 Overflow)" if e0275 else "FAIL (Other)")
        print(f"  S = {s:4d} | WallTime: {wall_time_ms:6.1f}ms | Status: {status_str}")

    # Cleanup temp files
    if temp_rs.exists():
        temp_rs.unlink()
    rmeta = Path(".temp_bench_rust.rmeta")
    if rmeta.exists():
        rmeta.unlink()

    out_file = data_dir / "phase3_rust_comparison_results.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n[+] Phase 3 Rust Comparative Benchmark Results saved to: {out_file}")

if __name__ == "__main__":
    run_rust_benchmarks()
