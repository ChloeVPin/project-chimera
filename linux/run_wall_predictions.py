#!/usr/bin/env python3
"""Act XIII-B — The Wall Equation, refined model.

Act XII gave walls at one stack size. The naive law N ~ S/f then FAILED
on g++: under RLIMIT_STACK(4M,4M) the wall was ~2.6k, not ~20.7k.
strace revealed the cause: the gcc driver calls
    prlimit64(RLIMIT_STACK, {min(64MB, rlim_max), rlim_max})
i.e. it RAISES the soft limit to 64MB whenever the hard limit allows.
So the effective stack is not rlim_cur but
    S_eff = max(rlim_cur, min(rlim_max, 64MB))   [g++ only]
Verified: 4M/4M->wall 2588, 8M/8M->5184, 16M/16M->10375 (frame ~1617B);
8M/inf -> 41521 (=64MB/1617B); 128M/128M survives 45k+.
clang/rustc/swiftc drivers do NOT self-raise (strace-verified).

Here we calibrate each compiler's frame cost at ONE stack size, then
predict walls at stack sizes never measured, and bisect-verify each.
"""
import json, os, resource, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_atlas as A
import run_survival_curves as S

MB = 1024 * 1024
M64 = 64 * MB

SPEC_X = {
    'g++':    dict(gen=S.gen_cpp, ext='.cpp',
                   cmd=lambda p:['g++','-std=c++20','-fsyntax-only','-ftemplate-depth=200000',p]),
    'clang++':dict(gen=S.gen_cpp, ext='.cpp',
                   cmd=lambda p:['clang++','-std=c++20','-fsyntax-only','-ftemplate-depth=200000',p]),
    'rustc':  dict(gen=S.gen_rust,ext='.rs',
                   cmd=lambda p:['rustc','--crate-type=lib','--edition=2021',p]),
    'swiftc': dict(A.SPECS['swiftc']),
}

def run_with(cmd_fn, path, soft=None, hard=None, env_extra=None, timeout=300):
    cmd = cmd_fn(path)
    preexec = None
    if soft is not None:
        def lim(s=soft, h=hard):
            resource.setrlimit(resource.RLIMIT_STACK, (s, h))
        preexec = lim
    env = dict(A.ENV)
    if env_extra:
        env.update(env_extra)
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           env=env, preexec_fn=preexec, timeout=timeout)
        return A.classify(r.returncode, r.stdout + r.stderr), r.returncode
    except subprocess.TimeoutExpired:
        return 'timeout', None

def measure_wall(spec, soft=None, hard=None, env_extra=None, lo=200, hi=200000):
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 'probe' + spec['ext'])
        def fails(d):
            open(p, 'w').write(spec['gen'](d))
            cls, _ = run_with(spec['cmd'], p, soft, hard, env_extra)
            return cls in ('crash', 'abort', 'stack-limit')
        if not fails(hi):
            return None
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if fails(mid): hi = mid
            else: lo = mid
        return hi - 1   # last passing depth

def gxx_eff_stack(soft, hard):
    """gcc driver rule: raise rlim_cur to min(rlim_max, 64MB) when cur < that."""
    INF = resource.RLIM_INFINITY
    cap = M64 if hard == INF else min(hard, M64)
    return max(soft, cap)

def main():
    out = {'model': 'wall ~ S_eff / frame_bytes',
           'g++_driver_rule': 'S_eff = max(rlim_cur, min(rlim_max, 64MB))',
           'calibration': {}, 'predictions': {}}

    # --- calibrate frame costs at one stack point each ---
    cal = {}
    fc_g = None; fc_c = None; fc_r = None; fc_s = None

    w = measure_wall(SPEC_X['g++'], soft=4*MB, hard=4*MB)
    cal['g++'] = w; fc_g = 4*MB / w; out['calibration']['g++ @4M/4M'] = w
    print(f'g++ calib @4M/4M wall={w} -> frame {fc_g:.0f}B', flush=True)

    w = measure_wall(SPEC_X['clang++'], soft=4*MB, hard=4*MB)
    cal['clang++'] = w; fc_c = 4*MB / w; out['calibration']['clang++ @4M/4M'] = w
    print(f'clang++ calib @4M/4M wall={w} -> frame {fc_c:.0f}B', flush=True)

    w = measure_wall(SPEC_X['rustc'], env_extra={'RUST_MIN_STACK': str(4*MB)})
    cal['rustc'] = w; fc_r = 4*MB / w; out['calibration']['rustc @4M'] = w
    print(f'rustc calib @4M wall={w} -> frame {fc_r:.0f}B', flush=True)

    w = measure_wall(SPEC_X['swiftc'], soft=4*MB, hard=4*MB)
    cal['swiftc'] = w; fc_s = 4*MB / w; out['calibration']['swiftc @4M/4M'] = w
    print(f'swiftc calib @4M/4M wall={w} -> frame {fc_s:.0f}B', flush=True)

    # --- predict & verify at unseen stack sizes ---
    cases = [
        # g++: effective stack follows driver rule
        ('g++_8M_8M',   'g++',    dict(soft=8*MB,   hard=8*MB),   gxx_eff_stack(8*MB, 8*MB)/fc_g),
        ('g++_16M_16M', 'g++',    dict(soft=16*MB,  hard=16*MB),  gxx_eff_stack(16*MB, 16*MB)/fc_g),
        ('g++_32M_32M', 'g++',    dict(soft=32*MB,  hard=32*MB),  gxx_eff_stack(32*MB, 32*MB)/fc_g),
        ('g++_128M_128M','g++',   dict(soft=128*MB, hard=128*MB), gxx_eff_stack(128*MB, 128*MB)/fc_g),
        ('g++_8M_inf',  'g++',    dict(soft=8*MB,   hard=resource.RLIM_INFINITY),
                                    gxx_eff_stack(8*MB, resource.RLIM_INFINITY)/fc_g),
        # clang/swiftc: no self-raise -> effective stack = rlim_cur
        ('clang_8M',    'clang++',dict(soft=8*MB,   hard=8*MB),   8*MB/fc_c),
        ('clang_16M',   'clang++',dict(soft=16*MB,  hard=16*MB),  16*MB/fc_c),
        ('rustc_8M',    'rustc',  dict(soft=8*MB),                8*MB/fc_r),
        ('rustc_16M',   'rustc',  dict(soft=16*MB),               16*MB/fc_r),
        ('swiftc_8M',   'swiftc', dict(soft=8*MB,   hard=8*MB),   8*MB/fc_s),
        ('swiftc_16M',  'swiftc', dict(soft=16*MB,  hard=16*MB),  16*MB/fc_s),
    ]
    for name, key, kw, pred in cases:
        spec = SPEC_X[key]
        env = {'RUST_MIN_STACK': str(kw['soft'])} if key == 'rustc' else None
        soft = kw.get('soft') if key != 'rustc' else None
        lo = max(200, int(pred*0.6)); hi = int(pred*1.5)
        print(f'== {name}: predicted ~{pred:.0f}', flush=True)
        w = measure_wall(spec, soft=soft, hard=kw.get('hard'),
                         env_extra=env, lo=lo, hi=hi)
        rec = {'predicted': round(pred), 'measured': w}
        if w:
            rec['err_pct'] = round(abs(w - pred)/pred*100, 2)
            print(f'   measured {w} err {rec["err_pct"]}%', flush=True)
        else:
            rec['err_pct'] = None
            print('   no wall in range', flush=True)
        out['predictions'][name] = rec

    p = os.path.join(A.ROOT, 'data', 'phaseXIII_predictions.json')
    json.dump({'act': 'XIII-B', 'results': out}, open(p, 'w'), indent=1)
    print(json.dumps(out, indent=1))

if __name__ == '__main__':
    main()
