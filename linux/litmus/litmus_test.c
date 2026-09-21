/**
 * Project Chimera: Phase 15 - The Ghost in Apple Silicon
 * Physical Hardware Memory Model Litmus Tests (ARMv8-A Weak Ordering vs. TSO)
 *
 * Implements:
 * 1. Store Buffering (SB) / Dekker's Litmus Test
 *    - Invariant: ~(r0 == 0 && r1 == 0)
 *    - Weak Ordering Violation: r0 == 0 && r1 == 0
 * 2. Message Passing (MP) Litmus Test
 *    - Invariant: (flag == 1) => (data == 42)
 *    - Weak Ordering Violation: flag == 1 && data == 0
 *
 * Evaluates three memory barrier configurations:
 * - MODE_RELAXED: Unsynchronized raw `str` and `ldr`
 * - MODE_FENCED: Full memory barriers (`dmb ish`, `dmb ishld`)
 * - MODE_ACQ_REL: One-way hardware barriers (`stlr`, `ldar`)
 *
 * Act XII-D additions:
 * 3. Load Buffering (LB) — load→store reordering; forbidden on TSO, allowed on ARMv8
 * 4. Write-to-Read Causality (WRC) — 3-thread store propagation; safe on TSO
 *    (multi-copy-atomic), observable on ARMv8 (non-MCA propagation windows)
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdalign.h>
#include <pthread.h>
#include <time.h>
#include <unistd.h>
#include <string.h>
#if defined(__APPLE__)
#include <sys/sysctl.h>
#endif

#define CACHE_LINE_SIZE 128
#define DEFAULT_ITERATIONS 1000000

typedef enum {
    MODE_RELAXED = 0,
    MODE_FENCED  = 1,
    MODE_ACQ_REL = 2
} BarrierMode;

// Cache-line aligned shared variables to induce store-buffer delays
typedef struct {
    alignas(CACHE_LINE_SIZE) volatile uint32_t x;
    alignas(CACHE_LINE_SIZE) volatile uint32_t y;
    alignas(CACHE_LINE_SIZE) volatile uint32_t flag;
    alignas(CACHE_LINE_SIZE) volatile uint32_t data;
} SharedMemory;


static uint64_t now_ns(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (uint64_t)ts.tv_sec * 1000000000ull + (uint64_t)ts.tv_nsec;
}

static SharedMemory g_mem;

// Synchronization harness
typedef struct {
    volatile uint32_t round;
    volatile uint32_t t0_done;
    volatile uint32_t t1_done;
    volatile uint32_t t2_done;
    volatile uint32_t t3_done;
    volatile bool terminate;
    BarrierMode mode;
    
    // Per-round output registers
    uint32_t r0;
    uint32_t r1;
    uint32_t r_flag;
    uint32_t r_data;
    uint32_t r_wrc_a;
    uint32_t r_wrc_b;
    uint32_t r_wrc_c;
    uint32_t r_iriw_a;
    uint32_t r_iriw_b;
    uint32_t r_iriw_c;
    uint32_t r_iriw_d;
} HarnessState;

static HarnessState g_state;

#if defined(__aarch64__)
#define CPU_YIELD() __builtin_arm_yield()
#elif defined(__x86_64__)
#define CPU_YIELD() asm volatile("pause")
#else
#define CPU_YIELD() do {} while(0)
#endif

// ============================================================================
// 1. Store Buffering (SB) Threads
// ============================================================================

void* sb_thread_0(void* arg) {
    uint32_t last_round = 0;
    while (!g_state.terminate) {
        // Spin-wait for new round
        while (g_state.round == last_round && !g_state.terminate) {
            CPU_YIELD();
        }
        if (g_state.terminate) break;
        last_round = g_state.round;

        uint32_t r0_val;
#if defined(__aarch64__)
        if (g_state.mode == MODE_RELAXED) {
            asm volatile (
                "str %w1, [%2]\n\t"
                "ldr %w0, [%3]\n\t"
                : "=&r"(r0_val)
                : "r"(1), "r"(&g_mem.x), "r"(&g_mem.y)
                : "memory"
            );
        } else if (g_state.mode == MODE_FENCED) {
            asm volatile (
                "str %w1, [%2]\n\t"
                "dmb ish\n\t"
                "ldr %w0, [%3]\n\t"
                : "=&r"(r0_val)
                : "r"(1), "r"(&g_mem.x), "r"(&g_mem.y)
                : "memory"
            );
        } else { // MODE_ACQ_REL
            asm volatile (
                "stlr %w1, [%2]\n\t"
                "ldar %w0, [%3]\n\t"
                : "=&r"(r0_val)
                : "r"(1), "r"(&g_mem.x), "r"(&g_mem.y)
                : "memory"
            );
        }
#elif defined(__x86_64__)
        if (g_state.mode == MODE_RELAXED) {
            asm volatile (
                "movl %1, (%2)\n\t"
                "movl (%3), %0\n\t"
                : "=r"(r0_val)
                : "r"(1), "r"(&g_mem.x), "r"(&g_mem.y)
                : "memory"
            );
        } else if (g_state.mode == MODE_FENCED) {
            asm volatile (
                "movl %1, (%2)\n\t"
                "mfence\n\t"
                "movl (%3), %0\n\t"
                : "=r"(r0_val)
                : "r"(1), "r"(&g_mem.x), "r"(&g_mem.y)
                : "memory"
            );
        } else { // MODE_ACQ_REL (atomic exchange on x86)
            uint32_t val = 1;
            asm volatile (
                "xchgl %0, (%1)\n\t"
                "movl (%2), %0\n\t"
                : "+r"(val)
                : "r"(&g_mem.x), "r"(&g_mem.y)
                : "memory"
            );
            r0_val = val;
        }
#endif
        g_state.r0 = r0_val;
        __atomic_store_n(&g_state.t0_done, last_round, __ATOMIC_RELEASE);
    }
    return NULL;
}

void* sb_thread_1(void* arg) {
    uint32_t last_round = 0;
    while (!g_state.terminate) {
        while (g_state.round == last_round && !g_state.terminate) {
            CPU_YIELD();
        }
        if (g_state.terminate) break;
        last_round = g_state.round;

        uint32_t r1_val;
#if defined(__aarch64__)
        if (g_state.mode == MODE_RELAXED) {
            asm volatile (
                "str %w1, [%2]\n\t"
                "ldr %w0, [%3]\n\t"
                : "=&r"(r1_val)
                : "r"(1), "r"(&g_mem.y), "r"(&g_mem.x)
                : "memory"
            );
        } else if (g_state.mode == MODE_FENCED) {
            asm volatile (
                "str %w1, [%2]\n\t"
                "dmb ish\n\t"
                "ldr %w0, [%3]\n\t"
                : "=&r"(r1_val)
                : "r"(1), "r"(&g_mem.y), "r"(&g_mem.x)
                : "memory"
            );
        } else { // MODE_ACQ_REL
            asm volatile (
                "stlr %w1, [%2]\n\t"
                "ldar %w0, [%3]\n\t"
                : "=&r"(r1_val)
                : "r"(1), "r"(&g_mem.y), "r"(&g_mem.x)
                : "memory"
            );
        }
#elif defined(__x86_64__)
        if (g_state.mode == MODE_RELAXED) {
            asm volatile (
                "movl %1, (%2)\n\t"
                "movl (%3), %0\n\t"
                : "=r"(r1_val)
                : "r"(1), "r"(&g_mem.y), "r"(&g_mem.x)
                : "memory"
            );
        } else if (g_state.mode == MODE_FENCED) {
            asm volatile (
                "movl %1, (%2)\n\t"
                "mfence\n\t"
                "movl (%3), %0\n\t"
                : "=r"(r1_val)
                : "r"(1), "r"(&g_mem.y), "r"(&g_mem.x)
                : "memory"
            );
        } else { // MODE_ACQ_REL (atomic exchange on x86)
            uint32_t val = 1;
            asm volatile (
                "xchgl %0, (%1)\n\t"
                "movl (%2), %0\n\t"
                : "+r"(val)
                : "r"(&g_mem.y), "r"(&g_mem.x)
                : "memory"
            );
            r1_val = val;
        }
#endif
        g_state.r1 = r1_val;
        __atomic_store_n(&g_state.t1_done, last_round, __ATOMIC_RELEASE);
    }
    return NULL;
}

// ============================================================================
// 2. Message Passing (MP) Threads
// ============================================================================

void* mp_thread_0(void* arg) { // Producer
    uint32_t last_round = 0;
    while (!g_state.terminate) {
        while (g_state.round == last_round && !g_state.terminate) {
            CPU_YIELD();
        }
        if (g_state.terminate) break;
        last_round = g_state.round;

#if defined(__aarch64__)
        if (g_state.mode == MODE_RELAXED) {
            asm volatile (
                "str %w0, [%1]\n\t"
                "str %w2, [%3]\n\t"
                :
                : "r"(42), "r"(&g_mem.data), "r"(1), "r"(&g_mem.flag)
                : "memory"
            );
        } else if (g_state.mode == MODE_FENCED) {
            asm volatile (
                "str %w0, [%1]\n\t"
                "dmb ish\n\t"
                "str %w2, [%3]\n\t"
                :
                : "r"(42), "r"(&g_mem.data), "r"(1), "r"(&g_mem.flag)
                : "memory"
            );
        } else { // MODE_ACQ_REL
            asm volatile (
                "str %w0, [%1]\n\t"
                "stlr %w2, [%3]\n\t"
                :
                : "r"(42), "r"(&g_mem.data), "r"(1), "r"(&g_mem.flag)
                : "memory"
            );
        }
#elif defined(__x86_64__)
        if (g_state.mode == MODE_RELAXED) {
            // Under x86 TSO, store-store is preserved in hardware without fences
            asm volatile (
                "movl %0, (%1)\n\t"
                "movl %2, (%3)\n\t"
                :
                : "r"(42), "r"(&g_mem.data), "r"(1), "r"(&g_mem.flag)
                : "memory"
            );
        } else if (g_state.mode == MODE_FENCED) {
            asm volatile (
                "movl %0, (%1)\n\t"
                "mfence\n\t"
                "movl %2, (%3)\n\t"
                :
                : "r"(42), "r"(&g_mem.data), "r"(1), "r"(&g_mem.flag)
                : "memory"
            );
        } else { // MODE_ACQ_REL
            asm volatile (
                "movl %0, (%1)\n\t"
                "movl %2, (%3)\n\t"
                :
                : "r"(42), "r"(&g_mem.data), "r"(1), "r"(&g_mem.flag)
                : "memory"
            );
        }
#endif
        __atomic_store_n(&g_state.t0_done, last_round, __ATOMIC_RELEASE);
    }
    return NULL;
}

void* mp_thread_1(void* arg) { // Consumer
    uint32_t last_round = 0;
    while (!g_state.terminate) {
        while (g_state.round == last_round && !g_state.terminate) {
            CPU_YIELD();
        }
        if (g_state.terminate) break;
        last_round = g_state.round;

        uint32_t rf, rd;
#if defined(__aarch64__)
        if (g_state.mode == MODE_RELAXED) {
            asm volatile (
                "ldr %w0, [%2]\n\t"
                "ldr %w1, [%3]\n\t"
                : "=&r"(rf), "=&r"(rd)
                : "r"(&g_mem.flag), "r"(&g_mem.data)
                : "memory"
            );
        } else if (g_state.mode == MODE_FENCED) {
            asm volatile (
                "ldr %w0, [%2]\n\t"
                "dmb ishld\n\t"
                "ldr %w1, [%3]\n\t"
                : "=&r"(rf), "=&r"(rd)
                : "r"(&g_mem.flag), "r"(&g_mem.data)
                : "memory"
            );
        } else { // MODE_ACQ_REL
            asm volatile (
                "ldar %w0, [%2]\n\t"
                "ldr %w1, [%3]\n\t"
                : "=&r"(rf), "=&r"(rd)
                : "r"(&g_mem.flag), "r"(&g_mem.data)
                : "memory"
            );
        }
#elif defined(__x86_64__)
        if (g_state.mode == MODE_RELAXED) {
            // Under x86 TSO, load-load is preserved in hardware without fences
            asm volatile (
                "movl (%2), %0\n\t"
                "movl (%3), %1\n\t"
                : "=r"(rf), "=r"(rd)
                : "r"(&g_mem.flag), "r"(&g_mem.data)
                : "memory"
            );
        } else if (g_state.mode == MODE_FENCED) {
            asm volatile (
                "movl (%2), %0\n\t"
                "mfence\n\t"
                "movl (%3), %1\n\t"
                : "=r"(rf), "=r"(rd)
                : "r"(&g_mem.flag), "r"(&g_mem.data)
                : "memory"
            );
        } else { // MODE_ACQ_REL
            asm volatile (
                "movl (%2), %0\n\t"
                "movl (%3), %1\n\t"
                : "=r"(rf), "=r"(rd)
                : "r"(&g_mem.flag), "r"(&g_mem.data)
                : "memory"
            );
        }
#endif
        g_state.r_flag = rf;
        g_state.r_data = rd;
        __atomic_store_n(&g_state.t1_done, last_round, __ATOMIC_RELEASE);
    }
    return NULL;
}

// ============================================================================
// 3. Load Buffering (LB) Threads — load→store reordering
//    P0: r0 = x; y = 1   |   P1: r1 = y; x = 1   |   violation: r0==1 && r1==1
// ============================================================================

void* lb_thread_0(void* arg) {
    uint32_t last_round = 0;
    while (!g_state.terminate) {
        while (g_state.round == last_round && !g_state.terminate) CPU_YIELD();
        if (g_state.terminate) break;
        last_round = g_state.round;

        uint32_t r0_val;
#if defined(__aarch64__)
        if (g_state.mode == MODE_RELAXED) {
            asm volatile ("ldr %w0, [%1]\n\tstr %w2, [%3]\n\t"
                : "=&r"(r0_val) : "r"(&g_mem.x), "r"(1), "r"(&g_mem.y) : "memory");
        } else if (g_state.mode == MODE_FENCED) {
            asm volatile ("ldr %w0, [%1]\n\tdmb ish\n\tstr %w2, [%3]\n\t"
                : "=&r"(r0_val) : "r"(&g_mem.x), "r"(1), "r"(&g_mem.y) : "memory");
        } else {
            asm volatile ("ldar %w0, [%1]\n\tstlr %w2, [%3]\n\t"
                : "=&r"(r0_val) : "r"(&g_mem.x), "r"(1), "r"(&g_mem.y) : "memory");
        }
#elif defined(__x86_64__)
        if (g_state.mode == MODE_RELAXED || g_state.mode == MODE_ACQ_REL) {
            // TSO preserves load->store order; acq/rel adds nothing here
            asm volatile ("movl (%1), %0\n\tmovl %2, (%3)\n\t"
                : "=r"(r0_val) : "r"(&g_mem.x), "r"(1), "r"(&g_mem.y) : "memory");
        } else {
            asm volatile ("movl (%1), %0\n\tmfence\n\tmovl %2, (%3)\n\t"
                : "=r"(r0_val) : "r"(&g_mem.x), "r"(1), "r"(&g_mem.y) : "memory");
        }
#endif
        g_state.r0 = r0_val;
        __atomic_store_n(&g_state.t0_done, last_round, __ATOMIC_RELEASE);
    }
    return NULL;
}

void* lb_thread_1(void* arg) {
    uint32_t last_round = 0;
    while (!g_state.terminate) {
        while (g_state.round == last_round && !g_state.terminate) CPU_YIELD();
        if (g_state.terminate) break;
        last_round = g_state.round;

        uint32_t r1_val;
#if defined(__aarch64__)
        if (g_state.mode == MODE_RELAXED) {
            asm volatile ("ldr %w0, [%1]\n\tstr %w2, [%3]\n\t"
                : "=&r"(r1_val) : "r"(&g_mem.y), "r"(1), "r"(&g_mem.x) : "memory");
        } else if (g_state.mode == MODE_FENCED) {
            asm volatile ("ldr %w0, [%1]\n\tdmb ish\n\tstr %w2, [%3]\n\t"
                : "=&r"(r1_val) : "r"(&g_mem.y), "r"(1), "r"(&g_mem.x) : "memory");
        } else {
            asm volatile ("ldar %w0, [%1]\n\tstlr %w2, [%3]\n\t"
                : "=&r"(r1_val) : "r"(&g_mem.y), "r"(1), "r"(&g_mem.x) : "memory");
        }
#elif defined(__x86_64__)
        if (g_state.mode == MODE_RELAXED || g_state.mode == MODE_ACQ_REL) {
            asm volatile ("movl (%1), %0\n\tmovl %2, (%3)\n\t"
                : "=r"(r1_val) : "r"(&g_mem.y), "r"(1), "r"(&g_mem.x) : "memory");
        } else {
            asm volatile ("movl (%1), %0\n\tmfence\n\tmovl %2, (%3)\n\t"
                : "=r"(r1_val) : "r"(&g_mem.y), "r"(1), "r"(&g_mem.x) : "memory");
        }
#endif
        g_state.r1 = r1_val;
        __atomic_store_n(&g_state.t1_done, last_round, __ATOMIC_RELEASE);
    }
    return NULL;
}

// ============================================================================
// 4. Write-to-Read Causality (WRC) — 3-thread store propagation test
//    P0: x = 1  |  P1: ra = x; y = 1  |  P2: rb = y; rc = x
//    violation: ra==1 && rb==1 && rc==0  (P1 saw x=1, propagated via y,
//    yet P2 reads stale x — only possible on non-multi-copy-atomic fabrics)
// ============================================================================

void* wrc_thread_0(void* arg) { // sole writer of x
    uint32_t last_round = 0;
    while (!g_state.terminate) {
        while (g_state.round == last_round && !g_state.terminate) CPU_YIELD();
        if (g_state.terminate) break;
        last_round = g_state.round;

#if defined(__aarch64__) || defined(__x86_64__)
        __atomic_store_n(&g_mem.x, 1, __ATOMIC_RELAXED);
#endif
        __atomic_store_n(&g_state.t0_done, last_round, __ATOMIC_RELEASE);
    }
    return NULL;
}

void* wrc_thread_1(void* arg) { // reads x, then writes y
    uint32_t last_round = 0;
    while (!g_state.terminate) {
        while (g_state.round == last_round && !g_state.terminate) CPU_YIELD();
        if (g_state.terminate) break;
        last_round = g_state.round;

        uint32_t ra;
#if defined(__aarch64__)
        if (g_state.mode == MODE_RELAXED) {
            asm volatile ("ldr %w0, [%1]\n\tstr %w2, [%3]\n\t"
                : "=&r"(ra) : "r"(&g_mem.x), "r"(1), "r"(&g_mem.y) : "memory");
        } else if (g_state.mode == MODE_FENCED) {
            asm volatile ("ldr %w0, [%1]\n\tdmb ish\n\tstr %w2, [%3]\n\t"
                : "=&r"(ra) : "r"(&g_mem.x), "r"(1), "r"(&g_mem.y) : "memory");
        } else {
            asm volatile ("ldar %w0, [%1]\n\tstlr %w2, [%3]\n\t"
                : "=&r"(ra) : "r"(&g_mem.x), "r"(1), "r"(&g_mem.y) : "memory");
        }
#elif defined(__x86_64__)
        if (g_state.mode == MODE_FENCED) {
            asm volatile ("movl (%1), %0\n\tmfence\n\tmovl %2, (%3)\n\t"
                : "=r"(ra) : "r"(&g_mem.x), "r"(1), "r"(&g_mem.y) : "memory");
        } else {
            asm volatile ("movl (%1), %0\n\tmovl %2, (%3)\n\t"
                : "=r"(ra) : "r"(&g_mem.x), "r"(1), "r"(&g_mem.y) : "memory");
        }
#endif
        g_state.r_wrc_a = ra;
        __atomic_store_n(&g_state.t1_done, last_round, __ATOMIC_RELEASE);
    }
    return NULL;
}

void* wrc_thread_2(void* arg) { // reads y, then reads x
    uint32_t last_round = 0;
    while (!g_state.terminate) {
        while (g_state.round == last_round && !g_state.terminate) CPU_YIELD();
        if (g_state.terminate) break;
        last_round = g_state.round;

        uint32_t rb, rc;
#if defined(__aarch64__)
        if (g_state.mode == MODE_RELAXED) {
            asm volatile ("ldr %w0, [%2]\n\tldr %w1, [%3]\n\t"
                : "=&r"(rb), "=&r"(rc) : "r"(&g_mem.y), "r"(&g_mem.x) : "memory");
        } else if (g_state.mode == MODE_FENCED) {
            asm volatile ("ldr %w0, [%2]\n\tdmb ishld\n\tldr %w1, [%3]\n\t"
                : "=&r"(rb), "=&r"(rc) : "r"(&g_mem.y), "r"(&g_mem.x) : "memory");
        } else {
            asm volatile ("ldar %w0, [%2]\n\tldar %w1, [%3]\n\t"
                : "=&r"(rb), "=&r"(rc) : "r"(&g_mem.y), "r"(&g_mem.x) : "memory");
        }
#elif defined(__x86_64__)
        if (g_state.mode == MODE_FENCED) {
            asm volatile ("movl (%2), %0\n\tmfence\n\tmovl (%3), %1\n\t"
                : "=r"(rb), "=r"(rc) : "r"(&g_mem.y), "r"(&g_mem.x) : "memory");
        } else {
            asm volatile ("movl (%2), %0\n\tmovl (%3), %1\n\t"
                : "=r"(rb), "=r"(rc) : "r"(&g_mem.y), "r"(&g_mem.x) : "memory");
        }
#endif
        g_state.r_wrc_b = rb;
        g_state.r_wrc_c = rc;
        __atomic_store_n(&g_state.t2_done, last_round, __ATOMIC_RELEASE);
    }
    return NULL;
}

// ============================================================================
// 5. Independent Reads of Independent Writes (IRIW) — 4 threads
//    P0: x=1  |  P1: y=1  |  P2: ra=x; rb=y  |  P3: rc=y; rd=x
//    violation: ra==1 && rb==0 && rc==1 && rd==0
//    Requires NON-multi-copy-atomic visibility: P2 sees x's store before y's
//    while P3 sees y's before x's — the observers disagree on store order.
//    Forbidden on TSO (MCA); the classical discriminator for ARM's fabric.
// ============================================================================

void* iriw_thread_0(void* arg) { // writes x
    uint32_t last_round = 0;
    while (!g_state.terminate) {
        while (g_state.round == last_round && !g_state.terminate) CPU_YIELD();
        if (g_state.terminate) break;
        last_round = g_state.round;
        __atomic_store_n(&g_mem.x, 1, __ATOMIC_RELAXED);
        __atomic_store_n(&g_state.t0_done, last_round, __ATOMIC_RELEASE);
    }
    return NULL;
}

void* iriw_thread_1(void* arg) { // writes y
    uint32_t last_round = 0;
    while (!g_state.terminate) {
        while (g_state.round == last_round && !g_state.terminate) CPU_YIELD();
        if (g_state.terminate) break;
        last_round = g_state.round;
        __atomic_store_n(&g_mem.y, 1, __ATOMIC_RELAXED);
        __atomic_store_n(&g_state.t1_done, last_round, __ATOMIC_RELEASE);
    }
    return NULL;
}

void* iriw_thread_2(void* arg) { // reads x then y
    uint32_t last_round = 0;
    while (!g_state.terminate) {
        while (g_state.round == last_round && !g_state.terminate) CPU_YIELD();
        if (g_state.terminate) break;
        last_round = g_state.round;

        uint32_t ra, rb;
#if defined(__aarch64__)
        if (g_state.mode == MODE_RELAXED) {
            asm volatile ("ldr %w0, [%2]\n\tldr %w1, [%3]\n\t"
                : "=&r"(ra), "=&r"(rb) : "r"(&g_mem.x), "r"(&g_mem.y) : "memory");
        } else if (g_state.mode == MODE_FENCED) {
            asm volatile ("ldr %w0, [%2]\n\tdmb ish\n\tldr %w1, [%3]\n\t"
                : "=&r"(ra), "=&r"(rb) : "r"(&g_mem.x), "r"(&g_mem.y) : "memory");
        } else {
            asm volatile ("ldar %w0, [%2]\n\tldar %w1, [%3]\n\t"
                : "=&r"(ra), "=&r"(rb) : "r"(&g_mem.x), "r"(&g_mem.y) : "memory");
        }
#elif defined(__x86_64__)
        if (g_state.mode == MODE_FENCED) {
            asm volatile ("movl (%2), %0\n\tmfence\n\tmovl (%3), %1\n\t"
                : "=r"(ra), "=r"(rb) : "r"(&g_mem.x), "r"(&g_mem.y) : "memory");
        } else {
            asm volatile ("movl (%2), %0\n\tmovl (%3), %1\n\t"
                : "=r"(ra), "=r"(rb) : "r"(&g_mem.x), "r"(&g_mem.y) : "memory");
        }
#endif
        g_state.r_iriw_a = ra;
        g_state.r_iriw_b = rb;
        __atomic_store_n(&g_state.t2_done, last_round, __ATOMIC_RELEASE);
    }
    return NULL;
}

void* iriw_thread_3(void* arg) { // reads y then x
    uint32_t last_round = 0;
    while (!g_state.terminate) {
        while (g_state.round == last_round && !g_state.terminate) CPU_YIELD();
        if (g_state.terminate) break;
        last_round = g_state.round;

        uint32_t rc, rd;
#if defined(__aarch64__)
        if (g_state.mode == MODE_RELAXED) {
            asm volatile ("ldr %w0, [%2]\n\tldr %w1, [%3]\n\t"
                : "=&r"(rc), "=&r"(rd) : "r"(&g_mem.y), "r"(&g_mem.x) : "memory");
        } else if (g_state.mode == MODE_FENCED) {
            asm volatile ("ldr %w0, [%2]\n\tdmb ish\n\tldr %w1, [%3]\n\t"
                : "=&r"(rc), "=&r"(rd) : "r"(&g_mem.y), "r"(&g_mem.x) : "memory");
        } else {
            asm volatile ("ldar %w0, [%2]\n\tldar %w1, [%3]\n\t"
                : "=&r"(rc), "=&r"(rd) : "r"(&g_mem.y), "r"(&g_mem.x) : "memory");
        }
#elif defined(__x86_64__)
        if (g_state.mode == MODE_FENCED) {
            asm volatile ("movl (%2), %0\n\tmfence\n\tmovl (%3), %1\n\t"
                : "=r"(rc), "=r"(rd) : "r"(&g_mem.y), "r"(&g_mem.x) : "memory");
        } else {
            asm volatile ("movl (%2), %0\n\tmovl (%3), %1\n\t"
                : "=r"(rc), "=r"(rd) : "r"(&g_mem.y), "r"(&g_mem.x) : "memory");
        }
#endif
        g_state.r_iriw_c = rc;
        g_state.r_iriw_d = rd;
        __atomic_store_n(&g_state.t3_done, last_round, __ATOMIC_RELEASE);
    }
    return NULL;
}

// ============================================================================
// Benchmark Execution
// ============================================================================

typedef struct {
    const char* test_name;
    const char* mode;
    uint32_t iterations;
    uint64_t sc_violations;
    double violation_rate_pct;
    double elapsed_ms;
} LitmusResult;

static LitmusResult g_results[20];
static int g_result_idx = 0;

void record_result(const char* test, const char* mode, uint32_t iters, uint64_t viol, double ms) {
    g_results[g_result_idx].test_name = test;
    g_results[g_result_idx].mode = mode;
    g_results[g_result_idx].iterations = iters;
    g_results[g_result_idx].sc_violations = viol;
    g_results[g_result_idx].violation_rate_pct = (double)viol / iters * 100.0;
    g_results[g_result_idx].elapsed_ms = ms;
    g_result_idx++;
}

void run_sb_experiment(uint32_t iterations, BarrierMode mode, const char* mode_name) {
    g_state.round = 0;
    g_state.t0_done = 0;
    g_state.t1_done = 0;
    g_state.t2_done = 0;
    g_state.terminate = false;
    g_state.mode = mode;

    pthread_t t0, t1;
    pthread_create(&t0, NULL, sb_thread_0, NULL);
    pthread_create(&t1, NULL, sb_thread_1, NULL);

    uint64_t sc_violations = 0;
    uint64_t r0_1_r1_1 = 0;
    uint64_t r0_1_r1_0 = 0;
    uint64_t r0_0_r1_1 = 0;

    uint64_t start_time = now_ns();

    for (uint32_t i = 1; i <= iterations; i++) {
        g_mem.x = 0;
        g_mem.y = 0;

        // Release workers for round i
        __atomic_store_n(&g_state.round, i, __ATOMIC_RELEASE);

        // Wait for workers
        while (__atomic_load_n(&g_state.t0_done, __ATOMIC_ACQUIRE) != i) {
            CPU_YIELD();
        }
        while (__atomic_load_n(&g_state.t1_done, __ATOMIC_ACQUIRE) != i) {
            CPU_YIELD();
        }

        uint32_t r0 = g_state.r0;
        uint32_t r1 = g_state.r1;

        if (r0 == 0 && r1 == 0) {
            sc_violations++;
        } else if (r0 == 1 && r1 == 1) {
            r0_1_r1_1++;
        } else if (r0 == 1 && r1 == 0) {
            r0_1_r1_0++;
        } else if (r0 == 0 && r1 == 1) {
            r0_0_r1_1++;
        }
    }

    uint64_t elapsed = now_ns() - start_time;
    double elapsed_ms = (double)elapsed / 1e6;

    g_state.terminate = true;
    __atomic_store_n(&g_state.round, iterations + 1, __ATOMIC_RELEASE);
    pthread_join(t0, NULL);
    pthread_join(t1, NULL);

    double rate = (double)sc_violations / iterations * 100.0;
    printf("  [SB Litmus - %-10s] Iterations: %u | SC Violations (r0=0,r1=0): %llu (%.4f%%) | Time: %.2f ms\n",
           mode_name, iterations, (unsigned long long)sc_violations, rate, elapsed_ms);
    printf("    Breakdown: [1,1]=%llu (%.1f%%) | [1,0]=%llu (%.1f%%) | [0,1]=%llu (%.1f%%) | [0,0]=%llu (%.4f%%)\n",
           (unsigned long long)r0_1_r1_1, (double)r0_1_r1_1/iterations*100,
           (unsigned long long)r0_1_r1_0, (double)r0_1_r1_0/iterations*100,
           (unsigned long long)r0_0_r1_1, (double)r0_0_r1_1/iterations*100,
           (unsigned long long)sc_violations, rate);
    record_result("Store Buffering (SB)", mode_name, iterations, sc_violations, elapsed_ms);
}

void run_mp_experiment(uint32_t iterations, BarrierMode mode, const char* mode_name) {
    g_state.round = 0;
    g_state.t0_done = 0;
    g_state.t1_done = 0;
    g_state.t2_done = 0;
    g_state.terminate = false;
    g_state.mode = mode;

    pthread_t t0, t1;
    pthread_create(&t0, NULL, mp_thread_0, NULL);
    pthread_create(&t1, NULL, mp_thread_1, NULL);

    uint64_t sc_violations = 0;
    uint64_t flag0_data0 = 0;
    uint64_t flag1_data42 = 0;

    uint64_t start_time = now_ns();

    for (uint32_t i = 1; i <= iterations; i++) {
        g_mem.flag = 0;
        g_mem.data = 0;

        __atomic_store_n(&g_state.round, i, __ATOMIC_RELEASE);

        while (__atomic_load_n(&g_state.t0_done, __ATOMIC_ACQUIRE) != i) {
            CPU_YIELD();
        }
        while (__atomic_load_n(&g_state.t1_done, __ATOMIC_ACQUIRE) != i) {
            CPU_YIELD();
        }

        uint32_t rf = g_state.r_flag;
        uint32_t rd = g_state.r_data;

        if (rf == 1 && rd == 0) {
            sc_violations++;
        } else if (rf == 1 && rd == 42) {
            flag1_data42++;
        } else {
            flag0_data0++;
        }
    }

    uint64_t elapsed = now_ns() - start_time;
    double elapsed_ms = (double)elapsed / 1e6;

    g_state.terminate = true;
    __atomic_store_n(&g_state.round, iterations + 1, __ATOMIC_RELEASE);
    pthread_join(t0, NULL);
    pthread_join(t1, NULL);

    double rate = (double)sc_violations / iterations * 100.0;
    printf("  [MP Litmus - %-10s] Iterations: %u | SC Violations (flag=1,data=0): %llu (%.4f%%) | Time: %.2f ms\n",
           mode_name, iterations, (unsigned long long)sc_violations, rate, elapsed_ms);
    record_result("Message Passing (MP)", mode_name, iterations, sc_violations, elapsed_ms);
}

void run_lb_experiment(uint32_t iterations, BarrierMode mode, const char* mode_name) {
    g_state.round = 0;
    g_state.t0_done = 0;
    g_state.t1_done = 0;
    g_state.terminate = false;
    g_state.mode = mode;

    pthread_t t0, t1;
    pthread_create(&t0, NULL, lb_thread_0, NULL);
    pthread_create(&t1, NULL, lb_thread_1, NULL);

    uint64_t violations = 0;
    uint64_t start_time = now_ns();

    for (uint32_t i = 1; i <= iterations; i++) {
        g_mem.x = 0;
        g_mem.y = 0;

        __atomic_store_n(&g_state.round, i, __ATOMIC_RELEASE);
        while (__atomic_load_n(&g_state.t0_done, __ATOMIC_ACQUIRE) != i) CPU_YIELD();
        while (__atomic_load_n(&g_state.t1_done, __ATOMIC_ACQUIRE) != i) CPU_YIELD();

        if (g_state.r0 == 1 && g_state.r1 == 1) violations++;
    }

    uint64_t elapsed = now_ns() - start_time;
    double elapsed_ms = (double)elapsed / 1e6;

    g_state.terminate = true;
    __atomic_store_n(&g_state.round, iterations + 1, __ATOMIC_RELEASE);
    pthread_join(t0, NULL);
    pthread_join(t1, NULL);

    double rate = (double)violations / iterations * 100.0;
    printf("  [LB Litmus - %-10s] Iterations: %u | Violations (r0=1,r1=1): %llu (%.4f%%) | Time: %.2f ms\n",
           mode_name, iterations, (unsigned long long)violations, rate, elapsed_ms);
    record_result("Load Buffering (LB)", mode_name, iterations, violations, elapsed_ms);
}

void run_wrc_experiment(uint32_t iterations, BarrierMode mode, const char* mode_name) {
    g_state.round = 0;
    g_state.t0_done = 0;
    g_state.t1_done = 0;
    g_state.t2_done = 0;
    g_state.t3_done = 0;
    g_state.terminate = false;
    g_state.mode = mode;

    pthread_t t0, t1, t2;
    pthread_create(&t0, NULL, wrc_thread_0, NULL);
    pthread_create(&t1, NULL, wrc_thread_1, NULL);
    pthread_create(&t2, NULL, wrc_thread_2, NULL);

    uint64_t violations = 0;
    uint64_t propagated = 0;
    uint64_t start_time = now_ns();

    for (uint32_t i = 1; i <= iterations; i++) {
        g_mem.x = 0;
        g_mem.y = 0;

        __atomic_store_n(&g_state.round, i, __ATOMIC_RELEASE);
        while (__atomic_load_n(&g_state.t0_done, __ATOMIC_ACQUIRE) != i) CPU_YIELD();
        while (__atomic_load_n(&g_state.t1_done, __ATOMIC_ACQUIRE) != i) CPU_YIELD();
        while (__atomic_load_n(&g_state.t2_done, __ATOMIC_ACQUIRE) != i) CPU_YIELD();

        uint32_t ra = g_state.r_wrc_a, rb = g_state.r_wrc_b, rc = g_state.r_wrc_c;
        if (ra == 1 && rb == 1) {
            propagated++;
            if (rc == 0) violations++;
        }
    }

    uint64_t elapsed = now_ns() - start_time;
    double elapsed_ms = (double)elapsed / 1e6;

    g_state.terminate = true;
    __atomic_store_n(&g_state.round, iterations + 1, __ATOMIC_RELEASE);
    pthread_join(t0, NULL);
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);

    double rate = (double)violations / iterations * 100.0;
    printf("  [WRC Litmus - %-10s] Iterations: %u | Causality violations (ra=1,rb=1,rc=0): %llu (%.6f%%) | Propagated rounds: %llu | Time: %.2f ms\n",
           mode_name, iterations, (unsigned long long)violations, rate,
           (unsigned long long)propagated, elapsed_ms);
    record_result("Write-Read Causality (WRC)", mode_name, iterations, violations, elapsed_ms);
}

void run_iriw_experiment(uint32_t iterations, BarrierMode mode, const char* mode_name) {
    g_state.round = 0;
    g_state.t0_done = 0;
    g_state.t1_done = 0;
    g_state.t2_done = 0;
    g_state.t3_done = 0;
    g_state.terminate = false;
    g_state.mode = mode;

    pthread_t t0, t1, t2, t3;
    pthread_create(&t0, NULL, iriw_thread_0, NULL);
    pthread_create(&t1, NULL, iriw_thread_1, NULL);
    pthread_create(&t2, NULL, iriw_thread_2, NULL);
    pthread_create(&t3, NULL, iriw_thread_3, NULL);

    uint64_t violations = 0;
    uint64_t contested = 0;
    uint64_t start_time = now_ns();

    for (uint32_t i = 1; i <= iterations; i++) {
        g_mem.x = 0;
        g_mem.y = 0;

        __atomic_store_n(&g_state.round, i, __ATOMIC_RELEASE);
        while (__atomic_load_n(&g_state.t0_done, __ATOMIC_ACQUIRE) != i) CPU_YIELD();
        while (__atomic_load_n(&g_state.t1_done, __ATOMIC_ACQUIRE) != i) CPU_YIELD();
        while (__atomic_load_n(&g_state.t2_done, __ATOMIC_ACQUIRE) != i) CPU_YIELD();
        while (__atomic_load_n(&g_state.t3_done, __ATOMIC_ACQUIRE) != i) CPU_YIELD();

        uint32_t ra = g_state.r_iriw_a, rb = g_state.r_iriw_b;
        uint32_t rc = g_state.r_iriw_c, rd = g_state.r_iriw_d;
        if ((ra == 1 || rc == 1)) contested++;
        if (ra == 1 && rb == 0 && rc == 1 && rd == 0) violations++;
    }

    uint64_t elapsed = now_ns() - start_time;
    double elapsed_ms = (double)elapsed / 1e6;

    g_state.terminate = true;
    __atomic_store_n(&g_state.round, iterations + 1, __ATOMIC_RELEASE);
    pthread_join(t0, NULL);
    pthread_join(t1, NULL);
    pthread_join(t2, NULL);
    pthread_join(t3, NULL);

    double rate = (double)violations / iterations * 100.0;
    printf("  [IRIW Litmus - %-10s] Iterations: %u | MCA violations (ra=1,rb=0,rc=1,rd=0): %llu (%.6f%%) | Contested rounds: %llu | Time: %.2f ms\n",
           mode_name, iterations, (unsigned long long)violations, rate,
           (unsigned long long)contested, elapsed_ms);
    record_result("Independent Reads (IRIW)", mode_name, iterations, violations, elapsed_ms);
}

// Reports the real host CPU name on macOS (e.g. "Apple M4") — under Rosetta
// it reports the underlying Apple chip (e.g. "Apple M1 (Virtual)").
#if defined(__APPLE__)
static const char* host_cpu_name(void) {
    static char name[128] = {0};
    size_t len = sizeof(name) - 1;
    if (sysctlbyname("machdep.cpu.brand_string", name, &len, NULL, 0) == 0 && name[0])
        return name;
    return NULL;
}
#endif

void save_json_results(const char* filepath) {
    FILE* fp = fopen(filepath, "w");
    if (!fp) return;

#if defined(__APPLE__) && defined(__x86_64__)
    const char* exp_name = "Act XII-D: Rosetta 2 x86_64 Litmus on Apple Silicon";
    const char* cpu_name = host_cpu_name() ? host_cpu_name() : "Apple Silicon (Rosetta)";
    const char* arch_name = "x86_64 translated by Rosetta 2 (hardware TSO mode)";
#elif defined(__x86_64__)
    const char* exp_name = "Phase L4: Linux x86_64 Native TSO Litmus";
    const char* cpu_name = "Intel Xeon Platinum 8375C (Ice Lake)";
    const char* arch_name = "x86_64 native (hardware TSO, no translation)";
#else
    const char* exp_name = "Phase 15: Apple Silicon Weak Memory Litmus Tests";
    const char* cpu_name = host_cpu_name() ? host_cpu_name() : "Apple Silicon";
    const char* arch_name = "ARMv8.5-A native weakly ordered memory";
#endif

    fprintf(fp, "{\n");
    fprintf(fp, "  \"metadata\": {\n");
    fprintf(fp, "    \"experiment\": \"%s\",\n", exp_name);
    fprintf(fp, "    \"cpu\": \"%s\",\n", cpu_name);
    fprintf(fp, "    \"architecture\": \"%s\"\n", arch_name);
    fprintf(fp, "  },\n");
    fprintf(fp, "  \"results\": [\n");
    for (int i = 0; i < g_result_idx; i++) {
        fprintf(fp, "    {\n");
        fprintf(fp, "      \"test\": \"%s\",\n", g_results[i].test_name);
        fprintf(fp, "      \"mode\": \"%s\",\n", g_results[i].mode);
        fprintf(fp, "      \"iterations\": %u,\n", g_results[i].iterations);
        fprintf(fp, "      \"sc_violations\": %llu,\n", (unsigned long long)g_results[i].sc_violations);
        fprintf(fp, "      \"violation_rate_pct\": %.6f,\n", g_results[i].violation_rate_pct);
        fprintf(fp, "      \"elapsed_ms\": %.2f\n", g_results[i].elapsed_ms);
        fprintf(fp, "    }%s\n", (i == g_result_idx - 1) ? "" : ",");
    }
    fprintf(fp, "  ]\n");
    fprintf(fp, "}\n");
    fclose(fp);
    printf("\n[SAVED] Empirical litmus results exported to %s\n", filepath);
}

int main(int argc, char** argv) {
    uint32_t iterations = DEFAULT_ITERATIONS;
    if (argc > 1) {
        iterations = (uint32_t)atoi(argv[1]);
    }

    const char* out_json = "data/phase15_litmus_results.json";
#if defined(__x86_64__)
    out_json = "data/phaseL4_linux_litmus_results.json";
#endif
    if (argc > 2) {
        out_json = argv[2];
    }

    printf("================================================================\n");
#if defined(__APPLE__) && defined(__x86_64__)
    printf("Project Chimera: Act XII-D - Rosetta 2 Translated x86_64 Litmus\n");
    printf("x86 binary on Apple Silicon via Rosetta 2 hardware TSO mode\n");
    printf("Arch: x86_64-on-ARM64 (%s) | Iterations: %u per test\n",
           host_cpu_name() ? host_cpu_name() : "Apple Silicon", iterations);
#elif defined(__x86_64__)
    printf("Project Chimera: Phase L4 - Linux x86_64 Native TSO Litmus\n");
    printf("Native x86 TSO: control arm for Phase 17 Rosetta result (expect 0 MP, nonzero SB)\n");
    printf("Arch: x86_64 native (Ice Lake Server) | Iterations: %u per test\n", iterations);
#else
    printf("Project Chimera: Phase 15 - Physical Apple Silicon Litmus Tests\n");
    printf("ARMv8-A Weak Memory Ordering vs. Sequential Consistency (TSO)\n");
    printf("Arch: ARM64 Native (%s) | Iterations: %u per test\n",
           host_cpu_name() ? host_cpu_name() : "Apple Silicon", iterations);
#endif
    printf("================================================================\n\n");

    printf(">>> Experiment A: Store Buffering (SB / Dekker)\n");
    run_sb_experiment(iterations, MODE_RELAXED, "RELAXED");
    run_sb_experiment(iterations, MODE_FENCED, "FENCED");
    run_sb_experiment(iterations, MODE_ACQ_REL, "ACQ_REL");

    printf("\n>>> Experiment B: Message Passing (MP)\n");
    run_mp_experiment(iterations, MODE_RELAXED, "RELAXED");
    run_mp_experiment(iterations, MODE_FENCED, "FENCED");
    run_mp_experiment(iterations, MODE_ACQ_REL, "ACQ_REL");

    printf("\n>>> Experiment C: Load Buffering (LB) — load->store reordering\n");
    run_lb_experiment(iterations, MODE_RELAXED, "RELAXED");
    run_lb_experiment(iterations, MODE_FENCED, "FENCED");
    run_lb_experiment(iterations, MODE_ACQ_REL, "ACQ_REL");

    printf("\n>>> Experiment D: Write-to-Read Causality (WRC) — store propagation\n");
    run_wrc_experiment(iterations, MODE_RELAXED, "RELAXED");
    run_wrc_experiment(iterations, MODE_FENCED, "FENCED");
    run_wrc_experiment(iterations, MODE_ACQ_REL, "ACQ_REL");

    printf("\n>>> Experiment E: Independent Reads of Independent Writes (IRIW) — MCA test\n");
    run_iriw_experiment(iterations, MODE_RELAXED, "RELAXED");
    run_iriw_experiment(iterations, MODE_FENCED, "FENCED");
    run_iriw_experiment(iterations, MODE_ACQ_REL, "ACQ_REL");

    save_json_results(out_json);
    printf("\n================================================================\n");
    printf("All litmus experiments complete.\n");
    printf("================================================================\n");
    return 0;
}
