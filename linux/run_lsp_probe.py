#!/usr/bin/env python3
"""Act XVI-A — the silent-accept hole reaches the editor.

Drives `tsgo --lsp --stdio` over real LSP JSON-RPC (initialize → ACK
client/registerCapability → didOpen → pull textDocument/diagnostic).

Result measured:
  tsgo-stock  depth=10  -> 1 diagnostic (TS2322)          pipeline works
  tsgo-stock  depth=150 -> 0 diagnostics                  SILENT ACCEPT IN EDITOR
  tsgo-unfused depth=150 -> 1 diagnostic (TS2322)         correct answer

The relater's 100-deep fuse (TernaryMaybe swallowed) therefore affects the LSP
path every user sees — deep wrong code gets no red squiggles.
"""
import json, os, subprocess, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBES = os.path.join(ROOT, 'linux', 'probes')

def deep_mismatch(n):
    l, r = 'number', 'string'
    for _ in range(n):
        l, r = f'Array<{l}>', f'Array<{r}>'
    return f'declare const src: {r};\nconst x: {l} = src;\n'

def lsp_diag(binary, text):
    p = subprocess.Popen([binary, '--lsp', '--stdio'],
                         stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                         stderr=subprocess.DEVNULL)
    def send(msg):
        b = json.dumps(msg)
        p.stdin.write(f'Content-Length: {len(b)}\r\n\r\n{b}'.encode()); p.stdin.flush()
    def read_msg():
        h = {}
        while True:
            line = p.stdout.readline()
            if not line: return None
            line = line.decode().strip()
            if line == '': break
            if ':' in line:
                k, v = line.split(':', 1); h[k.strip().lower()] = v.strip()
        return json.loads(p.stdout.read(int(h.get('content-length', 0))))
    fp = os.path.join(PROBES, 'LSP_probe.ts')
    open(fp, 'w').write(text)
    uri = 'file://' + os.path.abspath(fp)
    send({'jsonrpc': '2.0', 'id': 1, 'method': 'initialize',
          'params': {'processId': None, 'rootUri': 'file://' + PROBES,
                     'capabilities': {'workspace': {'didChangeConfiguration':
                                      {'dynamicRegistration': True}}},
                     'workspaceFolders': None}})
    deadline = time.time() + 90
    try:
        while time.time() < deadline:
            m = read_msg()
            if m is None:
                return 'EOF'
            if 'method' in m and 'id' in m:
                send({'jsonrpc': '2.0', 'id': m['id'], 'result': None})
                continue
            if m.get('id') == 1:
                send({'jsonrpc': '2.0', 'method': 'initialized', 'params': {}})
                send({'jsonrpc': '2.0', 'method': 'textDocument/didOpen',
                      'params': {'textDocument': {'uri': uri, 'languageId': 'typescript',
                                                  'version': 1, 'text': text}}})
                time.sleep(1.5)
                send({'jsonrpc': '2.0', 'id': 2, 'method': 'textDocument/diagnostic',
                      'params': {'textDocument': {'uri': uri}}})
                continue
            if m.get('id') == 2:
                return m.get('result')
    finally:
        p.terminate()
    return 'TIMEOUT'

def main():
    res = {}
    for name, n, binary in [
            ('stock-10', 10, os.path.expanduser('~/tools/tsgo-stock')),
            ('stock-150', 150, os.path.expanduser('~/tools/tsgo-stock')),
            ('unfused-150', 150, os.path.expanduser('~/tools/tsgo-unfused'))]:
        r = lsp_diag(binary, deep_mismatch(n))
        items = r.get('items') if isinstance(r, dict) else r
        res[name] = {'items': items}
        first = items[0].get('message', '')[:90] if items else None
        print(f'{name}: {len(items) if items is not None else r} diagnostics'
              + (f' — {first}' if first else ''))
    out = os.path.join(ROOT, 'data', 'phaseXVI_lsp.json')
    json.dump({'act': 'XVI-A', 'results': res}, open(out, 'w'), indent=1)
    print('wrote', out)

if __name__ == '__main__':
    main()
