#!/usr/bin/env python3
"""
Project Chimera — Act XII-B: The Chimera Transpiler.

Mechanical statement-fan-out transform (the Act IX bypass, productized):
given any iterative type-level function `F<X>` expressed as a TypeScript type
alias, emit a chain of statements `Ti = F<Ti-1>` such that each step's work
lands in its own instantiation window. Depth/fuel/5M-count fuses never engage.

Usage:
  python3 linux/chimera_transpile.py \
      --import ../../src/type_engine/rule110 \
      --fn StepZeroPadded \
      --init '[0,1,1,0,1,1,1,0]' \
      --steps 50000 \
      --verify-fn eval_tape        # optional: python oracle module.func(w)->w'
      --verify-every 1             # emit `const _cI: TI = <oracle>` every k steps
      --out linux/probes/MY_CHAIN.ts

With --verify-fn, the transpiler imports your python oracle (module path or
file) — func(state)->state' — computes ground truth per step, and emits
assignability assertions so `tsc --noEmit` *proves* the chain is correct.

Without --verify-fn it emits a final-step check only if --expect is given
(a literal type expression), else the chain alone (still exercises the work).
"""

import argparse
import importlib
import importlib.util
import json
import sys
from pathlib import Path


def load_oracle(spec):
    """spec = 'module:function' or '/path/file.py:function'"""
    target, func = spec.rsplit(":", 1)
    if target.endswith(".py") or "/" in target:
        p = Path(target).resolve()
        m = importlib.util.spec_from_file_location(p.stem, p)
        mod = importlib.util.module_from_spec(m)
        m.loader.exec_module(mod)
    else:
        mod = importlib.import_module(target)
    return getattr(mod, func)


def emit(fn, init, steps, import_path, oracle=None, verify_every=0, expect=None):
    lines = [f"import {{ {fn} }} from '{import_path}';",
             f"type T0 = {init};"]
    state = None
    if oracle:
        state = json.loads(init)
    for i in range(1, steps + 1):
        lines.append(f"type T{i} = {fn}<T{i-1}>;")
        if oracle:
            state = oracle(state)
            if verify_every and i % verify_every == 0:
                lines.append(f"const _c{i}: T{i} = {json.dumps(state)};")
    if oracle:
        lines.append(f"const _end: T{steps} = {json.dumps(state)};")
    elif expect is not None:
        lines.append(f"const _end: T{steps} = {expect};")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Chimera statement-fan-out transpiler")
    ap.add_argument("--import", dest="imp", required=True)
    ap.add_argument("--fn", required=True, help="step type alias name F<X>")
    ap.add_argument("--init", required=True, help="initial type expression (JSON literal)")
    ap.add_argument("--steps", type=int, required=True)
    ap.add_argument("--verify-fn", help="python oracle: module:func or /path.py:func")
    ap.add_argument("--verify-every", type=int, default=0)
    ap.add_argument("--expect", help="expected final type expression literal")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    oracle = load_oracle(a.verify_fn) if a.verify_fn else None
    src = emit(a.fn, a.init, a.steps, a.imp, oracle, a.verify_every, a.expect)
    Path(a.out).write_text(src)
    print(f"wrote {a.out} ({len(src)} bytes, {a.steps} steps"
          f"{', verified every ' + str(a.verify_every) if oracle and a.verify_every else ''})")


if __name__ == "__main__":
    main()
