// Act XIX-5: GPU fabric weak-ordering litmus — Apple Metal compute.
// SB (Dekker): violation r0==0 && r1==0 requires GPU-visible reordering.
// MP: flag==1 && data==0 requires store propagation anomaly.
// Memory model: atomic<T> + memory_order_relaxed, thread_scope_device.
#include <metal_stdlib>
using namespace metal;

struct LitmusBuf {
    atomic_uint x;
    atomic_uint y;
    atomic_uint flag;
    atomic_uint data;
    atomic_uint r0;
    atomic_uint r1;
    atomic_uint violations_sb;
    atomic_uint violations_mp;
    atomic_uint rounds;
};

// SB test: gid 0 writes x then reads y; gid 1 writes y then reads x.
kernel void sb_test(device LitmusBuf* buf [[buffer(0)]],
                    uint gid [[thread_position_in_grid]]) {
    if (gid == 0) {
        atomic_store_explicit(&buf->x, 1, memory_order_relaxed);
        uint v = atomic_load_explicit(&buf->y, memory_order_relaxed);
        atomic_store_explicit(&buf->r0, v, memory_order_relaxed);
    } else if (gid == 1) {
        atomic_store_explicit(&buf->y, 1, memory_order_relaxed);
        uint v = atomic_load_explicit(&buf->x, memory_order_relaxed);
        atomic_store_explicit(&buf->r1, v, memory_order_relaxed);
    }
}

// Verdict kernel runs single-threaded after the two writers complete.
kernel void sb_verdict(device LitmusBuf* buf [[buffer(0)]]) {
    uint a = atomic_load_explicit(&buf->r0, memory_order_relaxed);
    uint b = atomic_load_explicit(&buf->r1, memory_order_relaxed);
    if (a == 0 && b == 0) {
        atomic_fetch_add_explicit(&buf->violations_sb, 1, memory_order_relaxed);
    }
    // reset for next round
    atomic_store_explicit(&buf->x, 0, memory_order_relaxed);
    atomic_store_explicit(&buf->y, 0, memory_order_relaxed);
    atomic_store_explicit(&buf->r0, 2u, memory_order_relaxed);
    atomic_store_explicit(&buf->r1, 2u, memory_order_relaxed);
    atomic_fetch_add_explicit(&buf->rounds, 1, memory_order_relaxed);
}

// MP test: gid 0 writes data then flag; gid 1 reads flag then data.
kernel void mp_test(device LitmusBuf* buf [[buffer(0)]],
                    uint gid [[thread_position_in_grid]]) {
    if (gid == 0) {
        atomic_store_explicit(&buf->data, 42, memory_order_relaxed);
        atomic_store_explicit(&buf->flag, 1, memory_order_relaxed);
    } else if (gid == 1) {
        uint f = atomic_load_explicit(&buf->flag, memory_order_relaxed);
        uint d = atomic_load_explicit(&buf->data, memory_order_relaxed);
        atomic_store_explicit(&buf->r0, f, memory_order_relaxed);
        atomic_store_explicit(&buf->r1, d, memory_order_relaxed);
    }
}

kernel void mp_verdict(device LitmusBuf* buf [[buffer(0)]]) {
    uint f = atomic_load_explicit(&buf->r0, memory_order_relaxed);
    uint d = atomic_load_explicit(&buf->r1, memory_order_relaxed);
    if (f == 1 && d == 0) {
        atomic_fetch_add_explicit(&buf->violations_mp, 1, memory_order_relaxed);
    }
    atomic_store_explicit(&buf->flag, 0, memory_order_relaxed);
    atomic_store_explicit(&buf->data, 0, memory_order_relaxed);
    atomic_store_explicit(&buf->r0, 0u, memory_order_relaxed);
    atomic_store_explicit(&buf->r1, 0u, memory_order_relaxed);
}
