// Act XIX-5 v2: GPU fabric weak-ordering litmus — parallel contention.
// v1 result (phaseXIX_metal_gpu.json): 0/20k on the runner's Paravirtual
// device, but each round was only 2 threads in one threadgroup — possibly
// never truly concurrent. v2 gives each test its own slot per threadgroup
// so MANY pairs race simultaneously across the grid.
// SB: thread 2g writes x[g], reads y[g]; thread 2g+1 writes y[g], reads x[g].
// A violation r0==0 && r1==0 means both readers observed the other thread's
// relaxed store as not-yet-visible — a real fabric reordering.
#include <metal_stdlib>
using namespace metal;

struct Slot {
    atomic_uint x;
    atomic_uint y;
    atomic_uint data;
    atomic_uint flag;
    atomic_uint r0;
    atomic_uint r1;
    atomic_uint pad;
    atomic_uint pad2;
};

struct Result {
    atomic_uint violations_sb;
    atomic_uint violations_mp;
    atomic_uint rounds;
    atomic_uint exhausted;   // readers that saw r==2 sentinel (desync)
};

// Two logical threads per slot; slot index = tid/2.
kernel void sb_test(device Slot* slots [[buffer(0)]],
                    uint tid [[thread_position_in_grid]]) {
    device Slot& s = slots[tid / 2];
    if ((tid & 1) == 0) {
        atomic_store_explicit(&s.x, 1, memory_order_relaxed);
        uint v = atomic_load_explicit(&s.y, memory_order_relaxed);
        atomic_store_explicit(&s.r0, v, memory_order_relaxed);
    } else {
        atomic_store_explicit(&s.y, 1, memory_order_relaxed);
        uint v = atomic_load_explicit(&s.x, memory_order_relaxed);
        atomic_store_explicit(&s.r1, v, memory_order_relaxed);
    }
}

kernel void mp_test(device Slot* slots [[buffer(0)]],
                    uint tid [[thread_position_in_grid]]) {
    device Slot& s = slots[tid / 2];
    if ((tid & 1) == 0) {
        atomic_store_explicit(&s.data, 42, memory_order_relaxed);
        atomic_store_explicit(&s.flag, 1, memory_order_relaxed);
    } else {
        uint f = atomic_load_explicit(&s.flag, memory_order_relaxed);
        uint d = atomic_load_explicit(&s.data, memory_order_relaxed);
        atomic_store_explicit(&s.r0, f, memory_order_relaxed);
        atomic_store_explicit(&s.r1, d, memory_order_relaxed);
    }
}

// Single verdict thread per slot (gid = slot index).
kernel void verdict(device Slot* slots [[buffer(0)]],
                    device Result* res [[buffer(1)]],
                    uint gid [[thread_position_in_grid]],
                    constant uint& is_mp [[buffer(2)]]) {
    device Slot& s = slots[gid];
    uint a = atomic_load_explicit(&s.r0, memory_order_relaxed);
    uint b = atomic_load_explicit(&s.r1, memory_order_relaxed);
    if (a == 2u || b == 2u) {
        atomic_fetch_add_explicit(&res->exhausted, 1, memory_order_relaxed);
    } else if (is_mp != 0u) {
        if (a == 1 && b == 0)
            atomic_fetch_add_explicit(&res->violations_mp, 1, memory_order_relaxed);
    } else {
        if (a == 0 && b == 0)
            atomic_fetch_add_explicit(&res->violations_sb, 1, memory_order_relaxed);
    }
    // reset slot
    atomic_store_explicit(&s.x, 0, memory_order_relaxed);
    atomic_store_explicit(&s.y, 0, memory_order_relaxed);
    atomic_store_explicit(&s.data, 0, memory_order_relaxed);
    atomic_store_explicit(&s.flag, 0, memory_order_relaxed);
    atomic_store_explicit(&s.r0, 2u, memory_order_relaxed);
    atomic_store_explicit(&s.r1, 2u, memory_order_relaxed);
    atomic_fetch_add_explicit(&res->rounds, 1, memory_order_relaxed);
}
