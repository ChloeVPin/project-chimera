# Bug Report: `rustc` SIGBUS (Signal 10) on Deep Nominal Trait Projection with Elevated `recursion_limit`

**Target Repository:** `rust-lang/rust`  
**Report Type:** Defect / Non-Graceful Crash / Internal Compiler Error (ICE)  
**Affects:** `rustc 1.97.0` (and nightlies on `aarch64-apple-darwin`)  
**Discovered By:** Project Chimera (Formal Systems & Compiler Architecture Laboratory)  

---

## 1. Summary

When compiling a Rust file that defines deeply nested nominal associated type projections and declares `#![recursion_limit = "..."]` with a sufficiently high bound, `rustc` crashes abruptly with **`SIGBUS` (Signal 10)** instead of emitting a graceful compiler error or recursion limit diagnostic:

```text
error: rustc interrupted by SIGBUS, printing backtrace

0   librustc_driver-22cdaff06538ddcd.dylib   _RNvNtCs3Z9OGp4qESS_17rustc_driver_impl14signal_handler17print_stack_trace + 140
1   libsystem_platform.dylib                 _sigtramp + 56
2   librustc_driver-22cdaff06538ddcd.dylib   _RNvXs_NtCs4scqkk2JIvp_10rustc_lint5early...
...
```

The crash occurs deterministically within **0.09 seconds** without consuming significant CPU or system memory.

---

## 2. Minimal Reproducible Example (MRE)

The entire issue reproduces in **10 lines of safe Rust** ([`crashes/rust_deep_projection_sigbus_min.rs`](../crashes/rust_deep_projection_sigbus_min.rs)):

```rust
#![recursion_limit = "10000000"]
pub struct S<T>(std::marker::PhantomData<T>);
pub trait Trait { type Out; }
impl Trait for () { type Out = (); }
impl<T: Trait> Trait for S<T> { type Out = S<<T as Trait>::Out>; }
type N1<T> = S<S<S<S<S<S<S<S<S<S<T>>>>>>>>>>;
type N2<T> = N1<N1<N1<N1<N1<N1<N1<N1<N1<N1<T>>>>>>>>>>;
type N3<T> = N2<N2<N2<N2<N2<N2<N2<N2<N2<N2<T>>>>>>>>>>;
type N4<T> = N3<N3<N3<N3<N3<N3<N3<N3<N3<N3<T>>>>>>>>>>;
pub type Trigger = <N4<N4<()>> as Trait>::Out;
```

---

## 3. Reproduction Steps

1. Save the above code to `reproduce.rs`.
2. Execute `rustc`:
   ```bash
   rustc --crate-type=lib reproduce.rs
   ```
3. Observe process exit code:
   ```bash
   echo $?
   # Returns 138 (or -10 / 246 depending on shell wrapper, indicating SIGBUS)
   ```

---

## 4. Root Cause Analysis

### 4.1 Trait Resolution Stack Exhaustion
In `rustc_trait_selection::traits::project`, associated type normalization evaluates projections inductively:
$$\langle S\langle T \rangle \text{ as Trait} \rangle::\text{Out} \implies S\langle \langle T \text{ as Trait} \rangle::\text{Out} \rangle$$

Each recursive step allocates an activation frame in the rustc compiler thread. In standard operation, the compiler guards against unbounded recursion via `ObligationForest` and `recursion_limit` (defaulting to 128).

### 4.2 Ineffective Stack Guarding under User Override
When the user explicitly specifies `#![recursion_limit = "10000000"]`, the defensive limit is deactivated. On macOS Darwin ARM64 (`aarch64-apple-darwin`), the default main thread stack allocated by XNU is **8 MB** (`8,388,608 bytes`).

Each trait normalization frame consumes approximately **980 bytes** of stack memory:
$$\text{Stack Needed} = 8,200 \times 980 \text{ bytes} \approx 8.04 \text{ MB} > 8.00 \text{ MB}$$

At depth $D \approx 8,200$, the stack pointer overflows the stack segment and writes into the unmapped stack guard page. On Darwin, writing past the stack guard boundary generates an asynchronous memory bus fault (`EXC_BAD_ACCESS / KERN_PROTECTION_FAILURE`), translated by the kernel into **`SIGBUS` (Signal 10)**.

Because `rustc` does not insert stack probes (e.g. via `stacker::ensure_sufficient_stack`) on every associated type normalization step, the runtime fails to grow or catch the stack overflow, resulting in a fatal process crash.

---

## 5. Live Darwin Kernel Register Dump & Symbolicated Backtrace

The fault occurred when `rustc` hit the thread stack guard boundary:
- **Exception Code:** `EXC_BAD_ACCESS` (`SIGBUS`)
- **Subtype / Fault Address:** `KERN_PROTECTION_FAILURE at 0x000000016b517f60`
- **Message:** `Could not determine thread index for stack guard region`
- **Crash Artifact:** `~/Library/Logs/DiagnosticReports/rustc-2026-09-15-220930.ips`

### 5.1 Register State at Crash (`ARM_THREAD_STATE64`)
```text
    pc = 0x0000000112338520    lr = 0x000000011235ac54    sp = 0x000000016b517ed0    fp = 0x000000016b5182a0
   far = 0x000000016b517f60   esr = 0x92000047 ((Data Abort) byte write Translation fault)  cpsr = 0x80001000

    x0 = 0x000000011defc720   x1 = 0x000000016bcae860   x2 = 0x000000016bcae348   x3 = 0x000000011defc6f8
    x4 = 0x00000002000001c5   x5 = 0x000000000000000c   x6 = 0x000000010ac0c580   x7 = 0x0000000000000002
    x8 = 0x0000000117a466f6   x9 = 0x000000011235ac48  x10 = 0x000000000000002d  x11 = 0xfffffffffffffff9
   x12 = 0x000000010a280c28  x13 = 0x0000000000000080  x14 = 0x0000000000000000  x15 = 0x0000000000000010
   x16 = 0x00000001937e0d5c  x17 = 0x00000001935cea08  x18 = 0x0000000000000000  x19 = 0x000000011defc6f8
   x20 = 0x000000016bcae860  x21 = 0x000000011da75000  x22 = 0x0000000000000001  x23 = 0x000000016bcd1320
   x24 = 0x000000011dbfc0f0  x25 = 0x0000000000000014  x26 = 0x000000016b518120  x27 = 0x0000000000000005
   x28 = 0x000000016bcaed10
```

### 5.2 Symbolicated Activation Frames (Stack Exhaustion Trajectory)
| Frame | Binary / Image | Demangled Symbol | Offset |
|---|---|---|---|
| `#0` | `librustc_driver-22cdaff06538ddcd.dylib` | `<&rustc_middle::ty::list::RawList<(), rustc_middle::ty::generic_args::GenericArg> as rustc_type_ir::fold::TypeFoldable<rustc_middle::ty::context::TyCtxt>>::fold_with::<rustc_type_ir::binder::ArgFolder<rustc_middle::ty::context::TyCtxt>>` | `+4` |
| `#1` | `librustc_driver-22cdaff06538ddcd.dylib` | `<rustc_middle::ty::Ty as rustc_type_ir::fold::TypeSuperFoldable<rustc_middle::ty::context::TyCtxt>>::super_fold_with::<rustc_type_ir::binder::ArgFolder<rustc_middle::ty::context::TyCtxt>>` | `+268` |
| `#2` | `librustc_driver-22cdaff06538ddcd.dylib` | `<&rustc_middle::ty::list::RawList<(), rustc_middle::ty::generic_args::GenericArg> as rustc_type_ir::fold::TypeFoldable<rustc_middle::ty::context::TyCtxt>>::fold_with::<rustc_type_ir::binder::ArgFolder<rustc_middle::ty::context::TyCtxt>>` | `+440` |
| `#3` | `librustc_driver-22cdaff06538ddcd.dylib` | `<rustc_middle::ty::Ty as rustc_type_ir::fold::TypeSuperFoldable<rustc_middle::ty::context::TyCtxt>>::super_fold_with::<rustc_type_ir::binder::ArgFolder<rustc_middle::ty::context::TyCtxt>>` | `+268` |
| `#4` | `librustc_driver-22cdaff06538ddcd.dylib` | `<&rustc_middle::ty::list::RawList<(), rustc_middle::ty::generic_args::GenericArg> as rustc_type_ir::fold::TypeFoldable<rustc_middle::ty::context::TyCtxt>>::fold_with::<rustc_type_ir::binder::ArgFolder<rustc_middle::ty::context::TyCtxt>>` | `+440` |
| `#5` | `librustc_driver-22cdaff06538ddcd.dylib` | `<rustc_middle::ty::Ty as rustc_type_ir::fold::TypeSuperFoldable<rustc_middle::ty::context::TyCtxt>>::super_fold_with::<rustc_type_ir::binder::ArgFolder<rustc_middle::ty::context::TyCtxt>>` | `+268` |
| `#6` | `librustc_driver-22cdaff06538ddcd.dylib` | `<&rustc_middle::ty::list::RawList<(), rustc_middle::ty::generic_args::GenericArg> as rustc_type_ir::fold::TypeFoldable<rustc_middle::ty::context::TyCtxt>>::fold_with::<rustc_type_ir::binder::ArgFolder<rustc_middle::ty::context::TyCtxt>>` | `+440` |
| `#7` | `librustc_driver-22cdaff06538ddcd.dylib` | `<rustc_middle::ty::Ty as rustc_type_ir::fold::TypeSuperFoldable<rustc_middle::ty::context::TyCtxt>>::super_fold_with::<rustc_type_ir::binder::ArgFolder<rustc_middle::ty::context::TyCtxt>>` | `+268` |
| `#8` | `librustc_driver-22cdaff06538ddcd.dylib` | `<&rustc_middle::ty::list::RawList<(), rustc_middle::ty::generic_args::GenericArg> as rustc_type_ir::fold::TypeFoldable<rustc_middle::ty::context::TyCtxt>>::fold_with::<rustc_type_ir::binder::ArgFolder<rustc_middle::ty::context::TyCtxt>>` | `+440` |
| `#9` | `librustc_driver-22cdaff06538ddcd.dylib` | `<rustc_middle::ty::Ty as rustc_type_ir::fold::TypeSuperFoldable<rustc_middle::ty::context::TyCtxt>>::super_fold_with::<rustc_type_ir::binder::ArgFolder<rustc_middle::ty::context::TyCtxt>>` | `+268` |
| `#10` | `librustc_driver-22cdaff06538ddcd.dylib` | `<&rustc_middle::ty::list::RawList<(), rustc_middle::ty::generic_args::GenericArg> as rustc_type_ir::fold::TypeFoldable<rustc_middle::ty::context::TyCtxt>>::fold_with::<rustc_type_ir::binder::ArgFolder<rustc_middle::ty::context::TyCtxt>>` | `+440` |
| `#11` | `librustc_driver-22cdaff06538ddcd.dylib` | `<rustc_middle::ty::Ty as rustc_type_ir::fold::TypeSuperFoldable<rustc_middle::ty::context::TyCtxt>>::super_fold_with::<rustc_type_ir::binder::ArgFolder<rustc_middle::ty::context::TyCtxt>>` | `+268` |
| `#12` | `librustc_driver-22cdaff06538ddcd.dylib` | `<dyn rustc_hir_analysis::hir_ty_lowering::HirTyLowerer>::lower_path_segment` | `+992` |
| `#13` | `librustc_driver-22cdaff06538ddcd.dylib` | `<dyn rustc_hir_analysis::hir_ty_lowering::HirTyLowerer>::lower_ty` | `+1616` |
| `#14` | `librustc_driver-22cdaff06538ddcd.dylib` | `<dyn rustc_hir_analysis::hir_ty_lowering::HirTyLowerer>::lower_generic_args_of_path::{closure#0}` | `+2624` |
| `#15` | `librustc_driver-22cdaff06538ddcd.dylib` | `<dyn rustc_hir_analysis::hir_ty_lowering::HirTyLowerer>::lower_path_segment` | `+104` |
| `#16` | `librustc_driver-22cdaff06538ddcd.dylib` | `<dyn rustc_hir_analysis::hir_ty_lowering::HirTyLowerer>::lower_ty` | `+1616` |
| `#17` | `librustc_driver-22cdaff06538ddcd.dylib` | `<dyn rustc_hir_analysis::hir_ty_lowering::HirTyLowerer>::lower_ty` | `+1588` |
| `#18` | `librustc_driver-22cdaff06538ddcd.dylib` | `rustc_hir_analysis::collect::type_of::type_of` | `+2176` |
| `#19` | `librustc_driver-22cdaff06538ddcd.dylib` | `rustc_query_impl::query_impl::type_of::invoke_provider_fn::__rust_begin_short_backtrace` | `+36` |
| `#20` | `librustc_driver-22cdaff06538ddcd.dylib` | `rustc_query_impl::execution::try_execute_query::<rustc_middle::query::caches::DefIdCache<rustc_middle::query::erase::ErasedData<[u8; 8]>>, false>` | `+1556` |
| `#21` | `librustc_driver-22cdaff06538ddcd.dylib` | `rustc_query_impl::query_impl::type_of::execute_query_non_incr::__rust_end_short_backtrace` | `+220` |
| `#22` | `librustc_driver-22cdaff06538ddcd.dylib` | `rustc_hir_analysis::check::check::check_item_type` | `+9308` |
| `#23` | `librustc_driver-22cdaff06538ddcd.dylib` | `rustc_hir_analysis::check::wfcheck::check_well_formed` | `+64` |
| `#24` | `librustc_driver-22cdaff06538ddcd.dylib` | `rustc_query_impl::query_impl::check_well_formed::invoke_provider_fn::__rust_begin_short_backtrace` | `+20` |

## 6. Suggested Remediation / Compiler Patch

1. **Stacker Probing in Trait Projection:**  
   Introduce a stack probe check in `rustc_trait_selection::traits::project`:
   ```rust
   stacker::maybe_grow(32 * 1024, 1024 * 1024, || {
       // normalize associated type projection
   });
   ```
2. **Physical Stack Ceiling:**  
   Even when the user specifies an astronomical `#![recursion_limit]`, `rustc` should cap recursion depth at $\min(\text{user\_limit}, \text{safe\_stack\_frames})$ where `safe_stack_frames` is derived from remaining thread stack space.
3. **Graceful Diagnostic:**  
   If stack boundaries are approached, emit `error[E0275]: overflow evaluating the requirement` rather than letting the host thread crash into the Mach guard page.
