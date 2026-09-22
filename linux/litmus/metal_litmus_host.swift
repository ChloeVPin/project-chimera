// Act XIX-5: host driver for the Metal GPU litmus tests.
// Compiles metal_litmus.metal to a .metallib, dispatches sb_test+sb_verdict
// and mp_test+mp_verdict pairs `iterations` times, reads back violation
// counters, writes JSON. Usage:
//   swiftc metal_litmus_host.swift -o metal_host && ./metal_host <iters> <out.json>
// Expects metal_litmus.metallib beside the binary (build via xcrun metal).
import Foundation
import Metal

struct LitmusBuf {
    var x: UInt32 = 0
    var y: UInt32 = 0
    var flag: UInt32 = 0
    var data: UInt32 = 0
    var r0: UInt32 = 0
    var r1: UInt32 = 0
    var violations_sb: UInt32 = 0
    var violations_mp: UInt32 = 0
    var rounds: UInt32 = 0
}

let args = CommandLine.arguments
let iterations = args.count > 1 ? Int(args[1])! : 10000
let outPath = args.count > 2 ? args[2] : "data/litmus_metal_gpu.json"

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

let sbTest = pipe("sb_test"), sbVerdict = pipe("sb_verdict")
let mpTest = pipe("mp_test"), mpVerdict = pipe("mp_verdict")

var initBuf = LitmusBuf()
initBuf.r0 = 2; initBuf.r1 = 2
let buf = device.makeBuffer(bytes: &initBuf, length: MemoryLayout<LitmusBuf>.stride,
                            options: .storageModeShared)!

func dispatch(_ p: MTLComputePipelineState, _ threads: Int) {
    let cmd = queue.makeCommandBuffer()!
    let enc = cmd.makeComputeCommandEncoder()!
    enc.setComputePipelineState(p)
    enc.setBuffer(buf, offset: 0, index: 0)
    enc.dispatchThreads(MTLSize(width: threads, height: 1, depth: 1),
                        threadsPerThreadgroup: MTLSize(width: threads, height: 1, depth: 1))
    enc.endEncoding()
    cmd.commit()
    cmd.waitUntilCompleted()
}

let t0 = Date()
var sbRounds = 0, mpRounds = 0
for i in 0..<iterations {
    if i % 2 == 0 {
        dispatch(sbTest, 2); dispatch(sbVerdict, 1); sbRounds += 1
    } else {
        dispatch(mpTest, 2); dispatch(mpVerdict, 1); mpRounds += 1
    }
}
let elapsed = Date().timeIntervalSince(t0) * 1000.0
let r = buf.contents().bindMemory(to: LitmusBuf.self, capacity: 1).pointee

let json: [String: Any] = [
    "test": "Metal GPU fabric litmus (device-scope relaxed atomics)",
    "device": device.name,
    "iterations": iterations,
    "sb": ["rounds": sbRounds, "violations": Int(r.violations_sb),
           "rate_pct": Double(r.violations_sb) / Double(max(sbRounds,1)) * 100.0],
    "mp": ["rounds": mpRounds, "violations": Int(r.violations_mp),
           "rate_pct": Double(r.violations_mp) / Double(max(mpRounds,1)) * 100.0],
    "elapsed_ms": elapsed,
]
let data = try! JSONSerialization.data(withJSONObject: json, options: .prettyPrinted)
try! data.write(to: URL(fileURLWithPath: outPath))
print("Metal GPU litmus: device=\(device.name)")
print("  SB: \(r.violations_sb)/\(sbRounds) violations")
print("  MP: \(r.violations_mp)/\(mpRounds) violations")
print("  elapsed: \(String(format: "%.1f", elapsed)) ms")
