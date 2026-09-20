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
    volatile bool terminate;
    BarrierMode mode;
    
    // Per-round output registers
    uint32_t r0;
    uint32_t r1;
    uint32_t r_flag;
    uint32_t r_data;
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

static LitmusResult g_results[6];
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
           mode_name, iterations, sc_violations, rate, elapsed_ms);
    printf("    Breakdown: [1,1]=%llu (%.1f%%) | [1,0]=%llu (%.1f%%) | [0,1]=%llu (%.1f%%) | [0,0]=%llu (%.4f%%)\n",
           r0_1_r1_1, (double)r0_1_r1_1/iterations*100,
           r0_1_r1_0, (double)r0_1_r1_0/iterations*100,
           r0_0_r1_1, (double)r0_0_r1_1/iterations*100,
           sc_violations, rate);
    record_result("Store Buffering (SB)", mode_name, iterations, sc_violations, elapsed_ms);
}

void run_mp_experiment(uint32_t iterations, BarrierMode mode, const char* mode_name) {
    g_state.round = 0;
    g_state.t0_done = 0;
    g_state.t1_done = 0;
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
           mode_name, iterations, sc_violations, rate, elapsed_ms);
    record_result("Message Passing (MP)", mode_name, iterations, sc_violations, elapsed_ms);
}

void save_json_results(const char* filepath) {
    FILE* fp = fopen(filepath, "w");
    if (!fp) return;

#if defined(__x86_64__)
    const char* exp_name = "Phase L4: Linux x86_64 Native TSO Litmus";
    const char* arch_name = "x86_64 native Intel Xeon Platinum 8375C (hardware TSO, no translation)";
#else
    const char* exp_name = "Phase 15: Apple Silicon Weak Memory Litmus Tests";
    const char* arch_name = "ARMv8.5-A native weakly ordered memory";
#endif

    fprintf(fp, "{\n");
    fprintf(fp, "  \"metadata\": {\n");
    fprintf(fp, "    \"experiment\": \"%s\",\n", exp_name);
    fprintf(fp, "    \"cpu\": \"Apple M2\",\n");
    fprintf(fp, "    \"architecture\": \"%s\"\n", arch_name);
    fprintf(fp, "  },\n");
    fprintf(fp, "  \"results\": [\n");
    for (int i = 0; i < g_result_idx; i++) {
        fprintf(fp, "    {\n");
        fprintf(fp, "      \"test\": \"%s\",\n", g_results[i].test_name);
        fprintf(fp, "      \"mode\": \"%s\",\n", g_results[i].mode);
        fprintf(fp, "      \"iterations\": %u,\n", g_results[i].iterations);
        fprintf(fp, "      \"sc_violations\": %llu,\n", g_results[i].sc_violations);
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
#if defined(__x86_64__)
    printf("Project Chimera: Phase L4 - Linux x86_64 Native TSO Litmus\n");
    printf("Native x86 TSO: control arm for Phase 17 Rosetta result (expect 0 MP, nonzero SB)\n");
    printf("Arch: x86_64 native (Ice Lake Server) | Iterations: %u per test\n", iterations);
#else
    printf("Project Chimera: Phase 15 - Physical Apple Silicon Litmus Tests\n");
    printf("ARMv8-A Weak Memory Ordering vs. Sequential Consistency (TSO)\n");
    printf("Arch: ARM64 Native (Apple M2) | Iterations: %u per test\n", iterations);
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

    save_json_results(out_json);

    printf("\n[OK] Litmus test suite complete.\n");
    return 0;
}
