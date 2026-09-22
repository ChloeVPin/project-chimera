#!/usr/bin/env python3
"""Act XVIII-3: silent-accept scan, round 2 — extends the cross-language map.

Same experiment as run_crosslang.py: generate a nested-generic MISMATCH at
escalating depth, feed to each compiler, classify SILENT-ACCEPT (compiles
clean — wrong code accepted) / LOUD-ERROR (correctly rejected) / HANG /
CRASH. New languages: F#, VB.NET, OCaml, Scala, Kotlin, Zig, Haskell.
Each gets a 'control' (identical types) that must compile clean so a LOUD
result isn't misparsed.

Writes raw cells to data/phaseXVIII_crosslang2_raw.json; the committed
data/phaseXVIII_crosslang2.json is the curated summary (with annotations)
derived from it — do not overwrite.
"""
import json, os, subprocess, tempfile

T = os.path.expanduser
DOTNET = T('~/tools/dotnet/dotnet')
FSC = [DOTNET, T('~/tools/dotnet/sdk/8.0.425/FSharp/fsc.dll')]
VBC = [DOTNET, T('~/tools/dotnet/sdk/8.0.425/Roslyn/bincore/vbc.dll')]
CSC = [DOTNET, T('~/tools/dotnet/sdk/8.0.425/Roslyn/bincore/csc.dll')]
KOTLINC = T('~/tools/kotlinc/bin/kotlinc')
ZIG = T('~/tools/zig-linux-x86_64-0.13.0/zig')

def wrap(inner, n, leaf):
    """inner='W<x>' style nesting: W applied n times to leaf."""
    s = leaf
    for _ in range(n):
        s = inner.format(s)
    return s

CASES = {
    'fsharp': dict(
        good=lambda n: f'type W<\'T> = {{ v: \'T }}\nlet a: {wrap("W<{0}>", n, "int")} = Unchecked.defaultof<' + f'{wrap("W<{0}>", n, "int")}>\nlet b: {wrap("W<{0}>", n, "int")} = a\n',
        bad=lambda n: f'type W<\'T> = {{ v: \'T }}\nlet a: {wrap("W<{0}>", n, "int")} = Unchecked.defaultof<' + f'{wrap("W<{0}>", n, "int")}>\nlet b: {wrap("W<{0}>", n, "string")} = a\n',
        ext='.fs', cmd=lambda f: FSC + ['--targetprofile:netstandard', '--noframework', f],
        errpat=r'error'),
    'vbnet': dict(
        good=lambda n: f'Class W(Of T)\n Public v As T\nEnd Class\nModule M\n Sub Main()\n  Dim a As {wrap("W(Of {0})", n, "Integer")} = Nothing\n  Dim b As {wrap("W(Of {0})", n, "Integer")} = a\n End Sub\nEnd Module\n',
        bad=lambda n: f'Class W(Of T)\n Public v As T\nEnd Class\nModule M\n Sub Main()\n  Dim a As {wrap("W(Of {0})", n, "Integer")} = Nothing\n  Dim b As {wrap("W(Of {0})", n, "String")} = a\n End Sub\nEnd Module\n',
        ext='.vb', cmd=lambda f: VBC + ['/nologo', '/t:exe', f],
        errpat=r'error BC'),
    'ocaml': dict(
        good=lambda n: f'type \'a w = {{ v : \'a }}\nlet a : {wrap("({0}) w", n, "int")} = Obj.magic 0\nlet b : {wrap("({0}) w", n, "int")} = a\n',
        bad=lambda n: f'type \'a w = {{ v : \'a }}\nlet a : {wrap("({0}) w", n, "int")} = Obj.magic 0\nlet b : {wrap("({0}) w", n, "string")} = a\n',
        ext='.ml', cmd=lambda f: ['ocamlc', '-c', f],
        errpat=r'Error'),
    'scala': dict(
        good=lambda n: f'case class W[T](v: T)\nobject M {{\n  def a: {wrap("W[{0}]", n, "Int")} = ???\n  def b: {wrap("W[{0}]", n, "Int")} = a\n}}\n',
        bad=lambda n: f'case class W[T](v: T)\nobject M {{\n  def a: {wrap("W[{0}]", n, "Int")} = ???\n  def b: {wrap("W[{0}]", n, "String")} = a\n}}\n',
        ext='.scala', cmd=lambda f: ['scalac', f],
        errpat=r'error'),
    'kotlin': dict(
        good=lambda n: f'class W<T>(val v: T)\nval a: {wrap("W<{0}>", n, "Int")} = TODO() as {wrap("W<{0}>", n, "Int")}\nval b: {wrap("W<{0}>", n, "Int")} = a\n',
        bad=lambda n: f'class W<T>(val v: T)\nval a: {wrap("W<{0}>", n, "Int")} = TODO() as {wrap("W<{0}>", n, "Int")}\nval b: {wrap("W<{0}>", n, "String")} = a\n',
        ext='.kt', cmd=lambda f: [KOTLINC, f, '-d', '/tmp/kt_out.jar', '-nowarn'],
        errpat=r'error'),
    'zig': dict(
        good=lambda n: f'fn W(comptime T: type) type {{ return struct {{ v: T }}; }}\nconst A = {wrap("W({0})", n, "i32")};\nvar a: A = undefined;\nvar b: {wrap("W({0})", n, "i32")} = undefined;\npub fn main() void {{ b = a; }}\n',
        bad=lambda n: f'fn W(comptime T: type) type {{ return struct {{ v: T }}; }}\nconst A = {wrap("W({0})", n, "i32")};\nvar a: A = undefined;\nvar b: {wrap("W({0})", n, "i64")} = undefined;\npub fn main() void {{ b = a; }}\n',
        ext='.zig', cmd=lambda f: [ZIG, 'build-obj', f],
        errpat=r'error'),
    'haskell': dict(
        good=lambda n: f'main :: IO ()\nmain = return ()\nnewtype W a = W a\na :: {wrap("W ({0})", n, "Int")}\na = undefined\nb :: {wrap("W ({0})", n, "Int")}\nb = a\n',
        bad=lambda n: f'main :: IO ()\nmain = return ()\nnewtype W a = W a\na :: {wrap("W ({0})", n, "Int")}\na = undefined\nb :: {wrap("W ({0})", n, "String")}\nb = a\n',
        ext='.hs', cmd=lambda f: ['ghc', '-fno-code', f],
        errpat=r'error'),
}

if __name__ == "__main__":
    DEPTHS = [25, 100, 300]
    OUT = {}
    for lang, c in CASES.items():
        OUT[lang] = {}
        with tempfile.TemporaryDirectory() as td:
            for n in DEPTHS:
                for kind in ('good', 'bad'):
                    f = os.path.join(td, f'p{kind}{n}{c["ext"]}')
                    open(f, 'w').write(c[kind](n))
                    try:
                        r = subprocess.run(c['cmd'](f), capture_output=True, text=True, timeout=120,
                                           cwd=td, env={**os.environ, 'PATH': os.environ.get('PATH','')})
                        out = r.stderr + r.stdout
                        import re
                        has_err = re.search(c['errpat'], out) is not None
                        if kind == 'good':
                            v = 'OK-CLEAN' if r.returncode == 0 and not has_err else f'FALSE-POSITIVE(rc={r.returncode})'
                        else:
                            if r.returncode == 0 and not has_err:
                                v = 'SILENT-ACCEPT'
                            elif has_err:
                                v = 'LOUD-ERROR'
                            else:
                                v = f'CRASH(rc={r.returncode})'
                        OUT[lang][f'{n}/{kind}'] = v
                    except subprocess.TimeoutExpired:
                        OUT[lang][f'{n}/{kind}'] = 'HANG(>120s)'
                print(f'{lang:8}: ' + '  '.join(f'{k}={v}' for k, v in list(OUT[lang].items())[-2:]))
    json.dump({'act': 'XVIII-3', 'results': OUT}, open('data/phaseXVIII_crosslang2_raw.json', 'w'), indent=1)
    print('done')
