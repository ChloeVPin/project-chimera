#!/usr/bin/env python3
"""Act XX — The Compiler Whisperer: census of silently-dropped diagnostics.

Runs a fixed battery of probes against tsc 5.9, stock tsgo, and tsgo-unfused,
and records exit code + emitted diagnostics per case into
data/phaseXX_whisperer_raw.json. Each case maps to one silent-drop site or
class found in the checker source:

  post-fuse-1/2   checker.go:22225 / instantiateType (tsc5) — after the fuse
                  yields errorType, all further checks on that type pass
                  silently (SHARED swallow, proven here).
  deep-mismatch   relater.go:3137 — the proven tsgo-unique hole (positive
                  control: stock accepts silently, tsc5/unfused report).
  phantom-1/2     relater.go:3162 expanding-Both — fires only on
                  infinitely-similar shapes; expected accept is CORRECT
                  (params never materialize).
  inference       inference.go:352 — expanding-Both at depth-2 in inference;
                  benign: T still infers from top-level args.
  controls        ordinary mismatches must always be loud.

Honest labels: a case is 'silent-accept' only when a real error is dropped;
'correct-accept' when acceptance is semantically right (phantom params);
'loud' when the diagnostic is emitted.
"""
import json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STOCK   = os.path.expanduser('~/tools/tsgo-stock')
UNFUSED = os.path.expanduser('~/tools/tsgo-unfused')
TSC5    = '/home/ubuntu/d1/ts5/node_modules/typescript/bin/tsc'
NODE    = os.path.expanduser('~/tools/node/bin/node')
OUT     = os.path.join(ROOT, 'data', 'phaseXX_whisperer_raw.json')

CASES = {}

def case(name, src, expect, klass, note, cwd_config=False, strict_tsconfig=False):
    CASES[name] = dict(src=src, expect=expect, klass=klass, note=note,
                       cwd_config=cwd_config, strict_tsconfig=strict_tsconfig)

# --- Class B: post-fuse permissive-any suppression (SHARED) -------------------
BOMB = ("type Bomb<T> = T extends any ? (Bomb<T> extends infer U ? "
        "[U, U, U, U, U] : never) : never;\n")
case('post-fuse-1',
     BOMB + "const b = null as any as Bomb<Bomb<Bomb<Bomb<Bomb<string>>>>>;\n"
            "const wrong: { x: number } = b;   // real mismatch — expect silent\n"
            "const plain: number = \"str\";     // ordinary error — expect loud\n",
     expect={'tsc5': ['TS2589', 'TS2322'], 'tsgo': ['TS2589', 'TS2322'],
             'unfused': ['TIMEOUT']},
     klass='post-fuse-suppression',
     note='w1 silently accepted on both stock checkers; fuse converts the '
          'type to errorType (universally assignable) after one loud TS2589')
case('post-fuse-2',
     BOMB + "const b1 = null as any as Bomb<Bomb<Bomb<Bomb<Bomb<string>>>>>;\n"
            "const b2 = null as any as Bomb<Bomb<Bomb<Bomb<Bomb<number>>>>>;\n"
            "const w1: { x: number } = b1;\n"
            "const w2: { y: string } = b2;\n"
            "const ok: number = \"loud\";\n",
     expect={'tsc5': ['TS2589', 'TS2589', 'TS2322'], 'tsgo': ['TS2589', 'TS2589', 'TS2322'],
             'unfused': ['TIMEOUT']},
     klass='post-fuse-suppression',
     note='each bomb trips once (2x TS2589); BOTH wrong-shape assigns swallowed')

# --- Class A: depth-100 relater hole (positive control) -----------------------
case('deep-mismatch-150',
     'declare const src: %s;\nconst x: %s = src;\n' % (
         ''.join('Array<' for _ in range(150)) + 'string' + '>' * 150,
         ''.join('Array<' for _ in range(150)) + 'number' + '>' * 150),
     expect={'tsc5': ['TS2321'], 'tsgo': [], 'unfused': ['TS2322']},
     klass='relater-depth-100-hole',
     note='proven tsgo-unique hole: stock swallows the whole subtree at relater '
          'stack>100; tsc5 warns TS2321, unfused reports the real mismatch')

# --- Class C: benign bails (phantom params — accept is CORRECT) ---------------
case('phantom-deep',
     'type Deep<T> = { v: Deep<T[]> };\n'
     'declare const a: Deep<string>;\n'
     'const b: Deep<number> = a;\n',
     expect={'tsc5': [], 'tsgo': [], 'unfused': []},
     klass='expanding-both-benign',
     note='T is phantom — Deep<string> ≡ Deep<number> structurally; accept is '
          'semantically correct, the bail cannot hide finite errors here')
case('phantom-recur',
     'interface B<T> { v: B<T> }\n'
     'function f<T>() {\n'
     '  const src = null as any as B<T>;\n'
     '  const dst: B<number> = src;\n'
     '}\n',
     expect={'tsc5': [], 'tsgo': [], 'unfused': []},
     klass='expanding-both-benign',
     note='recursive generic interface: same recursion identity each level, '
          'param phantom again — accept correct on all three')
case('generic-leaf',
     'type D6<X> = {a:{a:{a:{a:{a:{a:X}}}}}};\n'
     'function g<T>() {\n'
     '  const src = null as any as D6<T>;\n'
     '  const dst: D6<number> = src;\n'
     '}\n',
     expect={'tsc5': ['TS2322'], 'tsgo': ['TS2322'], 'unfused': ['TS2322']},
     klass='expanding-both-boundary',
     note='param DOES materialize at leaf → error reported before flags reach '
          'Both — mismatch always surfaces above the bail trigger depth')

# --- inference circularity skip (depth-2, benign) ------------------------------
case('inference-top-arg',
     'interface B<T> { v: B<T> }\n'
     'type B6<X> = B<B<B<B<B<B<X>>>>>>\n'
     'declare function f<T>(x: B6<T>): T;\n'
     'declare const src: B6<string>;\n'
     'const r = f(src);\n'
     'const check: string = r;\n'
     'const check2: number = r;\n',
     expect={'tsc5': ['TS2322'], 'tsgo': ['TS2322'], 'unfused': ['TS2322']},
     klass='inference-circularity-benign',
     note='T inferred at top-level args before the expanding-Both skip can '
          'fire — r:string, check2 errors correctly')

# --- Class E: the config-gate pair (needs a tsconfig-bearing cwd) -------------
case('config-gate-tsgo',
     'const a: number = "x";\nconst b: string = 42;\n',
     expect={'tsc5': ['TS2322', 'TS2322'], 'tsgo': ['TS5112'], 'unfused': ['TS5112']},
     klass='config-gate-suppression',
     note='file args + tsconfig.json in cwd: tsgo emits ONLY TS5112 and skips '
          'compilation (ExitStatusDiagnosticsPresent_OutputsSkipped) — every '
          'real diagnostic dropped; tsc5 checks the files but silently ignores '
          'the project config (see strict-drop below)',
     cwd_config=True)
case('strict-drop-tsc5',
     'export function f(x) { return x; }\n',
     expect={'tsc5': [], 'tsgo': ['TS5112'], 'unfused': ['TS5112']},
     klass='silent-config-drop',
     note='tsconfig declares strict:true + noImplicitAny; tsc5 with file args '
          'silently bypasses it → rc=0, the TS7006 implicit-any error never '
          'reported. False-clean on code violating the project\'s rules.',
     cwd_config=True, strict_tsconfig=True)

CASES['strict-drop-tsc5']['no_strict_args'] = True

# --- controls ------------------------------------------------------------------
case('control-shallow',
     'const x: number = "string";\n',
     expect={'tsc5': ['TS2322'], 'tsgo': ['TS2322'], 'unfused': ['TS2322']},
     klass='control', note='ordinary error always loud')
case('control-deep-ok',
     'declare const src: %s;\nconst x: %s = src;\n' % (
         ''.join('Array<' for _ in range(150)) + 'number' + '>' * 150,
         ''.join('Array<' for _ in range(150)) + 'number' + '>' * 150),
     expect={'tsc5': [], 'tsgo': [], 'unfused': []},
     klass='control', note='identical deep types accept everywhere')

RUNNERS = {
    'tsc5':    [NODE, TSC5],
    'tsgo':    [STOCK],
    'unfused': [UNFUSED],
}
DIAG = re.compile(r'error (TS\d+)')

CLEAN_DIR = tempfile.mkdtemp(prefix='whisperer-')   # no tsconfig up this tree
CFG_DIR = tempfile.mkdtemp(prefix='whisperer-cfg-')  # plain tsconfig
STRICT_DIR = tempfile.mkdtemp(prefix='whisperer-strict-')
with open(os.path.join(CFG_DIR, 'tsconfig.json'), 'w') as f:
    f.write('{"compilerOptions": {"strict": true}}\n')
with open(os.path.join(STRICT_DIR, 'tsconfig.json'), 'w') as f:
    f.write('{"compilerOptions": {"strict": true, "noImplicitAny": true}}\n')

def run_one(cmd, src, timeout=90, workdir=None, strict_args=True):
    workdir = workdir or CLEAN_DIR
    with tempfile.NamedTemporaryFile('w', suffix='.ts', dir=workdir, delete=False) as f:
        f.write(src)
        path = f.name
    try:
        # cwd matters: tsgo walks up from CWD for tsconfig.json and aborts
        # with TS5112 if found — a config-gate, not a checker result.
        args = cmd + ['--noEmit'] + (['--strict'] if strict_args else []) + \
            [os.path.basename(path)]
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                           cwd=workdir)
        return sorted(set(DIAG.findall(p.stdout + p.stderr))), p.returncode
    except subprocess.TimeoutExpired:
        return ['TIMEOUT'], -1
    finally:
        os.unlink(path)

def main():
    results = {}
    for name, c in CASES.items():
        row = {'klass': c['klass'], 'note': c['note'], 'runs': {}}
        workdir = (STRICT_DIR if c.get('strict_tsconfig') else
                   CFG_DIR if c.get('cwd_config') else CLEAN_DIR)
        for label, cmd in RUNNERS.items():
            if label == 'unfused' and c['expect'].get('unfused') == ['TIMEOUT']:
                row['runs'][label] = {'diags': ['TIMEOUT'], 'rc': -1, 'skipped': True}
                continue
            diags, rc = run_one(cmd, c['src'], workdir=workdir,
                                strict_args=not c.get('no_strict_args'))
            row['runs'][label] = {'diags': diags, 'rc': rc}
        row['expect'] = c['expect']
        results[name] = row
        print(f"{name:22s} " + ' '.join(
            f"{l}={r['diags']}" for l, r in row['runs'].items()))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w') as f:
        json.dump({'act': 'XX-whisperer', 'cases': results}, f, indent=2)
    print('wrote', OUT)

if __name__ == '__main__':
    sys.exit(main())
