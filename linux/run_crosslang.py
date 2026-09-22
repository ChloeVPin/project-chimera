#!/usr/bin/env python3
"""Act XVII-4 — cross-language silent-accept scan.

Feeds each production compiler a deep nested-generic MISMATCH probe
(Wrap^N<leafA> assigned to Wrap^N<leafB>) and a same-type control.

Measured results (Linux x86_64):
  rustc   E0308 error at n=50,200            LOUD
  go      type error at n=50,200             LOUD
  javac   error <=25, then EXPONENTIAL HANG  (~10x per +5 levels: 0.5s@25,
          6s@30, >60s@35, >90s@50-200) — third failure mode
  csc     CS0029 error at n=200              LOUD
  swiftc  error at n=50,200                  LOUD
  g++     error at n=50,200                  LOUD
  clang++ error at n=50,200                  LOUD
  tsgo    error <=100, SILENT ACCEPT >=101   the only silent hole

tsgo-stock is the only production compiler here that accepts wrong deep code
with zero diagnostics.
"""
import subprocess, os, sys

def nest(w, i, n):
    s = i
    for _ in range(n):
        s = w.format(s)
    return s

CASES = {
 'rust':   ('p.rs',    lambda n, L: f'struct W<T>(T);\nfn f(x: {nest("W<{}>",L[0],n)}) -> {nest("W<{}>",L[1],n)} {{ x }}\nfn main(){{}}',
            ['rustc', '-o', '/tmp/xl_rust', '--edition', '2021', '-A', 'dead_code'], ('u32', 'i32')),
 'go':     ('p.go',    lambda n, L: f'package main\ntype W[T any] struct{{ v T }}\nvar a {nest("W[{}]",L[0],n)}\nvar b {nest("W[{}]",L[1],n)} = a\nfunc main(){{}}',
            ['go', 'build', '-o', '/tmp/xl_go'], ('int', 'string')),
 'java':   ('P.java',  lambda n, L: 'class Box<T> { T v; }\nclass P { ' + nest('Box<{}>', L[0], n) + ' a; ' + nest('Box<{}>', L[1], n) + ' b = a; }',
            ['javac', '-d', '/tmp/xl_out'], ('Integer', 'String')),
 'swift':  ('p.swift', lambda n, L: f'struct W<T> {{ var v: T }}\nfunc f(_ x: {nest("W<{}>",L[0],n)}) -> {nest("W<{}>",L[1],n)} {{ x }}\n',
            ['swiftc', '-o', '/tmp/xl_swift'], ('Int', 'String')),
 'g++':    ('p.cpp',   lambda n, L: 'template<class T> struct W { T v; };\n' + nest('W<{}>', L[0], n) + ' a; ' + nest('W<{}>', L[1], n) + ' b = a;\nint main(){}',
            ['g++', '-x', 'c++', '-fsyntax-only', '-std=c++20'], ('int', 'double')),
 'clang++':('p.cpp',   lambda n, L: 'template<class T> struct W { T v; };\n' + nest('W<{}>', L[0], n) + ' a; ' + nest('W<{}>', L[1], n) + ' b = a;\nint main(){}',
            ['clang++', '-x', 'c++', '-fsyntax-only', '-std=c++20'], ('int', 'double')),
 'tsgo':   ('p.ts',    lambda n, L: f'declare const a: {nest("Array<{}>",L[0],n)};\nconst b: {nest("Array<{}>",L[1],n)} = a;\n',
            [os.path.expanduser('~/tools/tsgo-stock'), '--noEmit', '--ignoreConfig'], ('number', 'string')),
}

def classify(rc, out):
    if rc == 0:
        return 'SILENT-ACCEPT'
    if 'error' in out.lower() or 'mismatch' in out.lower() or 'cannot' in out.lower():
        return 'LOUD-ERROR'
    return f'CRASH(rc={rc})'

def main():
    os.makedirs('/tmp/xl_out', exist_ok=True)
    for lang, (fn, gen, cmd, leaves) in CASES.items():
        for n in (50, 200):
            fp = '/tmp/xl_' + fn
            open(fp, 'w').write(gen(n, leaves))
            try:
                r = subprocess.run(cmd + [fp], capture_output=True, text=True, timeout=120)
                print(f'{lang:8} n={n}: {classify(r.returncode, r.stderr + r.stdout)}', flush=True)
            except subprocess.TimeoutExpired:
                print(f'{lang:8} n={n}: HANG >120s', flush=True)

if __name__ == '__main__':
    main()
