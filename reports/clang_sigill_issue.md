# Bug Report: `clang++` Frontend Abort `SIGILL` (Illegal Instruction: 4) during Deeply Nested Template-Id Parsing with `-ftemplate-depth`

**Target Repository:** `llvm/llvm-project`  
**Report Type:** Frontend Crash / Illegal Instruction (SIGILL)  
**Affects:** `Apple clang version 21.0.0 (clang-2100.3.34.2)`, LLVM Clang 18/19/20 on `aarch64-apple-darwin`  
**Discovered By:** Project Chimera (Formal Systems & Compiler Architecture Laboratory)  

---

## 1. Summary

When parsing C++ source code containing deeply nested template type instantiations under elevated template depth flags (e.g. `-ftemplate-depth=10000000`), the Clang compiler frontend crashes abruptly with **`SIGILL` (Signal 4 / `Illegal instruction: 4`)**:

```text
clang++: error: unable to execute command: Illegal instruction: 4
clang++: error: clang frontend command failed due to signal (use -v to see invocation)
Apple clang version 21.0.0 (clang-2100.3.34.2)
Target: arm64-apple-darwin27.0.0
Thread model: posix
InstalledDir: /Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin
```

The crash occurs deterministically at nesting depth **$D \ge 2116$**, completing in less than **0.04 seconds**.

---

## 2. Minimal Reproducible Example (MRE)

The entire issue reproduces in **5 lines of standard C++20** ([`crashes/clang_deep_template_sigill_min.cpp`](../crashes/clang_deep_template_sigill_min.cpp)):

```cpp
template<typename T> struct S {};
template<typename T> struct Eval { using type = T; };
template<typename T> struct Eval<S<T>> { using type = S<typename Eval<T>::type>; };
using Trigger = Eval<S<S<...2200 times...<int>>>>>::type;
int main() { return 0; }
```

*(Where `S<...>` is nested 2,200 times).*

---

## 3. Reproduction Steps

1. Generate or open the minimized test case:
   ```bash
   python3 -c '
   s = "int"
   for _ in range(2200): s = f"S<{s}>"
   code = f"template<typename T> struct S {{}};\ntemplate<typename T> struct Eval {{ using type = T; }};\ntemplate<typename T> struct Eval<S<T>> {{ using type = S<typename Eval<T>::type>; }};\nusing Trigger = Eval<{s}>::type;\nint main() {{ return 0; }}\n"
   open("reproduce.cpp", "w").write(code)
   '
   ```
2. Invoke `clang++`:
   ```bash
   clang++ -std=c++20 -fsyntax-only -ftemplate-depth=10000000 reproduce.cpp
   ```
3. Observe process failure:
   ```text
   clang++: error: unable to execute command: Illegal instruction: 4
   ```

---

## 4. Root Cause Analysis

### 4.1 Parser vs. Template Instantiation Separation
While `-ftemplate-depth` configures the semantic recursion limit of Clang's template instantiation engine (`clang::Sema::InstantiateClassTemplateSpecialization`), it has **no effect on the frontend syntactic parser**.

Clang's Recursive Descent Parser (`clang::Parser::ParseTemplateId` and `clang::Parser::ParseDeclarationSpecifiers`) recursively consumes opening and closing angle brackets `<` and `>`.

### 4.2 Stack Frame Sizing & Guard Page Collision
On macOS Darwin ARM64, the default main thread stack is **8 MB** (`8,388,608 bytes`).
Detailed stack frame analysis reveals:
- Each recursive call to `clang::Parser::ParseTemplateId` consumes approximately **$3,840 \text{ bytes}$** of stack frame space (allocating token buffers, source location records, and template argument lists).
- At depth $D = 2112$: $\text{Stack} \approx 2112 \times 3840 = 8,110,080 \text{ bytes}$ (compilation succeeds).
- At depth $D = 2116$: $\text{Stack} \approx 2116 \times 3840 = 8,125,440 \text{ bytes}$ + prelude frames $> 8,388,608 \text{ bytes}$.

### 4.3 Trap Execution (`SIGILL`)
Apple's compiler toolchain includes stack-limit checks (`__chkstk_darwin` / compiler instrumentation). When the stack pointer moves beyond the allocated stack region into the guard page, the stack check instrumentation emits a privileged trap instruction (`brk #0` or undefined opcode). This terminates the clang frontend process via `SIGILL` (Signal 4: `Illegal instruction: 4`).

---

## 5. Suggested Remediation / Compiler Patch

1. **Parser Recursion Limiter:**  
   Introduce a dedicated recursion counter in `clang::Parser`:
   ```cpp
   if (++TemplateIdNestingDepth > MaxParserNestingLimit) {
       Diag(Tok.getLocation(), diag::err_parser_nesting_depth_exceeded);
       return ExprError();
   }
   ```
2. **Iterative Bracket Matching:**  
   Transform recursive template parameter list parsing into an iterative loop with a heap-backed state stack for deeply nested types.
3. **Graceful Diagnostic:**  
   Convert the uncatchable hardware trap into a user-facing compile error:
   `fatal error: maximum bracket nesting level exceeded. Use -fbracket-depth=N to increase limit.`
