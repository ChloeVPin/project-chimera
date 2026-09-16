/**
 * Project Chimera: Phase 16 - Asymmetric Scheduler Probing
 * Native Mach IPC Ping-Pong Probe (XNU Kernel APIs & Heterogeneous Apple Silicon Clusters)
 *
 * Measures:
 * 1. P-Core <-> P-Core (Intra-Cluster Performance: QOS_CLASS_USER_INTERACTIVE)
 * 2. E-Core <-> E-Core (Intra-Cluster Efficiency: QOS_CLASS_BACKGROUND)
 * 3. P-Core <-> E-Core (Inter-Cluster Asymmetric: P-to-E Core Migration)
 *
 * Telemetry:
 * - Round-trip latency (min, mean, median, p99, max, stddev/jitter)
 * - Inter-cluster cache coherency overhead across Firestorm/Avalanche vs. Icestorm/Blizzard
 */

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdbool.h>
#include <math.h>
#include <mach/mach.h>
#include <mach/mach_time.h>
#include <pthread.h>
#include <pthread/qos.h>
#include <unistd.h>
#include <string.h>

#define DEFAULT_ROUNDS 50000

// Mach Message Payload Definition
typedef struct {
    mach_msg_header_t header;
    uint64_t send_time;
    uint32_t round;
} MsgBody;

typedef struct {
    mach_msg_header_t header;
    uint64_t send_time;
    uint32_t round;
    mach_msg_trailer_t trailer;
} MsgRecvBuffer;

typedef struct {
    const char* config_name;
    qos_class_t qos_a;
    qos_class_t qos_b;
    const char* desc;
} BenchConfig;

typedef struct {
    const char* config_name;
    const char* desc;
    uint32_t rounds;
    double min_ns;
    double mean_ns;
    double median_ns;
    double p99_ns;
    double max_ns;
    double stddev_ns;
    double msgs_per_sec;
} IPCResult;

static IPCResult g_ipc_results[3];
static int g_ipc_idx = 0;

static mach_port_t g_port_a_to_b;
static mach_port_t g_port_b_to_a;
static volatile bool g_thread_b_ready = false;
static volatile bool g_terminate = false;
static uint32_t g_total_rounds = 0;

static double* g_latencies = NULL;

static mach_timebase_info_data_t g_tb;

static inline double ticks_to_ns(uint64_t ticks) {
    return (double)(ticks * g_tb.numer) / g_tb.denom;
}

// Comparison function for qsort
static int cmp_doubles(const void* a, const void* b) {
    double da = *(const double*)a;
    double db = *(const double*)b;
    if (da < db) return -1;
    if (da > db) return 1;
    return 0;
}

// Thread B: Receiver & Responder
void* thread_b_worker(void* arg) {
    qos_class_t qos = *(qos_class_t*)arg;
    pthread_set_qos_class_self_np(qos, 0);

    g_thread_b_ready = true;

    MsgRecvBuffer recv_buf;
    MsgBody reply_msg;

    for (uint32_t r = 0; r < g_total_rounds; r++) {
        // 1. Receive from Thread A
        mach_msg_return_t ret = mach_msg(
            &recv_buf.header,
            MACH_RCV_MSG,
            0,
            sizeof(recv_buf),
            g_port_a_to_b,
            MACH_MSG_TIMEOUT_NONE,
            MACH_PORT_NULL
        );
        if (ret != MACH_MSG_SUCCESS) {
            fprintf(stderr, "Thread B receive failed: %d\n", ret);
            break;
        }

        // 2. Reply to Thread A
        reply_msg.header.msgh_bits = MACH_MSGH_BITS(MACH_MSG_TYPE_COPY_SEND, 0);
        reply_msg.header.msgh_size = sizeof(MsgBody);
        reply_msg.header.msgh_remote_port = g_port_b_to_a;
        reply_msg.header.msgh_local_port = MACH_PORT_NULL;
        reply_msg.header.msgh_id = 2002;
        reply_msg.send_time = recv_buf.send_time;
        reply_msg.round = recv_buf.round;

        ret = mach_msg(
            &reply_msg.header,
            MACH_SEND_MSG,
            sizeof(MsgBody),
            0,
            MACH_PORT_NULL,
            MACH_MSG_TIMEOUT_NONE,
            MACH_PORT_NULL
        );
        if (ret != MACH_MSG_SUCCESS) {
            fprintf(stderr, "Thread B reply failed: %d\n", ret);
            break;
        }
    }
    return NULL;
}

void run_ipc_config(const BenchConfig* cfg, uint32_t rounds) {
    g_total_rounds = rounds;
    g_thread_b_ready = false;
    g_terminate = false;

    // Allocate Mach Ports
    mach_port_allocate(mach_task_self(), MACH_PORT_RIGHT_RECEIVE, &g_port_a_to_b);
    mach_port_insert_right(mach_task_self(), g_port_a_to_b, g_port_a_to_b, MACH_MSG_TYPE_MAKE_SEND);

    mach_port_allocate(mach_task_self(), MACH_PORT_RIGHT_RECEIVE, &g_port_b_to_a);
    mach_port_insert_right(mach_task_self(), g_port_b_to_a, g_port_b_to_a, MACH_MSG_TYPE_MAKE_SEND);

    // Launch Thread B
    pthread_t thread_b;
    qos_class_t qos_b = cfg->qos_b;
    pthread_create(&thread_b, NULL, thread_b_worker, &qos_b);

    // Configure Thread A QoS
    pthread_set_qos_class_self_np(cfg->qos_a, 0);

    while (!g_thread_b_ready) {
        usleep(100);
    }

    MsgBody send_msg;
    MsgRecvBuffer recv_buf;

    uint64_t t_start_total = mach_absolute_time();

    for (uint32_t r = 0; r < rounds; r++) {
        uint64_t t_send = mach_absolute_time();

        send_msg.header.msgh_bits = MACH_MSGH_BITS(MACH_MSG_TYPE_COPY_SEND, 0);
        send_msg.header.msgh_size = sizeof(MsgBody);
        send_msg.header.msgh_remote_port = g_port_a_to_b;
        send_msg.header.msgh_local_port = MACH_PORT_NULL;
        send_msg.header.msgh_id = 1001;
        send_msg.send_time = t_send;
        send_msg.round = r;

        // Send to Thread B
        mach_msg_return_t ret = mach_msg(
            &send_msg.header,
            MACH_SEND_MSG,
            sizeof(MsgBody),
            0,
            MACH_PORT_NULL,
            MACH_MSG_TIMEOUT_NONE,
            MACH_PORT_NULL
        );
        if (ret != MACH_MSG_SUCCESS) {
            fprintf(stderr, "Thread A send failed: %d\n", ret);
            break;
        }

        // Receive reply from Thread B
        ret = mach_msg(
            &recv_buf.header,
            MACH_RCV_MSG,
            0,
            sizeof(recv_buf),
            g_port_b_to_a,
            MACH_MSG_TIMEOUT_NONE,
            MACH_PORT_NULL
        );
        if (ret != MACH_MSG_SUCCESS) {
            fprintf(stderr, "Thread A receive failed: %d\n", ret);
            break;
        }

        uint64_t t_recv = mach_absolute_time();
        double rtt_ns = ticks_to_ns(t_recv - t_send);
        g_latencies[r] = rtt_ns;
    }

    uint64_t t_end_total = mach_absolute_time();
    double total_ms = ticks_to_ns(t_end_total - t_start_total) / 1e6;

    pthread_join(thread_b, NULL);

    // Deallocate Mach Ports
    mach_port_mod_refs(mach_task_self(), g_port_a_to_b, MACH_PORT_RIGHT_RECEIVE, -1);
    mach_port_mod_refs(mach_task_self(), g_port_b_to_a, MACH_PORT_RIGHT_RECEIVE, -1);

    // Calculate Statistics
    double sum = 0.0;
    double min_v = 1e12;
    double max_v = 0.0;

    for (uint32_t r = 0; r < rounds; r++) {
        double v = g_latencies[r];
        sum += v;
        if (v < min_v) min_v = v;
        if (v > max_v) max_v = v;
    }

    double mean = sum / rounds;

    double variance_sum = 0.0;
    for (uint32_t r = 0; r < rounds; r++) {
        double diff = g_latencies[r] - mean;
        variance_sum += diff * diff;
    }
    double stddev = sqrt(variance_sum / rounds);

    qsort(g_latencies, rounds, sizeof(double), cmp_doubles);
    double median = g_latencies[rounds / 2];
    double p99 = g_latencies[(size_t)(rounds * 0.99)];
    double throughput = (double)rounds / (total_ms / 1000.0);

    printf("  [%-18s] (%s)\n", cfg->config_name, cfg->desc);
    printf("    Round Trips: %u | Mean: %8.1f ns | Median: %8.1f ns | P99: %8.1f ns\n",
           rounds, mean, median, p99);
    printf("    Min: %8.1f ns | Max: %8.1f ns | Jitter (StdDev): %8.1f ns | Throughput: %.0f msgs/sec\n\n",
           min_v, max_v, stddev, throughput * 2.0); // 2 messages per round trip

    g_ipc_results[g_ipc_idx].config_name = cfg->config_name;
    g_ipc_results[g_ipc_idx].desc = cfg->desc;
    g_ipc_results[g_ipc_idx].rounds = rounds;
    g_ipc_results[g_ipc_idx].min_ns = min_v;
    g_ipc_results[g_ipc_idx].mean_ns = mean;
    g_ipc_results[g_ipc_idx].median_ns = median;
    g_ipc_results[g_ipc_idx].p99_ns = p99;
    g_ipc_results[g_ipc_idx].max_ns = max_v;
    g_ipc_results[g_ipc_idx].stddev_ns = stddev;
    g_ipc_results[g_ipc_idx].msgs_per_sec = throughput * 2.0;
    g_ipc_idx++;
}

void save_ipc_json(const char* filepath) {
    FILE* fp = fopen(filepath, "w");
    if (!fp) return;

    fprintf(fp, "{\n");
    fprintf(fp, "  \"metadata\": {\n");
    fprintf(fp, "    \"experiment\": \"Phase 16: Apple Silicon Asymmetric Core Scheduling & Mach IPC\",\n");
    fprintf(fp, "    \"cpu\": \"Apple M2 (ARM64)\",\n");
    fprintf(fp, "    \"topology\": \"4 Avalanche P-Cores + 4 Blizzard E-Cores\",\n");
    fprintf(fp, "    \"ipc_mechanism\": \"XNU Native Mach Message Trap (mach_msg)\"\n");
    fprintf(fp, "  },\n");
    fprintf(fp, "  \"configs\": [\n");
    for (int i = 0; i < g_ipc_idx; i++) {
        fprintf(fp, "    {\n");
        fprintf(fp, "      \"config_name\": \"%s\",\n", g_ipc_results[i].config_name);
        fprintf(fp, "      \"description\": \"%s\",\n", g_ipc_results[i].desc);
        fprintf(fp, "      \"rounds\": %u,\n", g_ipc_results[i].rounds);
        fprintf(fp, "      \"min_ns\": %.1f,\n", g_ipc_results[i].min_ns);
        fprintf(fp, "      \"mean_ns\": %.1f,\n", g_ipc_results[i].mean_ns);
        fprintf(fp, "      \"median_ns\": %.1f,\n", g_ipc_results[i].median_ns);
        fprintf(fp, "      \"p99_ns\": %.1f,\n", g_ipc_results[i].p99_ns);
        fprintf(fp, "      \"max_ns\": %.1f,\n", g_ipc_results[i].max_ns);
        fprintf(fp, "      \"jitter_stddev_ns\": %.1f,\n", g_ipc_results[i].stddev_ns);
        fprintf(fp, "      \"msgs_per_sec\": %.0f\n", g_ipc_results[i].msgs_per_sec);
        fprintf(fp, "    }%s\n", (i == g_ipc_idx - 1) ? "" : ",");
    }
    fprintf(fp, "  ]\n");
    fprintf(fp, "}\n");
    fclose(fp);
    printf("[SAVED] Mach IPC telemetry exported to %s\n", filepath);
}

int main(int argc, char** argv) {
    uint32_t rounds = DEFAULT_ROUNDS;
    if (argc > 1) {
        rounds = (uint32_t)atoi(argv[1]);
    }

    mach_timebase_info(&g_tb);
    g_latencies = (double*)malloc(sizeof(double) * rounds);
    if (!g_latencies) {
        fprintf(stderr, "Memory allocation failed\n");
        return 1;
    }

    printf("================================================================\n");
    printf("Project Chimera: Phase 16 - Asymmetric Scheduler Probing\n");
    printf("Mach IPC Latency Across Heterogeneous Apple Silicon CPU Clusters\n");
    printf("Host: Apple M2 | P-Cores: Avalanche | E-Cores: Blizzard\n");
    printf("Rounds per configuration: %u\n", rounds);
    printf("================================================================\n\n");

    BenchConfig configs[] = {
        {
            .config_name = "P-Core <-> P-Core",
            .qos_a = QOS_CLASS_USER_INTERACTIVE,
            .qos_b = QOS_CLASS_USER_INTERACTIVE,
            .desc = "Intra-cluster Performance Core messaging (Avalanche <-> Avalanche)"
        },
        {
            .config_name = "E-Core <-> E-Core",
            .qos_a = QOS_CLASS_BACKGROUND,
            .qos_b = QOS_CLASS_BACKGROUND,
            .desc = "Intra-cluster Efficiency Core messaging (Blizzard <-> Blizzard)"
        },
        {
            .config_name = "P-Core <-> E-Core",
            .qos_a = QOS_CLASS_USER_INTERACTIVE,
            .qos_b = QOS_CLASS_BACKGROUND,
            .desc = "Inter-cluster Asymmetric messaging (Avalanche <-> Blizzard)"
        }
    };

    for (int i = 0; i < 3; i++) {
        run_ipc_config(&configs[i], rounds);
    }

    save_ipc_json("data/phase16_mach_ipc_results.json");

    free(g_latencies);
    printf("\n[OK] Mach IPC asymmetric probing complete.\n");
    return 0;
}
