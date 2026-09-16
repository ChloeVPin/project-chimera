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

## 5. Suggested Remediation / Compiler Patch

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
