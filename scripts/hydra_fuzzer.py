"""
Project Chimera: Phase 13 - Project Hydra Automated Compiler Fuzzer & ICE Hunter

Synthesizes adversarial type constructs targeting:
1. TypeScript (tsc --noEmit)
2. Rust (rustc)
3. C++20 (Apple Clang clang++ -std=c++20)

Monitors process exit codes, signals, and fatal diagnostics to detect non-graceful crashes:
- Signal 10 / 11: SIGBUS / SIGSEGV (Stack overflow / memory corruption)
- Signal 4: SIGILL (Frontend crash / illegal instruction)
- Signal 6 / Exit 134: SIGABRT / Node.js Heap OOM
- Rustc ICE (Internal Compiler Error)

Saves all reproducible crashing seeds and reproduction logs into `crashes/`.
"""

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CRASHES_DIR = REPO_ROOT / "crashes"
DATA_DIR = REPO_ROOT / "data"

def ensure_dirs():
    CRASHES_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================================
# Adversarial Generators
# ============================================================================

def generate_rust_deep_projection(depth=40000, recursion_limit=10000000):
    """
    Generates a deep nominal trait projection that bypasses user recursion limits
    and exhausts the native OS thread stack in rustc's trait resolution engine.
    """
    deep_term = "()"
    for _ in range(depth):
        deep_term = f"S<{deep_term}>"

    code = f"""#![recursion_limit = "{recursion_limit}"]
pub struct S<T>(std::marker::PhantomData<T>);
pub trait Trait {{ type Out; }}
impl Trait for () {{ type Out = (); }}
impl<T: Trait> Trait for S<T> {{
    type Out = S<<T as Trait>::Out>;
}}
pub type Trigger = <{deep_term} as Trait>::Out;
"""
    return code

def generate_clang_deep_templates(depth=40000, template_depth=10000000):
    """
    Generates deeply nested template specializations that trigger Apple Clang's
    stack-guard and induce a frontend crash (SIGILL / Illegal instruction: 4).
    """
    deep_term = "int"
    for _ in range(depth):
        deep_term = f"S<{deep_term}>"

    code = f"""// Project Hydra: Deep Template Specialization Attack
template<typename T> struct S {{}};
template<typename T> struct Eval {{ using type = T; }};
template<typename T> struct Eval<S<T>> {{ using type = S<typename Eval<T>::type>; }};

using Trigger = Eval<{deep_term}>::type;
int main() {{ return 0; }}
"""
    return code

def generate_ts_heap_exhaustion(breadth=800):
    """
    Generates a massive distributive union Cartesian product designed to trigger
    V8 heap allocation failures (exit code 134 / SIGABRT).
    """
    union_parts = " | ".join(f"[{i}]" for i in range(breadth))
    code = f"""// Project Hydra: Distributive Cartesian Product Heap Stress
type U = {union_parts};
type Product<X, Y> = X extends any ? Y extends any ? [X, Y] : never : never;
type Boom = Product<U, U>;
type Force<T extends [any, any]> = T;
type Trigger = Force<Boom>;
"""
    return code

def generate_ts_quaternary_tree(depth=9):
    """
    Generates an exponential quaternary branching tree (4^D concurrent instantiations).
    """
    code = f"""// Project Hydra: Quaternary Branching Tree
export type QuaternaryFreeze<D extends number, P extends readonly unknown[] = []> =
  P["length"] extends D
    ? 1
    : [
        QuaternaryFreeze<D, [0, ...P]>,
        QuaternaryFreeze<D, [1, ...P]>,
        QuaternaryFreeze<D, [2, ...P]>,
        QuaternaryFreeze<D, [3, ...P]>
      ] extends [infer A, infer B, infer C, infer D]
      ? [A, B, C, D]
      : never;

export type Trigger = QuaternaryFreeze<{depth}>;
"""
    return code

# ============================================================================
# Target Execution & Crash Detection
# ============================================================================

def test_rust_target(code, name):
    temp_file = REPO_ROOT / f"temp_hydra_{name}.rs"
    temp_file.write_text(code)

    cmd = ["rustc", "--crate-type=lib", str(temp_file)]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        duration = time.time() - t0
        returncode = proc.returncode
        stderr = proc.stderr
    except subprocess.TimeoutExpired:
        duration = 15.0
        returncode = -999 # Timeout
        stderr = "TIMEOUT: Compilation exceeded 15.0s limit"
    finally:
        temp_file.unlink(missing_ok=True)

    is_crash = (
        returncode in [-10, -11, -6, 134] or
        "SIGBUS" in stderr or
        "internal compiler error" in stderr or
        "stack overflow" in stderr
    )

    return {
        "target": "rustc",
        "test_name": name,
        "returncode": returncode,
        "duration_sec": round(duration, 3),
        "is_crash": is_crash,
        "signal": -returncode if returncode < 0 else None,
        "stderr_snippet": stderr[:400].strip(),
        "code": code
    }

def test_clang_target(code, name, template_depth=10000000):
    temp_file = REPO_ROOT / f"temp_hydra_{name}.cpp"
    temp_file.write_text(code)

    cmd = ["clang++", "-std=c++20", "-fsyntax-only", f"-ftemplate-depth={template_depth}", str(temp_file)]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        duration = time.time() - t0
        returncode = proc.returncode
        stderr = proc.stderr
    except subprocess.TimeoutExpired:
        duration = 15.0
        returncode = -999
        stderr = "TIMEOUT: Compilation exceeded 15.0s limit"
    finally:
        temp_file.unlink(missing_ok=True)

    is_crash = (
        returncode in [-4, -6, -10, -11] or
        "Illegal instruction" in stderr or
        "failed due to signal" in stderr or
        "Segmentation fault" in stderr
    )
    sig = -returncode if returncode < 0 else (4 if "Illegal instruction" in stderr else (11 if "Segmentation fault" in stderr else None))

    return {
        "target": "clang++",
        "test_name": name,
        "returncode": returncode,
        "duration_sec": round(duration, 3),
        "is_crash": is_crash,
        "signal": sig,
        "stderr_snippet": stderr[:400].strip(),
        "code": code
    }

def test_tsc_target(code, name, max_old_space_mb=64):
    temp_file = REPO_ROOT / f"temp_hydra_{name}.ts"
    temp_file.write_text(code)

    cmd = [
        "node",
        f"--max-old-space-size={max_old_space_mb}",
        "./node_modules/typescript/lib/tsc.js",
        "--noEmit",
        "--ignoreConfig",
        "--strict",
        str(temp_file)
    ]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        duration = time.time() - t0
        returncode = proc.returncode
        stderr = proc.stderr
    except subprocess.TimeoutExpired:
        duration = 15.0
        returncode = -999
        stderr = "TIMEOUT: Compilation exceeded 15.0s limit"
    finally:
        temp_file.unlink(missing_ok=True)

    is_crash = (
        returncode in [134, -6] or
        "heap out of memory" in stderr or
        "Maximum call stack size exceeded" in stderr
    )

    return {
        "target": "tsc",
        "test_name": name,
        "returncode": returncode,
        "duration_sec": round(duration, 3),
        "is_crash": is_crash,
        "signal": -returncode if returncode < 0 else (134 if returncode == 134 else None),
        "stderr_snippet": stderr[:400].strip(),
        "code": code
    }

# ============================================================================
# Main Fuzzing Harness
# ============================================================================

def run_hydra_fuzzer():
    ensure_dirs()

    print("================================================================")
    print("Project Chimera: Phase 13 - Project Hydra Automated Fuzzer")
    print("Differential Compiler Stress-Testing & ICE Hunting")
    print("Targets: rustc, clang++ -std=c++20, tsc --noEmit")
    print("================================================================\n")

    test_runs = []
    crashes_found = []

    # 1. Rust Targets
    print(">>> [Target: rustc] Fuzzing nominal trait projection engine...")
    rust_tests = [
        ("rust_shallow_projection", generate_rust_deep_projection(depth=100, recursion_limit=256)),
        ("rust_mid_projection", generate_rust_deep_projection(depth=2000, recursion_limit=10000)),
        ("rust_deep_projection_sigbus", generate_rust_deep_projection(depth=40000, recursion_limit=10000000)),
    ]
    for name, code in rust_tests:
        res = test_rust_target(code, name)
        test_runs.append(res)
        status = "CRASH DETECTED!" if res["is_crash"] else "GRACEFUL / PASS"
        print(f"  - {name:30s} | Exit: {res['returncode']:4d} | Status: {status} | Time: {res['duration_sec']:.2f}s")
        if res["is_crash"]:
            crashes_found.append(res)

    # 2. Clang Targets
    print("\n>>> [Target: clang++] Fuzzing template specialization engine...")
    clang_tests = [
        ("clang_shallow_template", generate_clang_deep_templates(depth=100, template_depth=500)),
        ("clang_mid_template", generate_clang_deep_templates(depth=2000, template_depth=10000)),
        ("clang_deep_template_sigill", generate_clang_deep_templates(depth=40000, template_depth=10000000)),
    ]
    for name, code in clang_tests:
        res = test_clang_target(code, name)
        test_runs.append(res)
        status = "CRASH DETECTED!" if res["is_crash"] else "GRACEFUL / PASS"
        print(f"  - {name:30s} | Exit: {res['returncode']:4d} | Status: {status} | Time: {res['duration_sec']:.2f}s")
        if res["is_crash"]:
            crashes_found.append(res)

    # 3. TypeScript Targets
    print("\n>>> [Target: tsc] Fuzzing V8 type checker and memory limits...")
    ts_tests = [
        ("ts_quaternary_tree_d7", generate_ts_quaternary_tree(depth=7), 128),
        ("ts_quaternary_tree_d9", generate_ts_quaternary_tree(depth=9), 256),
        ("ts_cartesian_product_stress", generate_ts_heap_exhaustion(breadth=350), 64),
    ]
    for name, code, mem_mb in ts_tests:
        res = test_tsc_target(code, name, max_old_space_mb=mem_mb)
        test_runs.append(res)
        status = "CRASH DETECTED!" if res["is_crash"] else "GRACEFUL / PASS"
        print(f"  - {name:30s} | Exit: {res['returncode']:4d} | Status: {status} | Time: {res['duration_sec']:.2f}s")
        if res["is_crash"]:
            crashes_found.append(res)

    # Log Crashes to crashes/ directory
    print(f"\n>>> Total Crashes / Abnormal Aborts Identified: {len(crashes_found)}")
    for crash in crashes_found:
        ext = "rs" if crash["target"] == "rustc" else ("cpp" if crash["target"] == "clang++" else "ts")
        crash_path = CRASHES_DIR / f"{crash['test_name']}.{ext}"
        crash_path.write_text(crash["code"])

        info_path = CRASHES_DIR / f"{crash['test_name']}_info.json"
        info_data = {
            "target": crash["target"],
            "test_name": crash["test_name"],
            "returncode": crash["returncode"],
            "signal": crash["signal"],
            "duration_sec": crash["duration_sec"],
            "stderr_snippet": crash["stderr_snippet"]
        }
        with open(info_path, "w") as f:
            json.dump(info_data, f, indent=2)

        print(f"  [SAVED] {crash_path.name} (Returncode: {crash['returncode']}, Signal: {crash['signal']})")

    # Output aggregated telemetry JSON
    summary = {
        "metadata": {
            "experiment": "Phase 13: Project Hydra Compiler Fuzzing & ICE Hunter",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "targets": ["rustc 1.97.0", "Apple Clang 21.0.0", "TypeScript 7.0.2"]
        },
        "total_tests": len(test_runs),
        "total_crashes": len(crashes_found),
        "crashes": [
            {
                "target": c["target"],
                "test_name": c["test_name"],
                "returncode": c["returncode"],
                "signal": c["signal"],
                "stderr_snippet": c["stderr_snippet"]
            }
            for c in crashes_found
        ],
        "runs": [
            {
                "target": r["target"],
                "test_name": r["test_name"],
                "returncode": r["returncode"],
                "duration_sec": r["duration_sec"],
                "is_crash": r["is_crash"]
            }
            for r in test_runs
        ]
    }

    out_file = DATA_DIR / "phase13_hydra_results.json"
    with open(out_file, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n[OK] Phase 13 Hydra results saved to {out_file}")

if __name__ == "__main__":
    run_hydra_fuzzer()
