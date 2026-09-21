#!/usr/bin/env python3
"""Act XV — The Silent-Accept Hunter.

Differential fuzzer: generates deep/mismatched type programs and runs each on
THREE compilers — tsgo-stock, tsgo-unfused, tsc5 — classifying each verdict and
cataloging every divergence.

The stock tsgo relater nest fuse (relater.go:3133: sourceStack/targetStack==100
→ TernaryMaybe) silently swallows assignability failures: mismatched deep types
compile with rc=0 and zero diagnostics. This script maps how wide that hole is:
which container types, mismatch positions, and depths produce silent accepts.

Classification per compiler:
  stock/unfused: ok | error | silent-accept (rc=0 on a program that should error)
               | fuse! | go-panic | oom | timeout
  tsc5:          ok | error (TS2321 fuse reported loudly counts as 'fuse-reported')

A case is a SILENT-ACCEPT finding when stock returns rc=0 with no diagnostics
while unfused or tsc5 reports a genuine error.
"""
import json, os, resource, subprocess, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBES = os.path.join(ROOT, 'linux', 'probes')
STOCK   = os.path.expanduser('~/tools/tsgo-stock')
UNFUSED = os.path.expanduser('~/tools/tsgo-unfused')
TSC5    = '/home/ubuntu/d1/ts5/node_modules/typescript/bin/tsc'
NODE    = os.path.expanduser('~/tools/node/bin/node')

AS_CAP = 12 * 1024**3
def _cap():
    resource.setrlimit(resource.RLIMIT_AS, (AS_CAP, AS_CAP))

# ---------- probe generators -------------------------------------------------
# Every probe: declare src of type R; const x: L = src;  (assignability check)
# wrap() builds the nesting; 'l'/'r' differ only where the mismatch is injected.

def chain(n, wrapper_l, wrapper_r, leaf_l='number', leaf_r='string'):
    l, r = leaf_l, leaf_r
    for _ in range(n):
        l, r = wrapper_l(l), wrapper_r(r)
    return l, r

def W(t):            # wrapper factory: lambda param 'X' filled per level
    return lambda s: t.replace('X', s)

CONTAINERS = {
    'array':    (W('Array<X>'), W('Array<X>')),
    'promise':  (W('Promise<X>'), W('Promise<X>')),
    'tuple':    (W('[X, 0]'),   W('[X, 0]')),
    'record':   (W('{v: X}'),   W('{v: X}')),
    'box':      (W('Box<X>'),   W('Box<X>')),
    'fn-arg':   (W('(x: X) => void'), W('(x: X) => void')),   # contravariant
    'readonly': (W('readonly X[]'),   W('readonly X[]')),
    'union':    (W('X | null'), W('X | null')),
}
HDR_BOX = 'interface Box<T> { v: T }\n'

def probe_bottom(container, n):
    """Mismatch only at the deepest leaf."""
    wl, wr = CONTAINERS[container]
    l, r = chain(n, wl, wr)
    return f'{HDR_BOX}declare const src: {r};\nconst x: {l} = src;\n'

def probe_mid(container, n):
    """Mismatch at mid-depth from the top; an identical deep subtree below it.
    `{v: …; extra: 1}` vs `{v: …}` sits mid-way down; the shared `v` subtree
    continues to depth n — tests whether the fuse also swallows mid-tree errors
    and whether it descends into the identical deep subtree afterward."""
    wl, wr = CONTAINERS[container]
    mid = n // 2
    inner = 'number'
    for _ in range(n - mid):
        inner = f'{{v: {inner}}}'
    l, r = f'{{v: {inner}; extra: 1}}', f'{{v: {inner}}}'
    for _ in range(mid):
        l, r = wl(l), wr(r)
    return f'{HDR_BOX}declare const src: {r};\nconst x: {l} = src;\n'

def probe_prop(container, n):
    """Record leaf: missing property at depth."""
    wl, wr = CONTAINERS[container]
    l, r = '{a: number; extra: 1}', '{a: number}'
    for _ in range(n):
        l, r = wl(l), wr(r)
    return f'{HDR_BOX}declare const src: {r};\nconst x: {l} = src;\n'

def probe_tuple_len(n):
    """Deep tuple arity mismatch: [T,...] lengths differ at the bottom."""
    l = 'number'; r = 'number'
    for _ in range(n):
        l = f'[{l}]'; r = f'[{r}]'
    l = f'[{l}, 0]'; r = f'[{r}]'          # arity differs at innermost level
    for _ in range(40):                     # wrap more so total depth > 100
        l = f'[{l}]'; r = f'[{r}]'
    return f'declare const src: {r};\nconst x: {l} = src;\n'

def probe_mutual(n):
    """Two mutually recursive deep interfaces that differ at depth n."""
    lines = ['interface A { next: B; leaf: number }',
             'interface B { next: A; leaf: number }',
             'interface C { next: D; leaf: number }',
             'interface D { next: C; leaf: string }',
             'declare const src: C;', 'const x: A = src;', '']
    return '\n'.join(lines)

def probe_ok(container, n):
    """Identical deep types — control (should always pass)."""
    wl, _ = CONTAINERS[container]
    s = 'number'
    for _ in range(n):
        s = wl(s)
    return f'{HDR_BOX}declare const src: {s};\nconst x: {s} = src;\n'

# ---------- runner -----------------------------------------------------------

def run_go(binary, path, timeout=120):
    t = time.time()
    try:
        r = subprocess.run([binary, '--noEmit', '--ignoreConfig', path],
                           capture_output=True, text=True, timeout=timeout,
                           env=dict(os.environ, GOMEMLIMIT='8GiB'), preexec_fn=_cap)
        out = r.stderr + r.stdout
        cls = 'ok'
        if r.returncode < 0 or (r.returncode != 0 and not out.strip()):
            cls = 'oom'
        elif 'goroutine stack exceeds' in out: cls = 'go-stack-panic'
        elif 'panic:' in out or 'fatal error' in out: cls = 'go-panic'
        elif 'TS2589' in out or 'TS2321' in out: cls = 'fuse!'
        elif 'error TS' in out: cls = 'error'
        elif r.returncode == 0: cls = 'silent-accept'  # caller decides if it matters
        return cls, r.returncode, round(time.time()-t, 2)
    except subprocess.TimeoutExpired:
        return 'timeout', None, timeout

def run_tsc5(path, timeout=120):
    t = time.time()
    try:
        r = subprocess.run([NODE, TSC5, '--noEmit', '--strict', path],
                           capture_output=True, text=True, timeout=timeout,
                           preexec_fn=_cap)
        out = r.stderr + r.stdout
        cls = 'ok'
        if r.returncode < 0: cls = 'killed'
        elif 'TS2321' in out: cls = 'fuse-reported'   # tsc5 reports loudly
        elif 'error TS' in out: cls = 'error'
        elif r.returncode == 0: cls = 'silent-accept'
        return cls, r.returncode, round(time.time()-t, 2)
    except subprocess.TimeoutExpired:
        return 'timeout', None, timeout

def verdict(stock, unfused, tsc5):
    """Classify the three-way comparison."""
    s, u, t = stock[0], unfused[0], tsc5[0]
    if s == 'silent-accept' and (u == 'error' or t in ('error', 'fuse-reported')):
        return 'SILENT-ACCEPT'
    if s == 'silent-accept':
        return 'silent-accept-unverified'   # no oracle disagreed
    if s == 'ok' and u == 'ok' and t == 'ok':
        return 'all-pass'
    if s == 'error' and u == 'error':
        return 'agree-error'
    return f'{s}|{u}|{t}'

def main():
    cases = []
    depths = [80, 120, 200]       # around the ~100 relater-fuse boundary
    for c in CONTAINERS:
        for d in depths:
            cases.append((f'bottom-{c}-{d}', probe_bottom(c, d)))
    for c in ['array', 'record', 'box', 'tuple']:
        for d in [120, 200]:
            cases.append((f'mid-{c}-{d}', probe_mid(c, d)))
            cases.append((f'prop-{c}-{d}', probe_prop(c, d)))
    cases.append(('tuple-len-80', probe_tuple_len(80)))
    cases.append(('mutual-interfaces', probe_mutual(0)))
    for c in ['array', 'record', 'box']:
        cases.append((f'ok-{c}-200', probe_ok(c, 200)))

    results = {}
    divergences = []
    print(f'{len(cases)} cases', flush=True)
    for name, src in cases:
        with tempfile.NamedTemporaryFile('w', suffix='.ts', dir=PROBES,
                                         prefix='SA_', delete=False) as f:
            f.write(src); p = f.name
        s = run_go(STOCK, p)
        u = run_go(UNFUSED, p)
        t5 = run_tsc5(p)
        os.unlink(p)
        v = verdict(s, u, t5)
        results[name] = {'stock': s[0], 'unfused': u[0], 'tsc5': t5[0],
                         'verdict': v, 's_s': s[2], 'u_s': u[2], 't5_s': t5[2]}
        if 'SILENT' in v or '|' in v:
            divergences.append(name)
            print(f'  {name}: stock={s[0]} unfused={u[0]} tsc5={t5[0]} -> {v}', flush=True)

    out = os.path.join(ROOT, 'data', 'phaseXV_silent_accept.json')
    json.dump({'act': 'XV', 'binaries': {'stock': STOCK, 'unfused': UNFUSED, 'tsc5': TSC5},
               'cases': results,
               'divergences': divergences}, open(out, 'w'), indent=1)
    print(f'\nwrote {out}\nverdict tally:', flush=True)
    from collections import Counter
    print(Counter(v['verdict'] for v in results.values()), flush=True)

if __name__ == '__main__':
    main()
