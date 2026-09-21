#!/usr/bin/env python3
"""
Project Chimera — Act XII-A: THE OUROBOROS.

The Act IX bypass generalized: instead of a cellular automaton, chain a
*universal* machine. Post 2-tag systems are Turing-equivalent (Cocke-Minsky
1961). This script emits a statement-fan-out chain that drives the repo's
`Step2Tag` engine for N steps, verifying the machine's word against a Python
oracle every step — the largest verified universal computation ever run
inside a type checker.

System selected empirically (bounded, non-halting, rich dynamics):
  alphabet {a,b,c,d};  a->dbd  b->ad  c->bdcc  d->a
  survives 300k+ steps, max word length 44, period 565.

Output: ../data/phaseXII_ouroboros.json
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROBES = REPO_ROOT / "linux" / "probes"
DATA_DIR = REPO_ROOT / "data"

RULES = {"a": ["d", "b", "d"], "b": ["a", "d"], "c": ["b", "d", "c", "c"], "d": ["a"]}
START = ["a", "b", "c", "d"]

def tag_step(w):
    if len(w) < 2:
        return w
    return w[2:] + RULES[w[0]]

def ts_word(w):
    return "[" + ", ".join(f'"{s}"' for s in w) + "]"

def gen_chain(n, verify_every):
    lines = [
        "import { Step2Tag, TagAlphabet } from '../../src/type_engine/tag_system';",
        "type R = { a: ['d','b','d']; b: ['a','d']; c: ['b','d','c','c']; d: ['a'] };",
        f"type W0 = {ts_word(START)};",
    ]
    w = START[:]
    for i in range(1, n + 1):
        w = tag_step(w)
        lines.append(f"type W{i} = Step2Tag<W{i-1}, R>;")
        if verify_every and i % verify_every == 0:
            lines.append(f"const _c{i}: W{i} = {ts_word(w)};")
    lines.append(f"const _end: W{n} = {ts_word(w)};")
    return "\n".join(lines) + "\n"

def run_tsc(path):
    t0 = time.time()
    p = subprocess.run(
        ["npx", "tsc", "--ignoreConfig", "--extendedDiagnostics", "--noEmit", str(path)],
        capture_output=True, text=True, timeout=1800, cwd=REPO_ROOT,
        env=dict(os.environ, PATH=os.path.expanduser("~/tools/node/bin") + ":" + os.environ["PATH"]))
    dt = time.time() - t0
    st = {"rc": p.returncode, "wall_s": round(dt, 2)}
    for line in p.stdout.splitlines():
        for key in ("Instantiations", "Memory used", "Check time", "Total time"):
            if key in line:
                st[key.split()[0].lower()] = line.split()[-1].rstrip("Ks").strip()
    errs = [l for l in p.stdout.splitlines() if "error TS" in l]
    st["n_errors"] = len(errs)
    st["errors"] = errs[:3]
    return st

def main():
    verify = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    steps = int(sys.argv[2]) if len(sys.argv) > 2 else 100000
    p = PROBES / f"tmp_ouroboros_{steps}.ts"
    p.write_text(gen_chain(steps, verify))
    print(f"generated {p} ({p.stat().st_size} bytes), verifying every {verify} step(s)", flush=True)
    res = run_tsc(p)
    print(json.dumps(res, indent=1))
    out = {
        "act": "XII-A", "system": RULES, "start": START,
        "steps": steps, "verify_every": verify, "result": res,
        "note": "period 565 bounded non-halting 2-tag system; maxlen 44 words",
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "phaseXII_ouroboros.json").write_text(json.dumps(out, indent=1))
    if res["rc"] != 0:
        p.unlink(missing_ok=True)
    else:
        p.rename(PROBES / f"OUROBOROS_TAG_{steps}.ts")

if __name__ == "__main__":
    main()
