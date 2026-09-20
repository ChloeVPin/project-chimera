#!/usr/bin/env python3
"""
Project Chimera: Act V / Phase L5 - Project Hydra on Linux

Port of the Phase 13 cross-compiler adversarial fuzzer to Linux x86_64.
Targets:
  1. rustc 1.97.1   — deep nominal projection (MRE) + parser literal nesting
  2. g++ 11.4       — deep template specialization (NEW: GCC crash surface)
  3. clang++ 14     — same seed as the Darwin SIGILL MRE
  4. tsc 7.0.2      — native Go binary (no V8 heap; OOM profile differs)

Divergence watch: Darwin produced SIGBUS (rustc) and SIGILL (clang).
Linux is expected to produce SIGSEGV for both — a crash-taxonomy divergence
driven by Mach guard-page faults vs. Linux stack-growth faults.

Output: data/phaseL5_linux_hydra_results.json
"""
import json
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from hydra_fuzzer import (  # noqa: E402
    generate_rust_deep_projection,
    generate_clang_deep_templates,
    generate_ts_quaternary_tree,
    generate_ts_heap_exhaustion,
)

CRASHES = REPO_ROOT / "crashes" / "linux"
DATA_DIR = REPO_ROOT / "data"
TIMEOUT_S = 30


def generate_rust_parser_nesting(depth: int) -> str:
    """Deep literal generic nesting — stresses the rustc *parser* stack,
    which is NOT guarded by #![recursion_limit] (that fuse covers trait
    evaluation only)."""
    term = "()"
    for _ in range(depth):
        term = f"S<{term}>"
    return (
        'pub struct S<T>(std::marker::PhantomData<T>);\n'
        f'pub type Trigger = {term};\n'
        'pub fn f() {}\n'
    )


EXT = {"rust": ".rs", "gcc": ".cpp", "clang": ".cpp", "tsc": ".ts"}


def run(target_cmd, name, code, timeout=TIMEOUT_S):
    tmp = REPO_ROOT / "linux" / f"hydra_{name}{EXT[name.split('_')[0]]}"
    tmp.write_text(code)
    t0 = time.time()
    try:
        proc = subprocess.run(target_cmd(tmp), capture_output=True,
                              text=True, timeout=timeout)
        rc, err = proc.returncode, proc.stderr or ""
    except subprocess.TimeoutExpired:
        rc, err = -999, "TIMEOUT"
    elapsed = time.time() - t0
    tmp.unlink(missing_ok=True)
    sig = -rc if rc and rc < 0 else None
    is_crash = bool(
        rc in (-4, -6, -10, -11, 132, 134, 136, 139) or
        "internal compiler error" in err or "stack overflow" in err or
        "Segmentation fault" in err or "Illegal instruction" in err or
        "SIGSEGV" in err or "SIGBUS" in err or "SIGILL" in err
    )
    return {"name": name, "returncode": rc, "signal": sig,
            "duration_s": round(elapsed, 2), "is_crash": is_crash,
            "stderr": err[:600], "code": code}


def rustc_cmd(f):
    return ["rustc", "--crate-type=lib", str(f), "-o", "/tmp/hydra_out.rlib"]

def gpp_cmd(f):
    return ["g++", "-std=c++20", "-fsyntax-only", "-ftemplate-depth=1000000", str(f)]

def clang_cmd(f):
    return ["clang++", "-std=c++20", "-fsyntax-only", "-ftemplate-depth=1000000", str(f)]

def tsc_cmd(f):
    return ["npx", "tsc", "--noEmit", "--ignoreConfig", "--strict", str(f)]


def main():
    CRASHES.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(exist_ok=True)
    runs = []

    cases = [
        # --- rustc: trait-solver stack exhaustion (same MRE as Darwin) ---
        ("rust_sigbus_mre",  rustc_cmd, generate_rust_deep_projection(40000)),
        # --- rustc: parser literal nesting (new Linux surface) ---
        ("rust_parser_nest_5k",  rustc_cmd, generate_rust_parser_nesting(5000)),
        ("rust_parser_nest_20k", rustc_cmd, generate_rust_parser_nesting(20000)),
        ("rust_parser_nest_50k", rustc_cmd, generate_rust_parser_nesting(50000)),
        # --- g++: deep template eval (GCC is NEW to the triad) ---
        # ForceEval forces instantiation — lazy alias alone is a no-op
        ("gcc_deep_template_40k", gpp_cmd,
         generate_clang_deep_templates(40000) + "\nstruct ForceEval : Trigger {};\nForceEval force_eval_inst;\n"),
        # --- clang++: same seed that SIGILL'd Apple Clang on Darwin ---
        ("clang_deep_template_40k", clang_cmd,
         generate_clang_deep_templates(40000) + "\nstruct ForceEval : Trigger {};\nForceEval force_eval_inst;\n"),
        # --- tsc native binary ---
        ("tsc_quat_d9",  tsc_cmd, generate_ts_quaternary_tree(9)),
        ("tsc_heap_350", tsc_cmd, generate_ts_heap_exhaustion(350)),
    ]

    print(f"{'case':<26} {'rc':>5} {'sig':>4} {'crash':>6} {'time_s':>7}")
    for name, mkcmd, code in cases:
        r = run(mkcmd, name, code)
        runs.append({k: v for k, v in r.items() if k != "code"})
        print(f"{name:<26} {r['returncode']:>5} {r['signal'] or '-':>4} "
              f"{'CRASH' if r['is_crash'] else '-':>6} {r['duration_s']:>7.2f}",
              flush=True)
        if r["is_crash"]:
            ext = {"rust": "rs"}.get(name.split("_")[0],
                                     "cpp" if "clang" in name or "gcc" in name else "ts")
            (CRASHES / f"{name}.{ext}").write_text(r["code"])
            (CRASHES / f"{name}_info.json").write_text(json.dumps(
                {k: v for k, v in r.items() if k != "code"}, indent=2))

    out = DATA_DIR / "phaseL5_linux_hydra_results.json"
    out.write_text(json.dumps({
        "phase": "L5", "platform": "linux-x86_64",
        "targets": ["rustc 1.97.1", "g++ 11.4", "clang++ 14", "tsc 7.0.2-native"],
        "runs": runs,
    }, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
