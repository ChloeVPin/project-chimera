"""
Project Chimera: Phase 6 - Pathological Freeze Benchmark Runner

Measures compiler solver duration under subverted cycle detection:
- TypeScript Quaternary Frontier Saturation (b=4)
- Rust Exponential Trait Projection Normalization (b=2)
"""

import json
import os
import subprocess
import time
from pathlib import Path

def run_phase6():
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)

    results = {
        "typescript_quaternary_freeze": [],
        "rust_exponential_projection_freeze": []
    }

    print("================================================================")
    print("Project Chimera: Phase 6 Pathological Freeze Suite")
    print("Subverting Compiler Cycle Detectors with <30 Lines of Code")
    print("================================================================\n")

    # 1. TypeScript Quaternary Frontier Saturation
    print(">>> Running Experiment 6A: TypeScript Quaternary Tree (b = 4)...")
    for d in [5, 6, 7, 8, 9]:
        leaves = 4 ** d
        code = f"""
type QuaternaryFreeze<Depth extends number, Path extends readonly unknown[] = []> =
  Path["length"] extends Depth
    ? 1
    : [
        QuaternaryFreeze<Depth, [0, ...Path]>,
        QuaternaryFreeze<Depth, [1, ...Path]>,
        QuaternaryFreeze<Depth, [2, ...Path]>,
        QuaternaryFreeze<Depth, [3, ...Path]>
      ] extends [infer A, infer B, infer C, infer D]
      ? [A, B, C, D]
      : never;
type Target = QuaternaryFreeze<{d}>;
"""
        temp_ts = Path(".temp_freeze.ts")
        with open(temp_ts, "w") as f:
            f.write(code)

        t0 = time.time()
        proc = subprocess.run(
            ["npx", "tsc", "--noEmit", "--extendedDiagnostics", "--ignoreConfig", "--strict", str(temp_ts)],
            capture_output=True,
            text=True
        )
        wall_ms = (time.time() - t0) * 1000.0
        temp_ts.unlink(missing_ok=True)

        combined = proc.stdout + proc.stderr
        import re
        inst = re.search(r"Instantiations:\s+(\d+)", combined)
        inst_cnt = int(inst.group(1)) if inst else 0
        mem = re.search(r"Memory used:\s+(\d+)K", combined)
        mem_kb = int(mem.group(1)) if mem else 0
        check = re.search(r"Check time:\s+([\d\.]+)s", combined)
        check_s = float(check.group(1)) if check else 0.0

        entry = {
            "depth": d,
            "branching_factor": 4,
            "leaves": leaves,
            "instantiations": inst_cnt,
            "heap_mb": mem_kb / 1024.0,
            "check_time_s": check_s,
            "wall_ms": wall_ms,
            "exit_code": proc.returncode,
            "success": proc.returncode == 0
        }
        results["typescript_quaternary_freeze"].append(entry)
        status_str = "PASS" if proc.returncode == 0 else "FAIL"
        print(f"  TS Depth {d:2d} (4^{d} = {leaves:7d} leaves) | Inst: {inst_cnt:8d} | Mem: {mem_kb/1024.0:6.1f} MB | Check: {check_s:.3f}s | Wall: {wall_ms:6.1f}ms | Status: {status_str}")

    # 2. Rust Exponential Projection Normalization
    print("\n>>> Running Experiment 6B: Rust Exponential Projection Normalization (b = 2)...")
    for d in [14, 16, 18, 20, 22, 23]:
        nodes = 2 ** d
        lines = [
            "pub struct Nil;",
            "pub struct Cons<H, T>(std::marker::PhantomData<(H, T)>);",
            "pub trait Eval { type Out; }",
            "impl Eval for Nil { type Out = Nil; }",
            "impl<H: Eval, T: Eval> Eval for Cons<H, T> {",
            "    type Out = Cons<<H as Eval>::Out, <T as Eval>::Out>;",
            "}",
            "type T0 = Nil;"
        ]
        for i in range(1, d + 1):
            lines.append(f"type T{i} = Cons<T{i-1}, T{i-1}>;")
        lines.append(f"pub fn freeze() {{ type Sol = <T{d} as Eval>::Out; let _ = std::marker::PhantomData::<Sol>; }}")
        code = "\n".join(lines)

        temp_rs = Path(".temp_freeze.rs")
        with open(temp_rs, "w") as f:
            f.write(code)

        t0 = time.time()
        proc = subprocess.run(
            ["rustc", "--edition=2021", "--crate-type=lib", "--crate-name=freeze_bench", str(temp_rs), "-o", ".temp_freeze.rmeta"],
            capture_output=True,
            text=True
        )
        wall_ms = (time.time() - t0) * 1000.0
        temp_rs.unlink(missing_ok=True)
        Path(".temp_freeze.rmeta").unlink(missing_ok=True)

        entry = {
            "depth": d,
            "branching_factor": 2,
            "nodes": nodes,
            "wall_ms": wall_ms,
            "wall_s": wall_ms / 1000.0,
            "exit_code": proc.returncode,
            "success": proc.returncode == 0
        }
        results["rust_exponential_projection_freeze"].append(entry)
        status_str = "PASS" if proc.returncode == 0 else "FAIL"
        print(f"  Rust Depth {d:2d} (2^{d} = {nodes:8d} nodes) | Wall: {wall_ms/1000.0:6.3f}s ({wall_ms:7.1f}ms) | Status: {status_str}")

    out_file = data_dir / "phase6_pathological_results.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\n[+] Phase 6 Pathological Freeze Results saved to: {out_file}")

if __name__ == "__main__":
    run_phase6()
