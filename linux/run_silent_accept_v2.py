#!/usr/bin/env python3
"""Act XV-B — boundary bisection + wider construct sweep for the silent-accept hole.

Part 1: bisect the exact type depth where stock tsgo stops reporting the
mismatch (Array<n> bottom-mismatch family, n = 101..160).

Part 2: more construct families — mapped types, conditional types, generic
inference, class methods, getter return types, index signatures, distributive
conditionals — at depths straddling the fuse.
"""
import json, os, resource, subprocess, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBES = os.path.join(ROOT, 'linux', 'probes')
STOCK   = os.path.expanduser('~/tools/tsgo-stock')
UNFUSED = os.path.expanduser('~/tools/tsgo-unfused')
TSC5    = '/home/ubuntu/d1/ts5/node_modules/typescript/bin/tsc'
NODE    = os.path.expanduser('~/tools/node/bin/node')
AS_CAP = 12 * 1024**3
def _cap(): resource.setrlimit(resource.RLIMIT_AS, (AS_CAP, AS_CAP))

def deep(n, inner_l='number', inner_r='string'):
    l, r = inner_l, inner_r
    for _ in range(n):
        l, r = f'Array<{l}>', f'Array<{r}>'
    return l, r

def assign(l, r):
    return f'declare const src: {r};\nconst x: {l} = src;\n'

# -- part 2 families ----------------------------------------------------------
def p_mapped(n):
    # mismatch inside a mapped type over a deep record
    inner = 'number'
    for _ in range(n):
        inner = f'{{v: {inner}}}'
    return (f'type M<T> = {{[K in keyof T]: T[K]}};\n'
            f'declare const src: M<{{v: {inner}; extra: 1}}>;\n'
            f'const x: M<{{v: {inner}}}> = src;\n')

def p_conditional(n):
    l, r = deep(n)
    return (f'type C<T> = T extends Array<infer I> ? I : never;\n'
            f'declare const src: {r};\n'
            f'const x: {l} = src;\n'
            f'type _T = C<{l}>;\nexport type {{ _T }};\n')

def p_infer(n):
    # inference path: generic function called with deep arg, return assign to wrong decl
    l, r = deep(n)
    return (f'declare function f<T>(x: T): T;\n'
            f'declare const src: {r};\n'
            f'const x: {l} = f(src);\n')

def p_method(n):
    l, r = deep(n)
    return (f'interface A {{ m(): {l} }}\n'
            f'interface B {{ m(): {r} }}\n'
            f'declare const src: B;\nconst x: A = src;\n')

def p_getter(n):
    l, r = deep(n)
    return (f'class A {{ get g(): {l} {{ throw 0 }} }}\n'
            f'class B {{ get g(): {r} {{ throw 0 }} }}\n'
            f'declare const src: B;\nconst x: A = src;\n')

def p_indexsig(n):
    l, r = deep(n)
    return (f'declare const src: {{[k: string]: {r}}};\n'
            f'const x: {{[k: string]: {l}}} = src;\n')

def p_deep_fn_param(n):
    # function type nested deep inside arrays (param position, bivariance check)
    l = 'number'; r = 'string'
    for _ in range(n):
        l = f'Array<(x: {l}) => void>'
        r = f'Array<(x: {r}) => void>'
    return assign(l, r)

def p_cond_constraint(n):
    # conditional-type constraint deep mismatch (exercises condConstraintDepth fuse at 100)
    body = 'T'
    return (f'type C<T> = T extends infer U ? (U extends number ? U : never) : never;\n'
            f'type R0<T> = T extends infer U ? C<U> : never;\n'
            + ''.join(f'type R{i}<T> = T extends infer U ? R{i-1}<U> : never;\n' for i in range(1, n))
            + f'type _T = R{n-1}<number>;\nexport type {{ _T }};\n')

def p_variance(n):
    # class with deep generic — in-variance via method param
    l, r = deep(n)
    return (f'class C<T> {{ set(v: T): void {{}} }}\n'
            f'declare const src: C<{r}>;\nconst x: C<{l}> = src;\n')

FAMS = {
    'mapped': p_mapped, 'conditional': p_conditional, 'infer': p_infer,
    'method': p_method, 'getter': p_getter, 'indexsig': p_indexsig,
    'deep-fn-param': p_deep_fn_param, 'variance-class': p_variance,
}

def run_go(binary, path, timeout=90):
    t = time.time()
    try:
        r = subprocess.run([binary, '--noEmit', '--ignoreConfig', path],
                           capture_output=True, text=True, timeout=timeout,
                           env=dict(os.environ, GOMEMLIMIT='8GiB'), preexec_fn=_cap)
        out = r.stderr + r.stdout
        cls = 'ok'
        if r.returncode < 0 or (r.returncode != 0 and not out.strip()): cls = 'oom'
        elif 'goroutine stack exceeds' in out: cls = 'go-stack-panic'
        elif 'panic:' in out or 'fatal error' in out: cls = 'go-panic'
        elif 'TS2589' in out or 'TS2321' in out: cls = 'fuse!'
        elif 'error TS' in out: cls = 'error'
        elif r.returncode == 0: cls = 'clean'
        return cls, round(time.time()-t, 2)
    except subprocess.TimeoutExpired:
        return 'timeout', timeout

def run_tsc5(path, timeout=90):
    t = time.time()
    try:
        r = subprocess.run([NODE, TSC5, '--noEmit', '--strict', path],
                           capture_output=True, text=True, timeout=timeout, preexec_fn=_cap)
        out = r.stderr + r.stdout
        cls = 'ok'
        if r.returncode < 0: cls = 'killed'
        elif 'TS2321' in out: cls = 'fuse-reported'
        elif 'error TS' in out: cls = 'error'
        elif r.returncode == 0: cls = 'clean'
        return cls, round(time.time()-t, 2)
    except subprocess.TimeoutExpired:
        return 'timeout', timeout

def run_case(name, src, expect_error=True):
    with tempfile.NamedTemporaryFile('w', suffix='.ts', dir=PROBES, prefix='SA2_',
                                     delete=False) as f:
        f.write(src); p = f.name
    s = run_go(STOCK, p); u = run_go(UNFUSED, p); t5 = run_tsc5(p)
    os.unlink(p)
    true_error = u[0] == 'error' or t5[0] == 'error'
    if expect_error and s[0] == 'clean' and true_error:
        v = 'SILENT-ACCEPT'
    elif expect_error and s[0] == 'clean' and not true_error:
        v = 'clean-unverified'
    elif not expect_error and all(c[0] in ('clean',) for c in (s, u, t5)):
        v = 'all-pass'
    elif s[0] == 'error' and u[0] == 'error':
        v = 'agree-error'
    else:
        v = f'{s[0]}|{u[0]}|{t5[0]}'
    print(f'  {name}: stock={s[0]} unfused={u[0]} tsc5={t5[0]} -> {v}', flush=True)
    return {'stock': s[0], 'unfused': u[0], 'tsc5': t5[0], 'verdict': v,
            's_s': s[1], 'u_s': u[1], 't5_s': t5[1]}

def main():
    res = {'bisection': {}, 'families': {}}
    print('== PART 1: exact silent-accept boundary (Array bottom-mismatch)', flush=True)
    for n in [100, 101, 105, 110, 115, 120, 125, 130, 140, 150]:
        l, r = deep(n)
        res['bisection'][n] = run_case(f'bisect-{n}', assign(l, r))
    print('== PART 2: wider construct families', flush=True)
    for fam, gen in FAMS.items():
        for d in [80, 150]:
            res['families'][f'{fam}-{d}'] = run_case(f'{fam}-{d}', gen(d))
    print('== conditional-constraint fuse path', flush=True)
    for d in [150, 300]:
        res['families'][f'cond-constraint-{d}'] = run_case(f'cond-constraint-{d}', p_cond_constraint(d), expect_error=False)
    out = os.path.join(ROOT, 'data', 'phaseXV_silent_accept_v2.json')
    json.dump({'act': 'XV-B', 'cases': res}, open(out, 'w'), indent=1)
    print('wrote', out, flush=True)

if __name__ == '__main__':
    main()
