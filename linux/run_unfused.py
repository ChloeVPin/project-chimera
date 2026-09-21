#!/usr/bin/env python3
"""Act XIV — The Limiter-Free Compiler.
tsgo-unfused = typescript-go @89d5d5b2 with all four fuse sites disabled:
  checker.go:22225  instantiationDepth==100 || instantiationCount>=5_000_000
  checker.go:24433  tailCount==1000
  checker.go:27686  conditionalConstraintDepth>=100
  relater.go:3133   len(sourceStack)==100 || len(targetStack)==100   (TS2321/2322 nest fuse)

Now every observed wall is PHYSICAL: time, heap, or Go's 1GB goroutine
stack cap (panic: 'goroutine stack exceeds 1000000000-byte limit').
We measure the TRUE work of programs only ever seen truncated at a fuse,
and the real walls of the unfused checker.
"""
import json, os, resource, subprocess, sys, time, tempfile

AS_CAP = 24 * 1024**3  # child virtual-memory cap: Go's mmap fails here, well before the 31GB kernel OOM killer

def _cap_child():
    resource.setrlimit(resource.RLIMIT_AS, (AS_CAP, AS_CAP))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBES = os.path.join(ROOT, 'linux', 'probes')
UNFUSED = os.path.expanduser('~/tools/tsgo-unfused')
STOCK   = os.path.expanduser('~/tools/tsgo-stock')

HDR = ('import { EvolveTCO, EvolveStrictNonTCO } from "../../src/type_engine/rule110";\n'
       'type Tape8 = [0, 1, 1, 0, 1, 1, 1, 0];\n')

def gen_nont(n):
    return HDR + f'type _Probe = EvolveStrictNonTCO<Tape8, {n}>;\nexport type {{ _Probe }};\n'

def gen_tco(n):
    return HDR + f'type _Probe = EvolveTCO<Tape8, {n}>;\nexport type {{ _Probe }};\n'

def gen_freeze(n):
    return HDR + ("""type QuaternaryFreeze<Depth extends number, Path extends readonly unknown[] = []> =
  Path['length'] extends Depth ? 1 :
  [QuaternaryFreeze<Depth, [0, ...Path]>, QuaternaryFreeze<Depth, [1, ...Path]>,
   QuaternaryFreeze<Depth, [2, ...Path]>, QuaternaryFreeze<Depth, [3, ...Path]>] extends [infer A, infer B, infer C, infer D] ? [A, B, C, D] : never;
""" + f'type _Probe = QuaternaryFreeze<{n}>;\nexport type {{ _Probe }};\n')

def gen_nest(n):
    # Two deep types compared against each other — exercises the relater's
    # sourceStack/targetStack nest fuse (relater.go:3133, TernaryMaybe at 100).
    # LHS/RHS differ only at the bottom, so a correct relater must recurse
    # the full depth before finding the mismatch.
    l = 'number'; r = 'string'
    for _ in range(n):
        l = f'Array<{l}>'; r = f'Array<{r}>'
    return f'declare const src: {r};\nconst x: {l} = src;\n'

def gen_nest_ok(n):
    # Identical deep types — the relater should succeed at any depth.
    s = 'number'
    for _ in range(n):
        s = f'Array<{s}>'
    return f'declare const src: {s};\nconst x: {s} = src;\n'

def run(compiler, path, timeout=600, expect_error=False):
    t = time.time()
    # GOMEMLIMIT caps the Go heap before the kernel OOM-killer can cascade
    # into the parent — an unfused FREEZE run would otherwise eat all 31GB.
    env = dict(os.environ, GOMEMLIMIT='20GiB', GOGC='100')
    try:
        r = subprocess.run([compiler, '--noEmit', '--ignoreConfig', '--extendedDiagnostics', path],
                           capture_output=True, text=True, timeout=timeout, env=env,
                           preexec_fn=_cap_child)
        out = r.stderr + r.stdout
        inst = None
        for line in out.splitlines():
            if line.startswith('Instantiations:'):
                inst = int(line.split(':')[1].strip().replace(',', ''))
        cls = 'ok'
        if r.returncode < 0:
            cls = 'oom'  # signal-killed (OOM killer SIGKILL) — no diagnostics survive
        elif 'goroutine stack exceeds' in out: cls = 'go-stack-panic'
        elif 'panic:' in out or 'fatal error' in out: cls = 'go-panic'
        elif 'out of memory' in out.lower() or 'cannot allocate' in out or 'memory limit' in out.lower() or r.returncode != 0 and not out.strip(): cls = 'oom'
        elif 'TS2589' in out or 'TS2321' in out: cls = 'fuse!'
        elif 'error TS' in out: cls = 'error'
        elif r.returncode == 0 and expect_error: cls = 'silent-accept'  # fuse swallowed the error
        return {'class': cls, 'inst': inst, 's': round(time.time() - t, 2),
                'stderr_tail': r.stderr[-300:] if cls not in ('ok', 'fuse!', 'error') else ''}
    except subprocess.TimeoutExpired:
        return {'class': 'timeout', 's': timeout}

def peak_rss(compiler, path, timeout=600):
    """Run under GNU time and report peak RSS (KB)."""
    try:
        r = subprocess.run(['/usr/bin/time', '-v', compiler, '--noEmit', '--ignoreConfig',
                            '--extendedDiagnostics', path],
                           capture_output=True, text=True, timeout=timeout)
        for line in r.stderr.splitlines():
            if 'Maximum resident set size' in line:
                return int(line.split(':')[1].strip())
    except Exception:
        return None
    return None

def sweep(compiler, gen, name, depths, timeout=600, expect_error=False):
    rows = []
    for d in depths:
        with tempfile.NamedTemporaryFile('w', suffix='.ts', dir=PROBES, prefix='UNFUSED_',
                                         delete=False) as f:
            f.write(gen(d)); p = f.name
        r = run(compiler, p, timeout, expect_error=expect_error)
        os.unlink(p)
        r['depth'] = d
        r['binary'] = os.path.basename(compiler)
        rows.append(r)
        print(f'  {name} depth={d}: {r["class"]} inst={r.get("inst")} {r["s"]}s', flush=True)
        if r['class'] in ('go-stack-panic', 'go-panic', 'oom', 'timeout'):
            print('   -> wall reached', flush=True)
            break
    return rows

def main():
    res = {'binary': UNFUSED, 'base_commit': '89d5d5b2',
           'fuses_removed': ['instantiationDepth==100', 'instantiationCount>=5M',
                             'tailCount==1000', 'conditionalConstraintDepth>=100',
                             'relater nest stack==100 (TS2321/2322)'],
           'experiments': {}}

    print('== TRUE WORK: programs only ever seen truncated at the 5M fuse', flush=True)
    # FREEZE_10 peak RSS + true instantiation count; FREEZE_11 expected OOM on 31GB.
    import tempfile as _tf
    with _tf.NamedTemporaryFile('w', suffix='.ts', dir=PROBES, prefix='UNFUSED_',
                                delete=False) as f:
        f.write(gen_freeze(10)); fp = f.name
    rss = peak_rss(UNFUSED, fp, timeout=300)
    os.unlink(fp)
    print(f'  FREEZE_10 peak RSS = {rss} KB', flush=True)
    res['experiments']['freeze10_peak_rss_kb'] = rss
    res['experiments']['freeze_true_cost'] = sweep(UNFUSED, gen_freeze, 'FREEZE',
                                                   [10, 11], timeout=900)

    print('== DEEP NON-TCO RECURSION (stock dies at 48, mutant at 248)', flush=True)
    res['experiments']['nont_depth'] = sweep(UNFUSED, gen_nont, 'NONT',
                                             [500, 1000, 2000], timeout=300)

    print('== TCO FUEL UNBOUNDED (stock dies at 1000, mutant at 5000)', flush=True)
    res['experiments']['tco_fuel'] = sweep(UNFUSED, gen_tco, 'TCO',
                                           [5000, 20000, 50000], timeout=900)

    print('== RELATER NEST FUSE: mismatched deep types (fuse may silently accept)', flush=True)
    res['experiments']['nest_mismatch_unfused'] = sweep(UNFUSED, gen_nest, 'NEST',
                                                        [150, 500, 1000, 2000], timeout=300,
                                                        expect_error=True)
    res['experiments']['nest_mismatch_stock'] = sweep(STOCK, gen_nest, 'NEST-stock',
                                                       [99, 100, 150, 500], timeout=300,
                                                       expect_error=True)
    res['experiments']['nest_identical_unfused'] = sweep(UNFUSED, gen_nest_ok, 'NEST-ok',
                                                          [5000, 60000], timeout=300)

    out = os.path.join(ROOT, 'data', 'phaseXIV_unfused.json')
    json.dump({'act': 'XIV', 'results': res}, open(out, 'w'), indent=1)
    print(json.dumps(res, indent=1)[:6000])

if __name__ == '__main__':
    main()
