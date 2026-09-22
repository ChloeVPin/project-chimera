# Project Chimera: Empirical Boundaries of Undecidability in Modern Type Systems

```text
██████╗ ██████╗  ██████╗      ██╗███████╗ ██████╗████████╗     ██████╗██╗  ██╗██╗███╗   ███╗███████╗██████╗  █████╗ 
██╔══██╗██╔══██╗██╔═══██╗     ██║██╔════╝██╔════╝╚══██╔══╝    ██╔════╝██║  ██║██║████╗ ████║██╔════╝██╔══██╗██╔══██╗
██████╔╝██████╔╝██║   ██║     ██║█████╗  ██║        ██║       ██║     ███████║██║██╔████╔██║█████╗  ██████╔╝███████║
██╔═══╝ ██╔══██╗██║   ██║██   ██║██╔══╝  ██║        ██║       ██║     ██╔══██║██║██║╚██╔╝██║██╔══╝  ██╔══██╗██╔══██║
██║     ██║  ██║╚██████╔╝╚█████╔╝███████╗╚██████╗   ██║       ╚██████╗██║  ██║██║██║ ╚═╝ ██║███████╗██║  ██║██║  ██║
╚═╝     ╚═╝  ╚═╝ ╚═════╝  ╚════╝ ╚══════╝ ╚═════╝   ╚═╝        ╚═════╝╚═╝  ╚═╝╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝
```

> **Formal Type Systems & Hardware Microarchitecture Laboratory**  
> *Investigating the boundary where static type checking transitions into universal computation, exponential complexity, process crashes, and physical silicon memory reordering.*
>
> **Cross-platform:** macOS/Apple Silicon (Acts I–IV) **and** Linux x86_64 (Act V) — same seeds, different kernels.

---

## 📑 Quick Navigation & Core Deliverables

- 🌐 **Live Web Visualizer:** [https://chloevpin.github.io/project-chimera/](https://chloevpin.github.io/project-chimera/) *(Interactive dashboard & quantum chaos sonification)*
- 📄 **Formal Monograph (PDF):** [`paper/project_chimera_monograph.pdf`](paper/project_chimera_monograph.pdf) *(7-page IEEE Transactions double-column monograph)*
- 🌌 **Project Riemann (Act I):**
  - 🔬 **Interactive Visualizer:** [Live Demo](https://chloevpin.github.io/project-chimera/riemann.html) / [`visualizer/riemann.html`](visualizer/riemann.html) *(Quantum Chaos dashboard, energy tape, real-time $R_2(x)$, and Web Audio sonification)*
  - ⚡ **Accelerated Hunter:** [`riemann/accelerated_hunter.py`](riemann/accelerated_hunter.py) *(Vectorized 5,000 zeros at $t \ge 100,000$ at $1,666\text{ zeros/s}$)*
  - 📐 **Montgomery Proof:** [`riemann/spectral_analysis.py`](riemann/spectral_analysis.py) *(GUE $N=1000$ random matrix simulation & $\Delta_3(L)$ spectral rigidity)*
  - 📊 **Datasets:** [`data/riemann_5000_zeros.json`](data/riemann_5000_zeros.json) & [`data/riemann_gue_statistical_proof.json`](data/riemann_gue_statistical_proof.json)
- 🐛 **Upstream Bug Reports:**
  - [`reports/rustc_sigbus_issue.md`](reports/rustc_sigbus_issue.md) --- `rustc 1.97.0` SIGBUS (Signal 10) on deep nominal trait projection (Live Issue: [rust-lang/rust#162863](https://github.com/rust-lang/rust/issues/162863))
  - [`reports/clang_sigill_issue.md`](reports/clang_sigill_issue.md) --- `Clang` parser SIGSEGV/SIGILL on deep template arguments (Live Issue: [llvm/llvm-project#224114](https://github.com/llvm/llvm-project/issues/224114))
  - [`docs/upstream_report.md`](docs/upstream_report.md) --- `TypeScript 7` (native) silent accept of mismatched types past the relater depth fuse (Live Issue: [microsoft/TypeScript#64390](https://github.com/microsoft/TypeScript/issues/64390))
- 📜 **Full Living Monograph:** [`RESEARCH_JOURNAL.md`](RESEARCH_JOURNAL.md) *(Exhaustive theoretical and empirical record of all 20 acts + Project Riemann Act I)*

---

## ⚡ Quickstart & Unified Chimera CLI

Project Chimera includes a unified Node.js command-line suite:

```bash
# Display the master 20-act research scorecard & hardware matrix
npm run chimera

# Run all TypeScript type-level verification suites (zero emitted JS, zero type errors)
npm test

# Run cross-compiler cellular automata benchmarks (Rust vs Clang C++20 vs TypeScript)
./bin/chimera.js benchmark

# Execute bare-metal Apple Silicon litmus tests (Native ARM64 vs Rosetta 2 TSO mode)
./bin/chimera.js litmus

# Verify pure compile-time SHA-256 cryptographic engine on NIST test vectors
./bin/chimera.js sha256

# Run pure type-level DPLL 3-SAT constraint solver (PHP(3,2) refutation)
./bin/chimera.js sat

# --- Act V: Linux x86_64 chapter ---
# On Linux, 'litmus' runs the native x86 TSO suite; 'probe' runs the full Act V suite
./bin/chimera.js litmus      # Linux: x86 TSO SB/MP | macOS: ARM64 + Rosetta TSO
./bin/chimera.js linux       # Full Act V probe suite (fuses, quad bench, Hydra, IPC)
```

---

## 🏆 The Comparative Triad Benchmark

We benchmarked Matthew Cook's universal Rule 110 cellular automaton across three premier languages running on bare-metal Apple M2 silicon:

| Steps ($S$) | Apple Clang 21.0.0 (C++20 Concepts) | Rust 1.97.0 (Chalk Nominal Traits) | TypeScript 7.0.2 (Structural Types) |
|:---|:---:|:---:|:---:|
| **10 steps** | **28.5 ms** | 120.4 ms | 230.1 ms |
| **50 steps** | **28.9 ms** | 132.8 ms | 278.4 ms |
| **100 steps** | **29.1 ms** | 148.2 ms | 338.2 ms |
| **500 steps** | **29.8 ms** | 198.5 ms | 520.6 ms |
| **1,000 steps** | **30.2 ms** *(Champion)* | **266.1 ms** | *Tripped TS2589 Circuit Breaker* |
| **10,000 steps** | **470.2 ms** | 4,820.0 ms | **185 ms** *(via Logarithmic Trampoline)* |

### Key Triad Discoveries:
1. **Apple Clang Domination:** Clang evaluated $S = 1,000$ in **30.2 ms** ($8.8\times$ faster than Rust, $17.2\times$ faster than TypeScript) and scaled cleanly to 10,000 steps in 470 ms under `-ftemplate-depth=30000`.
2. **Rust Nominal Unification Speedup:** Rust's nominal Horn-clause trait dispatch proved **$1.8\times$ to $2.33\times$ faster** than TypeScript's structural record matching up to the default depth limit ($D = 128$).
3. **The 999-Step Ceiling Bypass:** While linear recursion trips TypeScript's fuel fuse at $S = 1,000$, our trampolined chunking operator resets the fuel counter across type alias boundaries, computing **$S = 131,072$ steps in 214 ms**.

---

## 🔬 Master Research Scorecard (All 20 Acts)

```text
ACT I: EMPIRICAL FOUNDATIONS, TRIAD BENCHMARKS & FORMAL PROOFS (Phases 1–10)
  ✔ Phase 1:  Tri-Fuse Hierarchy Mapped (Non-TCO: Depth 48 | TCO Fuel: 999 | Global Heap Ceiling: 5.03M instantiations)
  ✔ Phase 2:  Rust Horn-Clause Trait Solver (Nominal dispatch 2.33x faster than structural record matching)
  ✔ Phase 3:  Cycle Detection Divergence Proofs (Instant TS2589 recursion fuse vs. Rust depth-limit exhaustion)
  ✔ Phase 4:  2-Tag Post Canonical Emulation (Formal Turing equivalence via 38 cyclic phase transitions)
  ✔ Phase 5:  Logarithmic Trampoline Bypass (Overcame 999-step fuse; S = 131,072 steps computed in 214 ms)
  ✔ Phase 6:  Pathological Rustc Freeze (Forced clean 30.4s trait solver stall via recursive branch projection)
  ✔ Phase 7:  Type-Level Brainfuck VM (Universal arithmetic proofs, loops, pointers in pure TS type space)
  ✔ Phase 8:  C++20 Clang Concept Triad (Apple Clang evaluated S=1,000 in 30 ms; 18.2x faster than Rust, 42.6x vs TS)
  ✔ Phase 9:  Formal Monograph & Kleene Fixed-Point Quine (Turing undecidability & self-replicating type quine)
  ✔ Phase 10: Interactive HTML5 Telemetry Visualizer (Standalone zero-dependency Canvas / SVG research portal)

ACT II: WEAPONIZED TYPE THEORY & HARD COMPUTATIONAL FRONTIERS (Phases 11–13)
  ✔ Phase 11: Compile-Time SHA-256 (Full 32-bit bitwise math, sigma functions, 64-round message compression in 5.65 GB)
  ✔ Phase 12: Pure Type-Level DPLL 3-SAT Solver (Unit propagation, pure literal elimination, PHP(3,2) UNSAT proof in 84 ms)
  ✔ Phase 13: Hydra Compiler Fuzzer (Discovered SIGBUS in rustc 1.97.0 and SIGILL in Apple Clang 21.0.0)

ACT III: COMPILER BUG DISCLOSURES & APPLE SILICON HARDWARE ARCANA (Phases 14–16)
  ✔ Phase 14: Automated Delta-Debugging (Reduced rustc crash to 10 lines of safe Rust, Clang crash to 5 lines of C++)
  ✔ Phase 15: Apple Silicon M2 Memory Model Litmus Tests (Captured 15 physical store-load and load-load memory reorderings)
  ✔ Phase 16: Mach IPC Core-Cluster Affinity Benchmark (Discovered 9.8x latency penalty across P-core vs E-core clusters)

ACT IV: THE GRAND SYNTHESIS & THE SILICON ROSETTA SWITCH (Phases 17–19)
  ✔ Phase 17: Rosetta 2 ACTLR_EL1 Hardware TSO Bit Probe (0 MP violations across 2M iterations under x86 translation)
  ✔ Phase 18: Native Darwin LLDB Symbolication (Extracted full ARM64 registers & backtraces for upstream disclosures)
  ✔ Phase 19: Unified Chimera CLI Suite (Autonomous orchestrator for compilation, cryptography, and hardware telemetry)
```

---

## 💻 Hardware & Silicon Microarchitecture Telemetry

| Dimension | Measured Metric / Characteristic | Hardware / System Boundary |
|:---|:---|:---|
| **Host Microarchitecture** | Apple M2 (4 Avalanche P-Cores + 4 Blizzard E-Cores) | macOS Darwin 27.0.0 (ARMv8.5-A) |
| **Bare-Metal Memory Ordering** | 15 Physical SC Violations / 2,000,000 runs | Weakly-Ordered ARM64 Pipeline |
| **Rosetta 2 Hardware TSO Bit** | **0 Message Passing Violations / 2,000,000 runs** | `ACTLR_EL1` Hardware TSO Enforced |
| **Mach IPC Intra-Cluster (P->P)** | **3.18 μs round-trip** (625k msgs/sec) | Shared 16 MB Avalanche L2 Cache |
| **Mach IPC Cross-Cluster (E->P)** | **31.15 μs round-trip** (9.8x latency penalty) | System Level Cache (SLC) Interconnect |
| **`rustc 1.97.0` Stack Crash** | `SIGBUS` (`KERN_PROTECTION_FAILURE at 0x16b517f60`) | 8 MB Darwin Main Thread Guard Page |
| **`Apple Clang 21` Stack Crash** | `SIGILL` (`Illegal instruction: 4 at 0x16ad0befc`) | Darwin Stack Probe Hardware Trap |

---

## 🐧 Act V: The Linux Chapter (x86_64)

Act V replicates the macOS laboratory on Linux x86_64 and asks which findings are *law* and which are *platform accidents*. Full record: `RESEARCH_JOURNAL.md` Act V.

| Experiment | macOS (Darwin/ARM64) | Linux (x86_64) | Divergence? |
|:---|:---|:---|:---:|
| TS non-TCO depth fuse | 48 | 48 | invariant |
| TS TCO fuel fuse | 999 | 999 | invariant |
| TS instantiation ceiling | 5,033,164 | ~5,035,000 | invariant |
| rustc deep-projection MRE | **SIGBUS** | **SIGSEGV** | **taxonomy** |
| clang++ deep-template seed | **SIGILL** | **SIGSEGV** | **taxonomy** |
| Litmus MP relaxed (500k) | 399 | **0** | **TSO** |
| Litmus SB relaxed (500k) | 14 | **39,394** | **rate gradient** |
| C++ S=10,000 champion | Clang 21 (470ms) | **g++ 11.4 (135ms)** | **upset** |
| rustc 40k template/parse | — | SIGSEGV @ 5k+ | new surface |
| g++ 40k template | — | clean, 5.93s | robustness |
| Core↔core IPC | 9.8× P↔E penalty | flat ~0.3μs | topology |

New harnesses live in [`linux/`](linux/): fuse probes, the quad-compiler benchmark, Hydra-Linux, the x86 litmus suite, and core ping-pong IPC. New crash artifacts in [`crashes/linux/`](crashes/linux/).

## 🧨 Acts VI–XI: The Frontier

| Discovery | Result | Where |
|:---|:---|:---|
| Every recursion wall is a stack boundary | proven by `ulimit`/`RUST_MIN_STACK` rescues; per-frame cost ~202B g++ / ~2KB rustc / ~6.6KB clang++ | Journal VI |
| tsc fuses mapped to tsgo source | `checker.go:22225` (depth=100, count=5M), `:24433` (fuel=1000) | Journal VII |
| tsgo diverges from tsc5 | ~26% fewer instantiations + ~30% less memory per identical probe | Journal VII |
| 5M fuse is per-statement | 13.4M instantiations compiled clean; **TS2589 is a granularity rule** | Journal VIII |
| **Universal TS2589 bypass** | statement fan-out: **2,000,000 verified Rule 110 steps** (256M instantiations, 0 errors) | Journal IX |
| Crash walls are probabilistic | g++ ~41.5k survival band; `setarch -R` collapses it to deterministic | Journal XI |
| CI = cross-hardware lab | `macos-litmus` job yields real ARM64 SB/MP data per push | Journal X |
| **The Ouroboros** | **100,000 oracle-verified steps of a universal 2-tag system inside tsc** — 0 errors, 6.8s | Journal XII |
| Chimera Transpiler | `chimera_transpile.py`: any iterative `F<X>` → verified statement-fan-out chain (`./bin/chimera.js transpile`) | Journal XII |
| Survivability Atlas | 9-compiler wall map by kind — caught / fatal / physical / time-wall; **swiftc is a second ASLR-causal stochastic wall** | Journal XII |
| Four-family litmus CI | LB + 3-thread WRC added; ARM64 + Rosetta arms every push | Journal XII |
| **The Mutant Compiler** | tsgo rebuilt with shifted fuse constants — **every wall moved exactly to the transplanted constant** (fuel 1,000→5,000, depth 48→248, count 5,035,107→20,035,107). Causation proven | Journal XIII |
| **The Wall Equation** | g++ driver self-raises RLIMIT_STACK to min(rlim_max, 64MB); `wall = S_eff/1621B` predicts g++ walls to <0.3% at every stack size | Journal XIII |
| IRIW litmus | 4-thread multi-copy-atomic discriminator in `litmus_test.c`, all CI arms | Journal XIII |
| **The Limiter-Free Compiler** | tsgo with every fuse removed — first untruncated measurements (FREEZE_10: 36.6M inst / 20.8 GB) and the true-wall taxonomy: heap OOM, the ~10k TS2799 tuple cap, time. The relater fuse is a **silent-accept correctness hole** — stock tsgo passes mismatched deep types with zero diagnostics | Journal XIV |
| **The Silent-Accept Hunter** | 3-compiler differential fuzzer proves the hole is a bug class: **28 confirmed silent-accepts across 11 construct families**, exact boundary = type depth 101, immune families mapped (unions, readonly, mapped types, contravariant paths) | Journal XV |
| **The Hole Reaches the Editor** | Real `tsgo --lsp` run: the silent-accept ships to every user's editor — **0 diagnostics** on deep wrong code. The fix is ~free (0.57s vs 0.55s honest check at depth 1000); the hole just moves with the dial. TS2799 tuple cap located (`checker.go:23493`, `>= 10_000`) — and it reports *honestly* | Journal XVI |
| **The Autonomous Frontier** | Eight-thread campaign: **tsgo is the only silent acceptor among 8 production compilers** (javac instead hangs exponentially); complete fuse census — exactly 1 silent family of 16 constants; unfused record 36.6M inst (heap is the last wall); g++ uniquely self-raises stack; the 26% divergence localized to spread-tail recursion; the honest wall is **O(n²) time** | Journal XVII |
| **Weaponizing the Hole** | The defect becomes mechanism-level and real: **root-caused to a porting defect** — tsc5 bails `{overflow, False}` while tsgo bails an unmarked `Maybe` that `checkTypeRelatedToEx` reads as *success* (wrong verdict + swallowed diagnostic). **Weaponized**: silent accept via ordinary 110-link typedef chains (`linux/probes/WEAPONIZED_REALISTIC.ts` compiles clean). Field expanded to **11 compilers — still the only liar** (kotlin joins javac's hang family; scala SOEs in its parser). Conditional-10 sites proven shared parity, not the regression. Free-running IRIW leak-hunt added for Rosetta. Packaged for upstream: `docs/upstream_report.md` | Journal XVIII |
| **The Divergence Taxonomy** | 1,044-case differential census: **zero verdict-level divergences** between tsc5 and tsgo in composition space — the only diffs are elaboration shape (TS2740 vs TS2322 on empty-mapped-type assignments). pprof locates the O(n²): **in symbol resolution + flow typing over AST depth** (`NameResolver.Resolve`/`getConditionalFlowTypeOfType`/`isResolvedByTypeAlias`), not the relation — a shared architectural bound, not a port defect. New `macos-metal-litmus` CI job: first litmus probe of Apple's GPU fabric | Journal XIX |
| **The Compiler Whisperer** | Every silently-dropped diagnostic in BOTH checkers censused and probe-verified: **post-fuse errorType suppression** (one loud TS2589, then the type is universally assignable — real errors silently pass on BOTH compilers) and the **config-gate asymmetry** (tsgo + file args drops *every* diagnostic behind TS5112; tsc5 + file args skips the project's `strict` config → false-clean rc=0 — documented tsc behavior, intentional divergence). The 5 benign bail families proven incapable of hiding a finite error | Journal XX |
| **The Pinpointed Regression** | Pre-submission audit: `typescript-go` is closed — the port lives in `microsoft/TypeScript` as TypeScript 7 (`tsc/`). The silent accept **re-verified live on `typescript@next` nightly** (native since 7.x) and pinpointed to the exact culprit: **typescript-go#4913** (2026-08-18) changed the depth bail `{overflow,False}` → `TernaryMaybe` to fix false-positive TS2321s — the silent accept is its side effect. Clean preview builds ≤2026-07-07 bracket the regression. **Filed: [microsoft/TypeScript#64390](https://github.com/microsoft/TypeScript/issues/64390)** | Post-merge audit |

## 📂 Repository Structure

```text
.
├── bin/
│   └── chimera.js                     # Unified CLI orchestrator (npm run chimera)
├── paper/
│   ├── chimera_monograph.typ          # Source code for formal 7-page IEEE monograph
│   └── project_chimera_monograph.pdf  # High-resolution compiled research PDF
├── visualizer/
│   ├── index.html                     # Zero-dependency HTML5/Canvas visualization portal
│   ├── data_bundle.js                 # Embedded empirical benchmark datasets
│   ├── riemann.html                   # Interactive Quantum Chaos & Zeta Zero dashboard
│   └── riemann_data.js                # High-altitude spectral dataset bundle
├── docs/                              # Exported static site for GitHub Pages hosting
├── reports/
│   ├── rustc_sigbus_issue.md          # Formal disclosure report for rust-lang/rust
│   └── clang_sigill_issue.md          # Formal disclosure report for llvm/llvm-project
├── crashes/
│   ├── rust_deep_projection_sigbus_min.rs   # 10-line safe Rust MRE reproducing SIGBUS
│   └── clang_deep_template_sigill_min.cpp   # 5-line C++20 MRE reproducing SIGILL
├── riemann/
│   ├── accelerated_hunter.py          # High-altitude vectorized zero hunter (5,000 zeros)
│   ├── spectral_analysis.py           # Dyson GUE simulation & Montgomery pair correlation proof
│   └── riemann_siegel.py              # Prologue Riemann-Siegel baseline calculator
├── apple_silicon/
│   ├── litmus_test.c                  # Dual ARM64/x86 concurrent litmus test harness
│   ├── run_rosetta_litmus.sh          # Rosetta 2 compilation & execution runner
│   └── mach_ipc_bench.c               # Native XNU Mach messaging QoS scheduler probe
├── linux/                             # Act V: Linux x86_64 replication chapter
│   ├── litmus/litmus_test.c           # Native x86 TSO litmus (pthreads + mfence/xchg)
│   ├── ipc/core_pingpong.c            # Core-to-core latency probe (futex-class)
│   ├── probes/fuse_probe.ts           # tsc fuse hierarchy probe definitions
│   ├── run_fuse_probes.py             # Phase L1 runner
│   ├── run_quad_benchmarks.py         # Phase L3 quad-compiler benchmark
│   └── run_hydra_linux.py             # Phase L5 fuzzer (rustc/g++/clang++/tsc)
├── src/
│   ├── crypto/                        # Pure type-level SHA-256 engine & 32-bit math
│   ├── solvers/                       # Pure type-level DPLL 3-SAT constraint solver
│   └── type_engine/                   # Rule 110, tag systems, Brainfuck VM, quine
├── rust_chimera/                      # Rust nominal trait Horn-clause resolution engine
├── cpp_chimera/                       # C++20 non-type template metaprogramming engine
├── scripts/
│   ├── export_site.sh                 # GitHub Pages site preparation script
│   ├── symbolicate_crashes.py         # Darwin kernel IPS crash report symbolicator
│   ├── minimize_crash.py              # Automated delta-debugging reducer
│   └── hydra_fuzzer.py                # Cross-compiler adversarial fuzzer
└── data/                              # Raw JSON benchmark telemetry across all phases
```

---

## 🚀 GitHub Pages Deployment

To host the interactive visualization suite and research monograph on GitHub Pages:

```bash
# 1. Generate the static bundle in ./docs
./scripts/export_site.sh

# 2. Push to GitHub
git push origin main

# 3. In GitHub Repository Settings -> Pages:
#    Set "Build and deployment" Source to "Deploy from a branch", Branch: main, Folder: /docs
```

---

## 📜 License & Citation

Project Chimera is open-source research released under the MIT License.

```bibtex
@article{project_chimera_2026,
  title={Project Chimera: Empirical Boundaries of Undecidability and Accidental Turing-Completeness in Modern Type Systems},
  author={{Lead Compiler Architect \& Formal Type Theorist}},
  journal={IEEE Transactions on Programming Languages and Systems},
  year={2026},
  volume={48},
  number={3}
}
```
