#!/usr/bin/env python3
"""Act XVI-B — the price of correctness + the tuple-cap boundary.

Part 1: tsgo-fixed (nest fuse moved 100 -> 1000, single-line patch to
internal/checker/relater.go) vs tsgo-stock vs tsgo-unfused on mismatched
Array^N probes. Answer: stock lies silently at every depth >= 101;
tsgo-fixed errors through 1000 and lies from 1001 (the hole just moves);
tsgo-unfused errors everywhere, costing ~1.96s at depth 2000 vs ~0.29s
for the dishonest compilers — the honest price is ~7x but sub-second.
The brake saves nothing a user could feel; it exists to bound pathology,
and it silently trades correctness for it.

Part 2: the TS2799 tuple cap. Found at internal/checker/checker.go:23493 —
`if len(spreadTypes)+len(n.types) >= 10_000` inside newTupleNormalizer.
Measured boundary: 9999 elements clean, 10000+ errors LOUDLY. Unlike the
relater fuse, this wall reports honestly.
"""
import json, os, subprocess, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def deep_mismatch(n):
    l, r = 'number', 'string'
    for _ in range(n):
        l, r = f'Array<{l}>', f'Array<{r}>'
    return f'declare const src: {r};\nconst x: {l} = src;\n'

def tup_probe(n):
    half, rest = n // 2, n - n // 2
    a, b = ','.join(['0'] * half), ','.join(['0'] * rest)
    return f'type A = [{a}];\ntype B = [{b}];\ntype T = [...A, ...B];\n'

def run(binary, path):
    t = time.time()
    r = subprocess.run([binary, '--noEmit', '--ignoreConfig', path],
                       capture_output=True, text=True, timeout=180)
    out = r.stderr + r.stdout
    cls = 'error' if 'error TS' in out else ('clean' if r.returncode == 0 else 'other')
    return cls, round(time.time() - t, 3)

def main():
    bins = {k: os.path.expanduser(f'~/tools/tsgo-{k}')
            for k in ('stock', 'fixed', 'unfused')}
    part1 = {}
    for n in (101, 500, 999, 1000, 1001, 2000):
        fp = f'/tmp/pc_{n}.ts'
        open(fp, 'w').write(deep_mismatch(n))
        part1[n] = {}
        for name, binary in bins.items():
            cls, dt = run(binary, fp)
            part1[n][name] = {'class': cls, 'seconds': dt}
            print(f'd={n} {name}: {cls} ({dt}s)', flush=True)
    part2 = {}
    for n in (9998, 9999, 10000, 10001):
        fp = f'/tmp/tup_{n}.ts'
        open(fp, 'w').write(tup_probe(n))
        cls, dt = run(bins['stock'], fp)
        part2[n] = {'class': cls, 'seconds': dt}
        print(f'tuple n={n}: {cls} ({dt}s)', flush=True)
    out = os.path.join(ROOT, 'data', 'phaseXVI_price_of_correctness.json')
    json.dump({'act': 'XVI-B/C', 'depth_mismatch': part1, 'tuple_boundary': part2,
               'tuple_cap_location': 'internal/checker/checker.go:23493 (>= 10_000, LOUD error TS2799)'},
              open(out, 'w'), indent=1)
    print('wrote', out)

if __name__ == '__main__':
    main()
