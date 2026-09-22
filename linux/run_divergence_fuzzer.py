#!/usr/bin/env python3
"""Act XIX-3: systematic tsc5 vs tsgo divergence fuzzer.

Generates small, self-contained TS programs across construct domains where
a Go-port porting defect could hide (variance, inference, conditionals,
mapped types, unions, index signatures, tuples, intersections, this-types,
excess-property checks). For each case: run tsc 5.9.3 and stock tsgo,
compare (a) whether each reports an error, (b) the error code sets.

Classification:
  IDENTICAL          both accept or both reject with same primary code
  TSC5_ONLY_ERR      tsc5 errors, tsgo silent  (suspect tsgo regression)
  TSGO_ONLY_ERR      tsgo errors, tsc5 silent  (suspect tsgo false-positive)
  CODE_DIFFER        both error but different codes / targets

Each case writes a self-contained file to cases/ for manual minimization.
Writes data/phaseXIX_divergence_raw.json (raw per-case schema; the committed phaseXIX_divergence.json is the curated summary).
"""
import json, os, re, subprocess, tempfile

TSC5 = ['node', '/home/ubuntu/d1/ts5/node_modules/typescript/bin/tsc']
TSGO = [os.path.expanduser('~/tools/tsgo-stock')]
FLAGS = ['--noEmit', '--strict', '--skipLibCheck']

CASES = {}  # name -> source

def add(domain, name, src):
    CASES[f'{domain}/{name}'] = src

# ---------- domain: variance ----------
for ro in ('', 'readonly '):
    for leaf in ('string', 'number'):
        other = 'number' if leaf == 'string' else 'string'
        add('variance', f'arr-{ro}-{leaf}-to-{other}',
            f'declare const a: {ro}Array<{leaf}>;\nconst b: {ro}Array<{other}> = a;\n')
add('variance', 'method-bivariance', '''
interface A { m(x: string): void }
interface B { m(x: number): void }
declare const a: A; const b: B = a;
''')
add('variance', 'fnprop-strict', '''
interface A { m: (x: string) => void }
interface B { m: (x: number) => void }
declare const a: A; const b: B = a;
''')
add('variance', 'param-count-more', '''
declare const f: (a: string, b: number) => void;
const g: (a: string) => void = f;
''')
add('variance', 'param-count-fewer', '''
declare const f: (a: string) => void;
const g: (a: string, b: number) => void = f;
''')

# ---------- domain: conditional ----------
add('conditional', 'naked-distributive', '''
type R<T> = T extends string ? "s" : "o";
declare const x: R<string | number>;
const y: "s" = x;
''')
add('conditional', 'clothed-nondistrib', '''
type R<T> = [T] extends [string] ? "s" : "o";
declare const x: R<string | number>;
const y: "o" = x;
''')
add('conditional', 'infer-position', '''
type R<T> = T extends { v: infer U } ? U : never;
declare const x: R<{ v: number }>;
const y: string = x;
''')
add('conditional', 'never-propagate', '''
type R<T> = T extends string ? T : never;
declare const x: R<never>;
const y: "ok" = x;
''')
add('conditional', 'nested-infer', '''
type R<T> = T extends Array<infer U extends string> ? U : never;
declare const x: R<Array<"a">>;
const y: number = x;
''')

# ---------- domain: mapped ----------
add('mapped', 'homomorphic-partial', '''
declare const a: Partial<{ x: string; y: number }>;
const b: { x: string } = a;
''')
add('mapped', 'key-remap-as', '''
type R<T> = { [K in keyof T as `get${string & K}`]: T[K] };
declare const a: R<{ x: number }>;
const b: { getx: string } = a;
''')
add('mapped', 'readonly-strip', '''
type R<T> = { -readonly [K in keyof T]: T[K] };
declare const a: R<{ readonly x: number }>;
const b: { x: string } = a;
''')
add('mapped', 'optional-add', '''
type R<T> = { [K in keyof T]+?: T[K] };
declare const a: R<{ x: number }>;
const b: { x: undefined } = a;
''')

# ---------- domain: inference ----------
add('inference', 'lower-upper-priority', '''
declare function f<T>(a: T, b: string): T;
const x = f(42, "s");
const y: string = x;
''')
add('inference', 'noinfer', '''
declare function f<T>(a: T, b: NoInfer<T>): void;
f("a", 42);
''')
add('inference', 'contravariant-witness', '''
declare function f<T>(cb: (x: T) => void): T;
const x = f((s: string) => {});
const y: number = x;
''')
add('inference', 'literal-widening', '''
declare function f<T>(x: T): T;
const x = f("lit");
const y: "lit" = x;
''')
add('inference', 'const-typeparam', '''
declare function f<const T>(x: T): T;
const x = f([1, 2]);
const y: readonly [1, 2] = x;
''')

# ---------- domain: union ----------
add('union', 'subtype-reduction', '''
declare const a: string | number;
const b: string | number | boolean = a;
''')
add('union', 'excess-union-member', '''
const o: { k: string } | { j: number } = { k: "s", extra: 1 };
''')
add('union', 'discriminant-narrow', '''
declare const u: { t: "a"; v: string } | { t: "b"; v: number };
const w: { t: "a"; v: string } = u;
''')
add('union', 'union-fn-call', '''
declare const f: ((x: string) => void) | ((x: number) => void);
f(1);
''')

# ---------- domain: index-signature ----------
add('index', 'exactoptional', '''
interface Cfg { [k: string]: string | undefined; req?: string }
const c: Cfg = { req: undefined };
''')
add('index', 'number-index-cov', '''
declare const a: { [i: number]: string };
const b: { [i: number]: number } = a;
''')
add('index', 'record-partial-mismatch', '''
declare const a: Record<string, { v: string }>;
const b: Record<string, { v: number }> = a;
''')

# ---------- domain: tuple ----------
add('tuple', 'variadic-middle', '''
declare const t: [string, ...number[], boolean];
const u: [string, boolean] = t;
''')
add('tuple', 'labeled-mismatch', '''
declare const t: [first: string, second: number];
const u: [first: number, second: string] = t;
''')
add('tuple', 'readonly-conv', '''
declare const t: readonly [string, number];
const u: [string, number] = t;
''')
add('tuple', 'optional-elem', '''
declare const t: [string, number?];
const u: [string] = t;
''')

# ---------- domain: intersection ----------
add('intersection', 'reduce-conflict', '''
type A = { x: string } & { x: number };
declare const a: A;
const s: string = a.x;
''')
add('intersection', 'prim-intersect', '''
declare const a: string & { brand: true };
const b: string = a;
''')
add('intersection', 'never-in-inter', '''
type A = string & never;
declare const a: A;
const b: number = a;
''')

# ---------- domain: this-types ----------
add('this', 'fluent-chain', '''
class B { m(): this { return this } }
class D extends B { d() { return 1 } }
const d = new D().m().d();
const s: string = d;
''')
add('this', 'assertion-sig', '''
function assert(x: unknown): asserts x is string {}
declare const u: unknown;
assert(u);
const n: number = u;
''')

# ---------- domain: excess-props ----------
add('excess', 'fresh-literal', '''
const o: { a: string } = { a: "s", b: 1 };
''')
add('excess', 'nonfresh-alias', '''
const src = { a: "s", b: 1 };
const o: { a: string } = src;
''')
add('excess', 'nested-fresh', '''
const o: { a: { x: string } } = { a: { x: "s", leak: true } };
''')

# ---------- domain: operators ----------
add('operators', 'keyof-never', '''
type K = keyof never;
declare const k: K;
const s: string = k;
''')
add('operators', 'keyof-union', '''
type K = keyof ({a:1} | {b:2});
declare const k: K;
const s: "a" = k;
''')
add('operators', 'typeof-window', '''
declare const t: typeof NaN;
const n: string = t;
''')

OUT = {}
for name, src in CASES.items():
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, 'p.ts')
        open(f, 'w').write(src)
        res = {}
        for tag, cmd in (('tsc5', TSC5 + FLAGS + [f]), ('tsgo', TSGO + FLAGS + ['--ignoreConfig', f])):
            try:
                r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                out = r.stderr + r.stdout
                codes = sorted(set(re.findall(r'error TS(\d+)', out)))
                res[tag] = {'ok': r.returncode == 0, 'codes': codes}
            except subprocess.TimeoutExpired:
                res[tag] = {'ok': None, 'codes': ['TIMEOUT']}
        t5, tg = res['tsc5'], res['tsgo']
        if t5['ok'] and tg['ok']:
            verdict = 'IDENTICAL-ACCEPT'
        elif not t5['ok'] and not tg['ok']:
            verdict = 'IDENTICAL-REJECT' if t5['codes'] == tg['codes'] else f"CODE_DIFFER tsc5={t5['codes']} tsgo={tg['codes']}"
        elif not t5['ok'] and tg['ok']:
            verdict = f"TSC5_ONLY_ERR {t5['codes']}"
        else:
            verdict = f"TSGO_ONLY_ERR {tg['codes']}"
        OUT[name] = {'verdict': verdict, 'tsc5': t5, 'tsgo': tg}
        mark = '' if verdict.startswith('IDENTICAL') else '  <<<<'
        print(f'{name:42} {verdict}{mark}')

divs = {k: v for k, v in OUT.items() if not v['verdict'].startswith('IDENTICAL')}
json.dump({'act': 'XIX-3', 'total': len(OUT), 'divergent': len(divs), 'results': OUT},
          open('data/phaseXIX_divergence_raw.json', 'w'), indent=1)
print(f"\n{len(divs)}/{len(OUT)} divergent")
for k in divs: print(' ', k, divs[k]['verdict'])
