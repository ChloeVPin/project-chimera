#!/usr/bin/env python3
"""Act XIII-A — The Mutant Compiler.
Controlled causation experiment: tsgo built twice from the same commit —
stock vs a mutant with fuse constants surgically shifted
(checker.go: instantiationDepth 100->500, instantiationCount 5M->20M,
tailCount 1000->5000). For each fuse probe, the mutant's failure point
must move to the *predicted* multiple of the stock wall:
  depth fuse:   stock trips at N=48   -> mutant at ~240
  fuel fuse:    stock trips at N=1000 -> mutant at ~5000
  count fuse:   stock trips ~5.03M    -> mutant at ~20.1M
If the walls move exactly where the mutated constants predict, the fuse
architecture is proven causal — not correlation.
"""
import json, os, subprocess, sys, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBES = os.path.join(ROOT, 'linux', 'probes')
STOCK  = os.path.expanduser('~/tools/tsgo-stock')
MUTANT = os.path.expanduser('~/tools/tsgo-mutant')

HDR = ('import { EvolveTCO, EvolveStrictNonTCO } from "../../src/type_engine/rule110";\n'
       'import { EvolvePow2 } from "../../src/type_engine/log_rule110";\n'
       'import { Bit } from "../../src/type_engine/cells";\n'
       'type Tape8 = [0, 1, 1, 0, 1, 1, 1, 0];\n')

def write_probe(name, body):
    p = os.path.join(PROBES, f'MUTANT_{name}.ts')
    open(p, 'w').write(HDR + body + '\nexport type { _Probe };\n')
    return p

def probe_nontco(n):   return write_probe(f'NONT_{n}', f'type _Probe = EvolveStrictNonTCO<Tape8, {n}>;')
def probe_tco(n):      return write_probe(f'TCO_{n}',  f'type _Probe = EvolveTCO<Tape8, {n}>;')
def probe_freeze(n):   return write_probe(f'FREEZE_{n}',"""type QuaternaryFreeze<Depth extends number, Path extends readonly unknown[] = []> =
  Path['length'] extends Depth ? 1 :
  [QuaternaryFreeze<Depth, [0, ...Path]>, QuaternaryFreeze<Depth, [1, ...Path]>,
   QuaternaryFreeze<Depth, [2, ...Path]>, QuaternaryFreeze<Depth, [3, ...Path]>] extends [infer A, infer B, infer C, infer D] ? [A, B, C, D] : never;
type _Probe = QuaternaryFreeze<%d>;""" % n)

def run(compiler, path, timeout=180):
    t = time.time()
    try:
        r = subprocess.run([compiler, '--noEmit', '--ignoreConfig', '--extendedDiagnostics', path],
                           capture_output=True, text=True, timeout=timeout)
        out = r.stderr + r.stdout
        inst = None
        for line in out.splitlines():
            if line.startswith('Instantiations:'):
                inst = int(line.split(':')[1].strip().replace(',', ''))
        trips = []
        if 'TS2589' in out: trips.append('TS2589')
        if 'TS2321' in out: trips.append('TS2321')
        return {'class': 'trip' if trips else ('error' if 'error TS' in out else 'ok'),
                'errors': trips, 'inst': inst, 's': round(time.time() - t, 2)}
    except subprocess.TimeoutExpired:
        return {'class': 'timeout', 's': timeout}

def bisect_trip(compiler, gen, lo, hi):
    """lo passes, hi trips. Find the first tripping N."""
    while hi - lo > 1:
        mid = (lo + hi) // 2
        c = run(compiler, gen(mid))['class']
        if c == 'ok': lo = mid
        else: hi = mid
    return lo, hi

def main():
    res = {'stock_binary': STOCK, 'mutant_binary': MUTANT,
           'mutations': {'instantiationDepth': '100->500',
                         'instantiationCount': '5_000_000->20_000_000',
                         'tailCount': '1000->5000'},
           'predictions': {}, 'measurements': {}}

    # --- Fuel fuse: stock trips at 1000, mutant predicted ~5000 ---
    res['predictions']['tco'] = 'mutant trips at 4999-5001 (5x stock 999/1000)'
    res['measurements']['tco_stock_999']  = run(STOCK,  probe_tco(999))
    res['measurements']['tco_stock_1000'] = run(STOCK,  probe_tco(1000))
    res['measurements']['tco_mutant_1000']= run(MUTANT, probe_tco(1000))
    res['measurements']['tco_mutant_4999']= run(MUTANT, probe_tco(4999))
    res['measurements']['tco_mutant_5000']= run(MUTANT, probe_tco(5000))
    if res['measurements']['tco_mutant_5000']['class'] == 'ok':
        l, h = bisect_trip(MUTANT, probe_tco, 5000, 8000)
        res['measurements']['tco_mutant_trip'] = [l, h]
    print('tco done', flush=True)

    # --- Depth fuse: stock trips at 48, mutant predicted ~240 ---
    res['predictions']['nontco'] = 'mutant trips at ~240 (5x stock 48)'
    res['measurements']['nontco_stock_47']  = run(STOCK,  probe_nontco(47))
    res['measurements']['nontco_stock_48']  = run(STOCK,  probe_nontco(48))
    res['measurements']['nontco_mutant_48'] = run(MUTANT, probe_nontco(48))
    res['measurements']['nontco_mutant_239']= run(MUTANT, probe_nontco(239))
    res['measurements']['nontco_mutant_240']= run(MUTANT, probe_nontco(240))
    res['measurements']['nontco_mutant_241']= run(MUTANT, probe_nontco(241))
    if res['measurements']['nontco_mutant_241']['class'] == 'ok':
        l, h = bisect_trip(MUTANT, probe_nontco, 241, 400)
        res['measurements']['nontco_mutant_trip'] = [l, h]
    print('nontco done', flush=True)

    # --- Count fuse: QuaternaryFreeze hits ~5.03M inst on stock; mutant -> ~20.03M ---
    res['predictions']['count'] = 'FREEZE_10 stock trips at ~5.03M inst; mutant trips at ~20.03M (4x)'
    res['measurements']['freeze_stock_10']  = run(STOCK,  probe_freeze(10))
    res['measurements']['freeze_mutant_10'] = run(MUTANT, probe_freeze(10), timeout=600)
    res['measurements']['freeze_stock_12']  = run(STOCK,  probe_freeze(12))
    res['measurements']['freeze_mutant_12'] = run(MUTANT, probe_freeze(12), timeout=600)
    print('count done', flush=True)

    out = os.path.join(ROOT, 'data', 'phaseXIII_mutant.json')
    json.dump({'act': 'XIII-A', 'results': res}, open(out, 'w'), indent=1)
    print(json.dumps(res, indent=1)[:4000])

if __name__ == '__main__':
    main()
