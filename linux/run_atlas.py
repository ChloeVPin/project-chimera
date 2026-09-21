#!/usr/bin/env python3
"""Act XII-C — The Survivability Atlas.
Cross-language map of where compilers die on deep recursive structure,
at unit-resolution survival bands, ASLR on/off. Each wall is classified:
  physical-segv  : OS stack fault (SIGSEGV/SIGBUS) — stochastic under ASLR
  abort          : managed runtime converts SOE into fatal process abort
  caught         : runtime catches SOE -> diagnostic exit (no crash)
  time-wall      : no crash at all; superlinear time is the boundary
"""
import json, os, subprocess, sys, time, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = os.path.expanduser('~/tools/node/bin')
GO   = os.path.expanduser('~/tools/go/bin/go')
JAVAC= os.path.expanduser('~/tools/jdk/bin/javac')
SWIFTC=os.path.expanduser('~/tools/swift/usr/bin/swiftc')
DOTNET=os.path.expanduser('~/tools/dotnet/dotnet')
CSC  =[DOTNET, os.path.expanduser('~/tools/dotnet/sdk/8.0.425/Roslyn/bincore/csc.dll'),
       '/t:library','/nologo','/nowarn:219,168,169','/nostdlib',
       '/r:'+os.path.expanduser('~/tools/dotnet/shared/Microsoft.NETCore.App/8.0.31/System.Private.CoreLib.dll')]
ENV  = dict(os.environ, PATH=NODE+':'+os.environ['PATH'],
            DOTNET_CLI_TELEMETRY_OPTOUT='1', DOTNET_NOLOGO='1')

def nest(d, inner, wrap):
    s = inner
    for _ in range(d): s = wrap(s)
    return s

def gen_cpp(d):
    body = ''.join(f'template<int D> struct F : F<D-1> {{}};\n' for _ in range(0))
    t = 'template<int D> struct F { static const int v = F<D-1>::v + 1; };\n'
    t += 'template<> struct F<0> { static const int v = 0; };\n'
    t += f'const int x = F<{d}>::v;\nint main(){{return x>0?0:0;}}\n'
    return t

def gen_rust(d):
    t = 'struct F<const N: usize>;'.replace('usize','usize')
    t = '#![allow(incomplete_features)]\n#![feature(generic_const_exprs)]\n'
    # simpler: type-level chain via nested generics like Act XI
    t = ''
    t += 'struct Wrap<T>(T);\n'
    expr = nest(d, 'u8', lambda x: f'Wrap<{x}>')
    t += f'fn main() {{ let _x: {expr}; }}\n'
    return t

def gen_java(d):
    s = nest(d, 'String', lambda x: f'java.util.List<{x}>')
    return f'class Deep {{ {s} f; }}\n'

def gen_cs(d):
    s = nest(d, 'object', lambda x: f'C<{x}>')
    return f'class C<T>{{}}\nclass Deep {{ {s} f; }}\n'

def gen_go(d):
    s = nest(d, 'int', lambda x: f'S[{x}]')
    return f'package main\ntype S[T any] struct{{ v T }}\nvar _ {s}\nfunc main(){{}}\n'

def gen_ts5(d):
    s = nest(d, 'number', lambda x: f'Array<{x}>')
    return f'const x: {s} = 0 as any;\n'

def gen_tsgo(d):
    return gen_ts5(d)

def gen_swift(d):
    s = nest(d, 'Int', lambda x: f'G<{x}>')
    return f'struct G<T>{{}}\nlet x: {s}? = nil\n'

SPECS = {
  'g++':    dict(gen=gen_cpp, ext='.cpp', cmd=lambda p:['g++','-fsyntax-only','-std=c++17',p]),
  'clang++':dict(gen=gen_cpp, ext='.cpp', cmd=lambda p:['clang++','-fsyntax-only','-std=c++17',p]),
  'rustc':  dict(gen=gen_rust,ext='.rs',  cmd=lambda p:['rustc','--edition=2021',p,'-o','/dev/null']),
  'javac':  dict(gen=gen_java,ext='.java',cmd=lambda p:[JAVAC,'-d','/tmp/atlas_out',p],cls='Deep'),
  'csc':    dict(gen=gen_cs,  ext='.cs',  cmd=lambda p:CSC+[p]),
  'tsc5':   dict(gen=gen_ts5, ext='.ts',  cmd=lambda p:['node',os.path.expanduser('~/d1/ts5/node_modules/typescript/bin/tsc'),'--noEmit',p]),
  'tsgo':   dict(gen=gen_tsgo,ext='.ts',  cmd=lambda p:['npx','tsc','--ignoreConfig','--noEmit',p]),
  'go gc':  dict(gen=gen_go,  ext='.go',  cmd=lambda p:[GO,'build','-o','/tmp/atlas_out/g',p]),
  'swiftc': dict(gen=gen_swift,ext='.swift',cmd=lambda p:[SWIFTC,'-parse',p,'-o','/dev/null']),
}

def classify(rc, err):
    e = err.lower()
    if rc == 0: return 'ok'
    if rc == -6 or 'sigabrt' in e:
        return 'abort'
    if rc in (-7, -11) or 'segmentation fault' in e or 'sigsegv' in e or 'sigbus' in e or 'illegal instruction' in e:
        return 'crash'
    if 'stackoverflowerror' in e or 'stack overflow' in e or 'maximum call stack' in e or 'rangeerror' in e:
        return 'stack-limit'
    if rc < 0:
        return 'crash'
    return 'diagnostic'

import shutil
def available(name):
    need = {'javac': JAVAC, 'go gc': GO, 'swiftc': SWIFTC, 'csc': DOTNET,
            'tsc5': os.path.expanduser('~/d1/ts5/node_modules/typescript/bin/tsc')}.get(name)
    if need is None:
        need = {'g++':'g++','clang++':'clang++','rustc':'rustc','tsgo':'npx'}.get(name, name)
    return shutil.which(need) or os.path.exists(need)

def probe(name, depth, setarch=False, timeout=120):
    spec = SPECS[name]
    os.makedirs('/tmp/atlas_out', exist_ok=True)
    path = f'/tmp/atlas_out/probe{spec["ext"]}'
    open(path,'w').write(spec['gen'](depth))
    cmd = spec['cmd'](path)
    if setarch: cmd = ['setarch','-R']+cmd
    t = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env=ENV)
        return classify(r.returncode, r.stderr + r.stdout), time.time()-t
    except subprocess.TimeoutExpired:
        return 'timeout', time.time()-t

def find_wall(name, lo, hi):
    """lo compiles, hi fails. Bisect to unit resolution."""
    while hi - lo > 1:
        mid = (lo+hi)//2
        c,_ = probe(name, mid)
        if c == 'ok': lo = mid
        else: hi = mid
    return lo, hi

def band(name, lo, hi, trials=12, setarch=False):
    out = {}
    for d in range(lo, hi+1):
        ok = sum(1 for _ in range(trials) if probe(name, d, setarch)[0] == 'ok')
        out[d] = round(ok/trials, 3)
    return out

def main():
    results = {}
    # --- compilers with located walls (bisect fresh to unit resolution) ---
    ranges = {'javac': (500,1600), 'csc': (4750,6500), 'tsc5': (50,2000),
              'swiftc': (5000,20000)}
    if '--only' in sys.argv:
        only = sys.argv[sys.argv.index('--only')+1]
        ranges = {only: ranges[only]}
    for name,(a,b) in ranges.items():
        if not available(name):
            results[name] = {'error': 'toolchain not installed'}; continue
        # find a compiling lo and a failing hi inside (a,b)
        lo,hi = a,b
        c,_ = probe(name, lo)
        if c != 'ok':
            results[name] = {'error': f'lo={lo} not ok ({c})'}; continue
        l,h = find_wall(name, lo, hi)
        results[name] = {'wall': [l,h], 'band_aslr_on': band(name, max(l-2,l), h+2),
                         'band_aslr_off': band(name, max(l-2,l), h+2, setarch=True)}
        print(name, 'wall', l, h, results[name]['band_aslr_on'])
    # --- gc: no crash wall, measure time curve ---
    if available('go gc'):
        gc_curve = {}
        for d in [1000,5000,10000,20000]:
            c,dt = probe('go gc', d, timeout=240)
            gc_curve[d] = {'class': c, 's': round(dt,2)}
        results['go gc'] = {'time_wall_curve': gc_curve}
    # --- tsgo graceful reference point ---
    if available('tsgo'):
        c,dt = probe('tsgo', 4000)
        results['tsgo'] = {'probe_4000': {'class': c, 's': round(dt,2)}}
    out_path = os.path.join(ROOT,'data','phaseXII_atlas.json')
    if os.path.exists(out_path):
        try:
            prev = json.load(open(out_path)).get('compilers',{})
            prev.update(results); results = prev
        except Exception: pass
    with open(out_path,'w') as f:
        json.dump({'act':'XII-C','compilers':results}, f, indent=1)
    print(json.dumps(results, indent=1)[:3000])

if __name__ == '__main__':
    main()
