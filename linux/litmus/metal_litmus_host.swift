// Act XIX-5 v2: host driver — parallel contention across the grid.
// Each dispatch launches 2*SLOTS threads: slot g is a self-contained SB/MP
// pair, so SLOTS pairs race simultaneously. Verdict kernel runs SLOTS
// threads reading back results and resetting for the next round.
// Usage: ./metal_host <rounds> <slots> <out.json>
// Expects metal_litmus.metallib beside the binary (build via xcrun metal).
import Foundation
import Metal

struct Slot {
    var x: UInt32 = 0
    var y: UInt32 = 0
    var data: UInt32 = 0
    var flag: UInt32 = 0
    var r0: UInt32 = 0
    var r1: UInt32 = 0
    var pad: UInt32 = 0
    var pad2: UInt32 = 0
}

struct Result {
    var violations_sb: UInt32 = 0
    var violations_mp: UInt32 = 0
    var rounds: UInt32 = 0
    var exhausted: UInt32 = 0
}

let args = CommandLine.arguments
let rounds = args.count > 1 ? Int(args[1])! : 100
let nSlots = args.count > 2 ? Int(args[2])! : 4096
let outPath = args.count > 3 ? args[3] : "data/litmus_metal_gpu.json"

guard let device = MTLCreateSystemDefaultDevice() else {
    FileHandle.standardError.write("NO_METAL_DEVICE\n".data(using: .utf8)!)
    exit(3)
}
let libURL = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
    .appendingPathComponent("metal_litmus.metallib")
let library: MTLLibrary
do {
    library = try device.makeLibrary(URL: libURL)
} catch {
    FileHandle.standardError.write("METALLIB_FAIL \(error)\n".data(using: .utf8)!)
    exit(4)
}
guard let queue = device.makeCommandQueue() else { exit(5) }

func pipe(_ name: String) -> MTLComputePipelineState {
    let fn = library.makeFunction(name: name)!
    return try! device.makeComputePipelineState(function: fn)
}
let sbTest = pipe("sb_test"), mpTest = pipe("mp_test"), verdictP = pipe("verdict")

var slots = [Slot](repeating: Slot(r0: 2, r1: 2), count: nSlots)
let slotBuf = device.makeBuffer(bytes: &slots,
                                length: nSlots * MemoryLayout<Slot>.stride,
                                options: .storageModeShared)!
var resInit = Result()
let resBuf = device.makeBuffer(bytes: &resInit, length: MemoryLayout<Result>.stride,
                               options: .storageModeShared)!

func dispatch(_ p: MTLComputePipelineState, _ threads: Int, isMP: UInt32? = nil) {
    let cmd = queue.makeCommandBuffer()!
    let enc = cmd.makeComputeCommandEncoder()!
    enc.setComputePipelineState(p)
    enc.setBuffer(slotBuf, offset: 0, index: 0)
    if let mp = isMP {
        enc.setBuffer(resBuf, offset: 0, index: 1)
        var mpv = mp
        enc.setBytes(&mpv, length: MemoryLayout<UInt32>.size, index: 2)
    }
    let tg = min(threads, p.maxTotalThreadsPerThreadgroup)
    enc.dispatchThreads(MTLSize(width: threads, height: 1, depth: 1),
                        threadsPerThreadgroup: MTLSize(width: tg, height: 1, depth: 1))
    enc.endEncoding()
    cmd.commit()
    cmd.waitUntilCompleted()
}

let t0 = Date()
var sbRounds = 0, mpRounds = 0
for i in 0..<rounds {
    if i % 2 == 0 {
        dispatch(sbTest, 2 * nSlots)
        dispatch(verdictP, nSlots, isMP: 0)
        sbRounds += nSlots
    } else {
        dispatch(mpTest, 2 * nSlots)
        dispatch(verdictP, nSlots, isMP: 1)
        mpRounds += nSlots
    }
}
let elapsed = Date().timeIntervalSince(t0) * 1000.0
let r = resBuf.contents().bindMemory(to: Result.self, capacity: 1).pointee

let json: [String: Any] = [
    "test": "Metal GPU fabric litmus v2 — parallel slot contention",
    "device": device.name,
    "slots_per_dispatch": nSlots,
    "sb": ["rounds": sbRounds, "violations": Int(r.violations_sb),
           "rate_pct": Double(r.violations_sb) / Double(max(sbRounds,1)) * 100.0],
    "mp": ["rounds": mpRounds, "violations": Int(r.violations_mp),
           "rate_pct": Double(r.violations_mp) / Double(max(mpRounds,1)) * 100.0],
    "desyncs_exhausted": Int(r.exhausted),
    "elapsed_ms": elapsed,
]
let data = try! JSONSerialization.data(withJSONObject: json, options: .prettyPrinted)
try! data.write(to: URL(fileURLWithPath: outPath))
print("Metal GPU litmus v2: device=\(device.name) slots=\(nSlots)/dispatch")
print("  SB: \(r.violations_sb)/\(sbRounds) violations")
print("  MP: \(r.violations_mp)/\(mpRounds) violations")
print("  desyncs: \(r.exhausted)   elapsed: \(String(format: "%.1f", elapsed)) ms")
