#!/usr/bin/env python3
"""
Project Chimera: Act V / Phase L1 - Linux Fuse Hierarchy Probe Runner

Each case is a STANDALONE .ts file: only the engine types it needs are
imported, and exactly one heavy type is instantiated. This isolates each
fuse (depth / fuel / heap) so a single run measures one circuit breaker.

Mirrors src/benchmarks/harness.ts methodology (one process per case).

Output: data/phaseL1_linux_fuse_results.json
"""
import json
import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

HEADER = (
    'import { EvolveTCO, EvolveStrictNonTCO } '
    'from "../../src/type_engine/rule110";\n'
    'import { EvolvePow2 } from "../../src/type_engine/log_rule110";\n'
    'import { Bit } from "../../src/type_engine/cells";\n'
    "type Tape8 = [0, 1, 1, 0, 1, 1, 1, 0];\n"
)

FREEZE_DEF = """
type QuaternaryFreeze<Depth extends number, Path extends readonly unknown[] = []> =
  Path['length'] extends Depth ? 1 :
  [QuaternaryFreeze<Depth, [0, ...Path]>, QuaternaryFreeze<Depth, [1, ...Path]>,
   QuaternaryFreeze<Depth, [2, ...Path]>, QuaternaryFreeze<Depth, [3, ...Path]>] extends [infer A, infer B, infer C, infer D] ? [A, B, C, D] : never;
"""

# (name, extra_defs, probe_type) — standalone file per case.
CASES = [
    ("TCO_999",     "", "EvolveTCO<Tape8, 999>"),
    ("TCO_1000",    "", "EvolveTCO<Tape8, 1000>"),
    ("TCO_1500",    "", "EvolveTCO<Tape8, 1500>"),
    ("NONTCO_30",   "", "EvolveStrictNonTCO<Tape8, 30>"),
    ("NONTCO_44",   "", "EvolveStrictNonTCO<Tape8, 44>"),
    ("NONTCO_45",   "", "EvolveStrictNonTCO<Tape8, 45>"),
    ("NONTCO_46",   "", "EvolveStrictNonTCO<Tape8, 46>"),
    ("NONTCO_47",   "", "EvolveStrictNonTCO<Tape8, 47>"),
    ("NONTCO_48",   "", "EvolveStrictNonTCO<Tape8, 48>"),
    ("NONTCO_49",   "", "EvolveStrictNonTCO<Tape8, 49>"),
    ("NONTCO_60",   "", "EvolveStrictNonTCO<Tape8, 60>"),
    ("TRAMP_1024",  "", "EvolvePow2<Tape8, 10>"),
    ("TRAMP_65536", "", "EvolvePow2<Tape8, 16>"),
    ("TRAMP_131072","", "EvolvePow2<Tape8, 17>"),
    ("FREEZE_7",  FREEZE_DEF, "QuaternaryFreeze<7>"),
    ("FREEZE_8",  FREEZE_DEF, "QuaternaryFreeze<8>"),
    ("FREEZE_9",  FREEZE_DEF, "QuaternaryFreeze<9>"),
    ("FREEZE_10", FREEZE_DEF, "QuaternaryFreeze<10>"),
    ("FREEZE_11", FREEZE_DEF, "QuaternaryFreeze<11>"),
    ("FREEZE_12", FREEZE_DEF, "QuaternaryFreeze<12>"),
]

FIELD_PATTERNS = {
    "instantiations": r"Instantiations:\s+(\d+)",
    "types": r"Types:\s+(\d+)",
    "memory_kb": r"Memory used:\s+(\d+)K",
    "check_time_s": r"Check time:\s+([\d.]+)s",
    "total_time_s": r"Total time:\s+([\d.]+)s",
}


def run_case(name: str, extra: str, probe: str, timeout_s: int = 600) -> dict:
    src = HEADER + extra + f"type _Probe = {probe};\nexport type {{ _Probe }};\n"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".ts", dir=REPO_ROOT / "linux" / "probes", delete=False
    ) as f:
        f.write(src)
        path = f.name
    start = time.time()
    try:
        proc = subprocess.run(
            ["npx", "tsc", "--noEmit", "--extendedDiagnostics",
             "--ignoreConfig", "--strict", path],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=timeout_s,
        )
        out = proc.stdout + proc.stderr
        exit_code = proc.returncode
        signal = None
    except subprocess.TimeoutExpired:
        out, exit_code, signal = "", -1, "TIMEOUT"
    finally:
        elapsed_ms = (time.time() - start) * 1000
        os.unlink(path)

    errors = sorted(set(re.findall(r"error (TS\d+)", out)))
    fields = {k: float(m.group(1)) if (m := re.search(p, out)) else None
              for k, p in FIELD_PATTERNS.items()}
    return {"case": name, "probe": probe, "exit_code": exit_code,
            "signal": signal, "ts_errors": errors,
            "wall_ms": round(elapsed_ms, 1), **fields}


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    results = []
    print(f"{'case':<14} {'exit':>5} {'errors':<12} {'wall_ms':>10} "
          f"{'instantiations':>14} {'mem_MB':>8} {'check_s':>8}")
    for name, extra, probe in CASES:
        r = run_case(name, extra, probe)
        results.append(r)
        mem_mb = (r["memory_kb"] or 0) / 1024
        print(f"{name:<14} {r['exit_code']:>5} "
              f"{','.join(r['ts_errors']) or '-':<12} {r['wall_ms']:>10.0f} "
              f"{r['instantiations'] or 0:>14.0f} {mem_mb:>8.0f} "
              f"{r['check_time_s'] or 0:>8.1f}", flush=True)

    out_path = DATA_DIR / "phaseL1_linux_fuse_results.json"
    out_path.write_text(json.dumps({
        "phase": "L1",
        "platform": "linux-x86_64",
        "compiler": "typescript 7.0.2 (native)",
        "results": results,
    }, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
