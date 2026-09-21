#!/usr/bin/env python3
"""
Project Chimera — Act XI: crash-wall survival curves.

Each compiler's deep-recursion wall was established as a *point estimate* in
Act VI/VII. This phase treats compilation as a reliability problem: at a fixed
depth near the wall, repeatedly compile the SAME file and measure the survival
probability p(depth) = P(clean compile). A physical stack limit randomized by
ASLR predicts a smooth 0->1 transition band; a software fuse predicts a step
function.

Control arm: `setarch -R` disables ASLR (personality ADDR_NO_RANDOMIZE). If the
transition band collapses to a deterministic boundary under -R, the stochasticity
is address-layout causation, not implementation nondeterminism.

Output: ../data/phaseXI_survival.json
"""

import json
import subprocess
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
TMP_DIR = REPO_ROOT / "linux" / "probes" / "survival"
ARCH = subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip()

TRIALS = 12          # compiles per (compiler, depth, aslr_mode)
CPP_TIMEOUT = 60
RUST_TIMEOUT = 90

def gen_cpp(depth: int) -> str:
    s = "int"
    for _ in range(depth):
        s = f"S<{s}>"
    return (
        "template<typename T> struct S {};\n"
        "template<typename T> struct Eval { using type = T; };\n"
        "template<typename T> struct Eval<S<T>> { using type = S<typename Eval<T>::type>; };\n"
        f"using Trigger = typename Eval<{s}>::type;\n"
        "int main() { return 0; }\n"
    )

def gen_rust(depth: int) -> str:
    s = "()"
    for _ in range(depth):
        s = f"S<{s}>"
    return (
        "pub struct S<T>(std::marker::PhantomData<T>);\n"
        f"pub type Trigger = {s};\n"
        "fn main() {}\n"
    )

def compile_once(cmd, timeout):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, (p.stderr or "")[:500]
    except subprocess.TimeoutExpired:
        return "timeout", ""

def classify(rc, stderr: str) -> str:
    """Drivers mask child signals: g++ returns rc=4 on cc1plus SIGSEGV, so
    classify on the stderr text as well as the raw returncode."""
    if rc == 0:
        return "ok"
    if rc == "timeout":
        return "timeout"
    crash_marks = ("Segmentation fault", "SIGSEGV", "SIGBUS", "SIGILL",
                   "Illegal instruction", "internal compiler error: Segmentation")
    if (isinstance(rc, int) and rc < 0) or any(m in stderr for m in crash_marks):
        return "crash"
    return "diagnostic"   # graceful error (fuse/diagnostic), no crash

def sweep(name, gen, cmd_fn, depths, trials, aslr_off):
    """aslr_off: wrap cmd in setarch -R."""
    rows = []
    for d in depths:
        src = TMP_DIR / f"xi_{name}_{d}.{'rs' if name=='rustc' else 'cpp'}"
        src.write_text(gen(d))
        cmd = cmd_fn(src)
        if aslr_off:
            cmd = ["setarch", "-R"] + cmd
        counts = {"ok": 0, "crash": 0, "diagnostic": 0, "timeout": 0}
        for _ in range(trials):
            rc, err = compile_once(cmd, CPP_TIMEOUT if name != "rustc" else RUST_TIMEOUT)
            counts[classify(rc, err)] += 1
        row = {
            "compiler": name, "depth": d, "trials": trials,
            "aslr_off": aslr_off, **counts,
            "survival": round(counts["ok"] / trials, 3),
        }
        rows.append(row)
        print(f"  {name} d={d} aslr_off={aslr_off} -> {counts}", flush=True)
        src.unlink(missing_ok=True)
    return rows

FINE_SPECS = [
    # unit-resolution bands bracketing the coarse transitions found above
    ("g++", gen_cpp,
     lambda f: ["g++", "-std=c++20", "-fsyntax-only", "-ftemplate-depth=200000", str(f)],
     list(range(41520, 41542, 2))),              # the ~41,520-41,540 band
    ("clang++", gen_cpp,
     lambda f: ["clang++", "-std=c++20", "-fsyntax-only", "-ftemplate-depth=200000", str(f)],
     list(range(1250, 1280, 5))),                # the 1,250-1,275 band
    ("rustc", gen_rust,
     lambda f: ["rustc", "--crate-type=lib", "--edition=2021", str(f)],
     list(range(4100, 4145, 5))),                # the 4,100-4,140 band
]

def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    fine_only = "--fine" in __import__("sys").argv
    trials = 20 if fine_only else TRIALS

    specs = FINE_SPECS if fine_only else [
        # known walls from Act VI/VII on this box
        ("g++", gen_cpp,
         lambda f: ["g++", "-std=c++20", "-fsyntax-only", "-ftemplate-depth=200000", str(f)],
         list(range(41380, 41700, 20))),          # 41,380..41,680
        ("clang++", gen_cpp,
         lambda f: ["clang++", "-std=c++20", "-fsyntax-only", "-ftemplate-depth=200000", str(f)],
         list(range(1150, 1450, 25))),           # ~1,150..1,425
        ("rustc", gen_rust,
         lambda f: ["rustc", "--crate-type=lib", "--edition=2021", str(f)],
         list(range(3900, 4400, 40))),           # ~3,900..4,380
    ]

    out = {
        "act": "XI",
        "mode": "fine" if fine_only else "coarse",
        "arch": ARCH,
        "kernel_randomize_va_space": Path("/proc/sys/kernel/randomize_va_space").read_text().strip(),
        "trials_per_point": trials,
        "started": t0,
        "aslr_on": [],
        "aslr_off": [],
        "notes": [],
    }

    for mode_flag, bucket in [(False, "aslr_on"), (True, "aslr_off")]:
        for name, gen, cmd_fn, depths in specs:
            print(f"[{bucket}] {name} sweep {depths[0]}..{depths[-1]}", flush=True)
            out[bucket].extend(sweep(name, gen, cmd_fn, depths, trials, mode_flag))

    out["elapsed_s"] = round(time.time() - t0, 1)
    fname = "phaseXI_survival_fine.json" if fine_only else "phaseXI_survival.json"
    (DATA_DIR / fname).write_text(json.dumps(out, indent=1))
    print(f"\nWrote data/{fname} in {out['elapsed_s']}s")

if __name__ == "__main__":
    main()
