/*
 * Project Chimera: Act V / Phase L6 - Linux Core-to-Core IPC Latency
 *
 * Linux analog of the Phase 16 Mach IPC core-cluster affinity benchmark.
 * Instead of Mach ports, two threads ping-pong a cache-line-sized token
 * across explicit core pairings (pthread_setaffinity_np), measuring
 * round-trip latency. On a homogeneous VM (8 identical Ice Lake vCPUs)
 * the prediction is FLAT latency — no asymmetric-cluster penalty —
 * vs. the M2's measured 9.8x P<->E penalty.
 *
 * Transport: shared aligned atomics (the same mechanism futexes use
 * in the uncontended fast path) plus a sched_yield fallback.
 *
 * Output: data/phaseL6_linux_ipc_results.json
 */
#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdatomic.h>
#include <stdalign.h>
#include <pthread.h>
#include <sched.h>
#include <time.h>
#include <unistd.h>

#define CACHE_LINE 128
#define DEFAULT_ROUNDS 200000

typedef struct {
    alignas(CACHE_LINE) _Atomic uint64_t seq;
    alignas(CACHE_LINE) _Atomic uint64_t ack;
    _Atomic int stop;
} Channel;

static Channel g_ch;
static int g_cpu_a, g_cpu_b;
static int g_rounds;

static void pin(int cpu) {
    cpu_set_t set;
    CPU_ZERO(&set);
    CPU_SET(cpu, &set);
    pthread_setaffinity_np(pthread_self(), sizeof(set), &set);
}

static void* pong_thread(void* arg) {
    pin(g_cpu_b);
    uint64_t seen = 0;
    while (!atomic_load_explicit(&g_ch.stop, memory_order_acquire)) {
        uint64_t s = atomic_load_explicit(&g_ch.seq, memory_order_acquire);
        if (s != seen) {
            seen = s;
            atomic_store_explicit(&g_ch.ack, s, memory_order_release);
        } else {
            sched_yield();
        }
    }
    return NULL;
}

static double bench_pair(int a, int b, int rounds) {
    g_cpu_a = a; g_cpu_b = b; g_rounds = rounds;
    atomic_store(&g_ch.seq, 0);
    atomic_store(&g_ch.ack, 0);
    atomic_store(&g_ch.stop, 0);

    pthread_t th;
    pthread_create(&th, NULL, pong_thread, NULL);
    pin(a);

    struct timespec t0, t1;
    clock_gettime(CLOCK_MONOTONIC, &t0);
    for (uint64_t i = 1; i <= (uint64_t)rounds; i++) {
        atomic_store_explicit(&g_ch.seq, i, memory_order_release);
        while (atomic_load_explicit(&g_ch.ack, memory_order_acquire) != i)
            sched_yield();
    }
    clock_gettime(CLOCK_MONOTONIC, &t1);

    atomic_store(&g_ch.stop, 1);
    pthread_join(th, NULL);

    double ns = (double)(t1.tv_sec - t0.tv_sec) * 1e9 +
                (double)(t1.tv_nsec - t0.tv_nsec);
    return ns / (double)rounds;
}

int main(int argc, char** argv) {
    int rounds = argc > 1 ? atoi(argv[1]) : DEFAULT_ROUNDS;
    const char* out_json = argc > 2 ? argv[2]
                                    : "data/phaseL6_linux_ipc_results.json";
    int ncpu = (int)sysconf(_SC_NPROCESSORS_ONLN);

    printf("================================================================\n");
    printf("Project Chimera: Phase L6 - Linux Core-to-Core IPC Ping-Pong\n");
    printf("Analog of Phase 16 Mach IPC; homogeneous Ice Lake vCPUs=%d\n", ncpu);
    printf("================================================================\n\n");

    /* Pairs: same-core, adjacent, and far-apart. */
    int pairs[][2] = {{0, 0}, {0, 1}, {0, ncpu / 2}, {0, ncpu - 1},
                      {1, 2}, {ncpu - 2, ncpu - 1}};
    int npairs = sizeof(pairs) / sizeof(pairs[0]);
    double results[8][3];
    int n = 0;

    for (int i = 0; i < npairs; i++) {
        int a = pairs[i][0], b = pairs[i][1];
        if (b >= ncpu) continue;
        double ns = bench_pair(a, b, rounds);
        results[n][0] = a; results[n][1] = b; results[n][2] = ns; n++;
        printf("  pair CPU%d <-> CPU%d : %.0f ns round-trip (%.1f us) | %d rounds\n",
               a, b, ns, ns / 1000.0, rounds);
    }

    FILE* fp = fopen(out_json, "w");
    if (fp) {
        fprintf(fp, "{\n  \"phase\": \"L6\",\n  \"platform\": \"linux-x86_64\",\n");
        fprintf(fp, "  \"cpu\": \"Intel Xeon Platinum 8375C (Ice Lake, homogeneous vCPUs)\",\n");
        fprintf(fp, "  \"transport\": \"shared-cache-line atomic ping-pong\",\n");
        fprintf(fp, "  \"rounds_per_pair\": %d,\n  \"results\": [\n", rounds);
        for (int i = 0; i < n; i++) {
            fprintf(fp,
                    "    {\"cpu_a\": %d, \"cpu_b\": %d, \"round_trip_ns\": %.1f}%s\n",
                    (int)results[i][0], (int)results[i][1], results[i][2],
                    i == n - 1 ? "" : ",");
        }
        fprintf(fp, "  ]\n}\n");
        fclose(fp);
        printf("\n[SAVED] %s\n", out_json);
    }
    return 0;
}
