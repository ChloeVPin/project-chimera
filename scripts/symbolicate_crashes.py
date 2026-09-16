#!/usr/bin/env python3
"""
Project Chimera: Phase 18 - Native LLDB & Kernel Symbolication and Register Extraction
Parses Darwin kernel crash reports (IPS) and extracts fault registers, backtraces,
and memory protection fault addresses for rustc SIGBUS and Clang SIGILL crashes.
"""

import os
import glob
import json
import subprocess
from pathlib import Path

CRASH_REPORTS_DIR = Path.home() / "Library/Logs/DiagnosticReports"
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
REPORTS_DIR = PROJECT_DIR / "reports"

def demangle(sym: str) -> str:
    if not sym:
        return "<unknown>"
    try:
        res = subprocess.run(["c++filt", sym], capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except Exception:
        return sym

def find_latest_ips(binary_name: str) -> Path | None:
    pattern = str(CRASH_REPORTS_DIR / f"{binary_name}-*.ips")
    files = glob.glob(pattern)
    if not files:
        return None
    # Sort by modification time descending
    files.sort(key=os.path.getmtime, reverse=True)
    return Path(files[0])

def parse_ips(ips_path: Path):
    with open(ips_path, "r", encoding="utf-8") as f:
        first_line = f.readline()
        rest = f.read()
    
    header = json.loads(first_line)
    body = json.loads(rest)
    return header, body

def extract_crash_telemetry(binary_name: str):
    ips_path = find_latest_ips(binary_name)
    if not ips_path:
        raise FileNotFoundError(f"No IPS crash report found for {binary_name} in {CRASH_REPORTS_DIR}")
    
    header, body = parse_ips(ips_path)
    exception = body.get("exception", {})
    faulting_thread_idx = body.get("faultingThread", 0)
    threads = body.get("threads", [])
    
    if faulting_thread_idx >= len(threads):
        raise IndexError(f"Faulting thread {faulting_thread_idx} not found in threads list")
    
    thread = threads[faulting_thread_idx]
    thread_state = thread.get("threadState", {})
    frames = thread.get("frames", [])
    
    # Extract register values
    regs = {}
    if "pc" in thread_state:
        regs["pc"] = f"0x{thread_state['pc']['value']:016x}"
    if "sp" in thread_state:
        regs["sp"] = f"0x{thread_state['sp']['value']:016x}"
    if "fp" in thread_state:
        regs["fp"] = f"0x{thread_state['fp']['value']:016x}"
    if "lr" in thread_state:
        regs["lr"] = f"0x{thread_state['lr']['value']:016x}"
    if "cpsr" in thread_state:
        regs["cpsr"] = f"0x{thread_state['cpsr']['value']:08x}"
    if "far" in thread_state:
        regs["far"] = f"0x{thread_state['far']['value']:016x}"
    if "esr" in thread_state:
        esr_val = thread_state['esr']['value']
        esr_desc = thread_state['esr'].get('description', '')
        regs["esr"] = f"0x{esr_val:08x} ({esr_desc})"
    
    # GPRs
    gprs = {}
    for i, reg in enumerate(thread_state.get("x", [])):
        gprs[f"x{i}"] = f"0x{reg['value']:016x}"
    regs["gpr"] = gprs
    
    # Demangle frames
    parsed_frames = []
    used_images = body.get("usedImages", [])
    for idx, f in enumerate(frames[:25]):
        raw_sym = f.get("symbol", "")
        demangled_sym = demangle(raw_sym)
        img_idx = f.get("imageIndex", 0)
        img_name = used_images[img_idx].get("name", "unknown") if img_idx < len(used_images) else "unknown"
        parsed_frames.append({
            "frame": idx,
            "image": img_name,
            "symbol": demangled_sym,
            "offset": f.get("symbolLocation", 0)
        })
    
    return {
        "binary": binary_name,
        "report_file": ips_path.name,
        "timestamp": header.get("timestamp"),
        "os_version": header.get("os_version"),
        "cpu": body.get("cpuType"),
        "exception": exception,
        "faulting_thread": faulting_thread_idx,
        "registers": regs,
        "backtrace": parsed_frames
    }

def format_register_block(regs: dict) -> str:
    lines = []
    lines.append(f"    pc = {regs.get('pc', 'N/A')}    lr = {regs.get('lr', 'N/A')}    sp = {regs.get('sp', 'N/A')}    fp = {regs.get('fp', 'N/A')}")
    lines.append(f"   far = {regs.get('far', 'N/A')}   esr = {regs.get('esr', 'N/A')}  cpsr = {regs.get('cpsr', 'N/A')}")
    lines.append("")
    gpr = regs.get("gpr", {})
    # 4 per line
    for i in range(0, 29, 4):
        chunk = []
        for j in range(i, min(i + 4, 29)):
            reg_name = f"x{j}"
            chunk.append(f"{reg_name:>3} = {gpr.get(reg_name, 'N/A')}")
        lines.append("   " + "  ".join(chunk))
    return "\n".join(lines)

def format_backtrace_table(frames: list) -> str:
    lines = []
    lines.append("| Frame | Binary / Image | Demangled Symbol | Offset |")
    lines.append("|---|---|---|---|")
    for f in frames:
        sym_clean = f['symbol'].replace("|", "\\|")
        lines.append(f"| `#{f['frame']}` | `{f['image']}` | `{sym_clean}` | `+{f['offset']}` |")
    return "\n".join(lines)

def update_rustc_report(telemetry: dict):
    report_file = REPORTS_DIR / "rustc_sigbus_issue.md"
    content = report_file.read_text(encoding="utf-8")
    
    reg_dump = format_register_block(telemetry["registers"])
    bt_table = format_backtrace_table(telemetry["backtrace"])
    exc = telemetry["exception"]
    
    section = f"""## 5. Live Darwin Kernel Register Dump & Symbolicated Backtrace

The fault occurred when `rustc` hit the thread stack guard boundary:
- **Exception Code:** `{exc.get('type')}` (`{exc.get('signal')}`)
- **Subtype / Fault Address:** `{exc.get('subtype')}`
- **Message:** `{exc.get('message')}`
- **Crash Artifact:** `~/Library/Logs/DiagnosticReports/{telemetry['report_file']}`

### 5.1 Register State at Crash (`ARM_THREAD_STATE64`)
```text
{reg_dump}
```

### 5.2 Symbolicated Activation Frames (Stack Exhaustion Trajectory)
{bt_table}
"""
    # Replace Section 5 if exists or insert before Remediation
    if "## 5. Live Darwin Kernel Register Dump" in content:
        # already present, update
        parts = content.split("## 5. Live Darwin Kernel Register Dump")
        remediation = parts[1].split("## 6. Suggested Remediation", 1)
        if len(remediation) > 1:
            content = parts[0] + section + "\n## 6. Suggested Remediation" + remediation[1]
        else:
            content = parts[0] + section
    elif "## 5. Suggested Remediation" in content:
        content = content.replace("## 5. Suggested Remediation", section + "\n## 6. Suggested Remediation")
    else:
        content += "\n\n" + section

    report_file.write_text(content, encoding="utf-8")
    print(f"Updated {report_file}")

def update_clang_report(telemetry: dict):
    report_file = REPORTS_DIR / "clang_sigill_issue.md"
    content = report_file.read_text(encoding="utf-8")
    
    reg_dump = format_register_block(telemetry["registers"])
    bt_table = format_backtrace_table(telemetry["backtrace"])
    exc = telemetry["exception"]
    
    section = f"""## 5. Live Darwin Kernel Register Dump & Symbolicated Backtrace

The fault occurred when `clang` hit the thread stack guard boundary during recursive template-id descent:
- **Exception Code:** `{exc.get('type')}` (`{exc.get('signal')}`)
- **Subtype / Fault Address:** `{exc.get('subtype')}`
- **Message:** `{exc.get('message')}`
- **Crash Artifact:** `~/Library/Logs/DiagnosticReports/{telemetry['report_file']}`

### 5.1 Register State at Crash (`ARM_THREAD_STATE64`)
```text
{reg_dump}
```

### 5.2 Symbolicated Activation Frames (Stack Exhaustion Trajectory)
{bt_table}
"""
    if "## 5. Live Darwin Kernel Register Dump" in content:
        parts = content.split("## 5. Live Darwin Kernel Register Dump")
        remediation = parts[1].split("## 6. Suggested Remediation", 1)
        if len(remediation) > 1:
            content = parts[0] + section + "\n## 6. Suggested Remediation" + remediation[1]
        else:
            content = parts[0] + section
    elif "## 5. Suggested Remediation" in content:
        content = content.replace("## 5. Suggested Remediation", section + "\n## 6. Suggested Remediation")
    else:
        content += "\n\n" + section

    report_file.write_text(content, encoding="utf-8")
    print(f"Updated {report_file}")

def main():
    print("================================================================================")
    print(" Project Chimera - Phase 18: Native Symbolication & Register State Extraction")
    print("================================================================================")
    
    results = {}
    
    print("\n[1/2] Processing rustc crash report...")
    rustc_telem = extract_crash_telemetry("rustc")
    results["rustc"] = rustc_telem
    print(f"  -> Extracted {len(rustc_telem['registers']['gpr'])} registers, {len(rustc_telem['backtrace'])} frames from {rustc_telem['report_file']}")
    update_rustc_report(rustc_telem)
    
    print("\n[2/2] Processing clang crash report...")
    clang_telem = extract_crash_telemetry("clang")
    results["clang"] = clang_telem
    print(f"  -> Extracted {len(clang_telem['registers']['gpr'])} registers, {len(clang_telem['backtrace'])} frames from {clang_telem['report_file']}")
    update_clang_report(clang_telem)
    
    out_json = DATA_DIR / "phase18_symbolicated_crashes.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved structured telemetry to {out_json}")
    print("================================================================================")
    print(" Phase 18 Complete.")
    print("================================================================================")

if __name__ == "__main__":
    main()
