#!/usr/bin/env python3
"""Act XIX-3b: randomized tsc5 vs tsgo divergence hunt.

Hand-targeted cases (run_divergence_fuzzer.py) found 0/44 divergent — the
port bugs hide in COMBINATIONS. This layer randomly composes: generic
interfaces + conditional/mapped/variadic wrappers + mismatched leaves,
seeded for reproducibility. Runs both checkers per case (~0.5s/1.5s each).

Usage: run_divergence_random.py [N] [SEED0] — writes data/phaseXIX_divergence_random_raw.json; prints divergent seeds.
"""
import json, os, random, re, subprocess, sys, tempfile

TSC5 = ['node', '/home/ubuntu/d1/ts5/node_modules/typescript/bin/tsc']
TSGO = [os.path.expanduser('~/tools/tsgo-stock')]
FLAGS = ['--noEmit', '--strict', '--skipLibCheck']

LEAVES = ['string', 'number', 'boolean', '{v: string}', '[number, string]', 'unknown', 'never', 'any', 'null', 'undefined', 'object', 'symbol', 'bigint', '"lit"', '42', 'Date', 'RegExp', 'string[]', 'string | number']
CONTAINERS = [
    'Array<{0}>', 'Promise<{0}>', '{{ v: {0} }}', '{{ v?: {0} }}',
    'readonly {0}[]', 'Partial<{0}>', 'Required<{0}>', 'Record<string, {0}>',
    '[{0}, number]', '[number, ...{0}[]]', 'Readonly<{0}>',
    '{{ m(x: {0}): void }}', '{{ f: (x: {0}) => void }}',
    '{{ r(): {0} }}', '{0} | undefined', '{0} & {{ tag: true }}',
    'keyof {{ k: {0} }}', '({0} extends any ? {0} : never)',
]
JUNCTIONS = [' | ', ' & ']

def gen(rng):
    """Compose a random (source_type, target_type) pair sharing structure."""
    leaf1 = rng.choice(LEAVES)
    leaf2 = rng.choice(LEAVES)
    depth = rng.randint(1, 4)
    s1, s2 = leaf1, leaf2
    for _ in range(depth):
        c = rng.choice(CONTAINERS)
        s1 = c.format(s1)
        s2 = c.format(s2)
    # occasional junction of two differently-composed halves
    if rng.random() < 0.35:
        j = rng.choice(JUNCTIONS)
        leaf1b, leaf2b = rng.choice(LEAVES), rng.choice(LEAVES)
        s1b, s2b = leaf1b, leaf2b
        for _ in range(rng.randint(1, 3)):
            c = rng.choice(CONTAINERS)
            s1b, s2b = c.format(s1b), c.format(s2b)
        s1, s2 = f'({s1}){j}({s1b})', f'({s2}){j}({s2b})'
    direction = rng.random() < 0.5
    src, tgt = (s1, s2) if direction else (s2, s1)
    return f'declare const a: {src};\nconst b: {tgt} = a;\n'

def run(cmd, f):
    try:
        r = subprocess.run(cmd + [f], capture_output=True, text=True, timeout=60)
        codes = sorted(set(re.findall(r'error TS(\d+)', r.stderr + r.stdout)))
        return r.returncode == 0, codes
    except subprocess.TimeoutExpired:
        return None, ['TIMEOUT']

def _usage():
    sys.exit("usage: run_divergence_random.py [N] [SEED0] — N int, SEED0 int")

def _arg(i, default):
    if len(sys.argv) <= i:
        return default
    if sys.argv[i].startswith('-'):
        _usage()
    try:
        return int(sys.argv[i])
    except ValueError:
        _usage()

N = _arg(1, 300)
SEED0 = _arg(2, 19000)
OUT, divs = {}, []
for i in range(N):
    seed = SEED0 + i
    rng = random.Random(seed)
    src = gen(rng)
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, 'p.ts')
        open(f, 'w').write(src)
        t5ok, t5c = run(TSC5 + FLAGS, f)
        tgok, tgc = run(TSGO + FLAGS + ['--ignoreConfig'], f)
    if t5ok and tgok:
        v = 'IDENTICAL-ACCEPT'
    elif not t5ok and not tgok:
        v = 'IDENTICAL-REJECT' if t5c == tgc else f'CODE_DIFFER {t5c}|{tgc}'
    elif not t5ok and tgok:
        v = f'TSC5_ONLY_ERR {t5c}'
    else:
        v = f'TSGO_ONLY_ERR {tgc}'
    OUT[seed] = {'verdict': v, 'src': src, 'tsc5': t5c, 'tsgo': tgc}
    if not v.startswith('IDENTICAL'):
        divs.append(seed)
        print(f'<<<< {seed}: {v}\n{src}')
    if i % 50 == 49:
        print(f'...{i+1}/{N}, divergent so far: {len(divs)}')

json.dump({'act': 'XIX-3b', 'total': N, 'divergent': len(divs), 'seeds': divs, 'results': OUT},
          open('data/phaseXIX_divergence_random_raw.json', 'w'), indent=1)
print(f'\n{len(divs)}/{N} divergent; seeds: {divs}')
