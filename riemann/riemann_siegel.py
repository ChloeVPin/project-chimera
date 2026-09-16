#!/usr/bin/env python3
"""
Project Chimera: Prologue to Project Riemann
High-Precision Riemann-Siegel Zero Calculator & Quantum Chaos GUE Statistics

Computes non-trivial zeros of zeta(1/2 + it) on the critical line for t in [1000, 1050],
unfolds the spectrum using the smooth Riemann-von Mangoldt counting function,
and compares the nearest-neighbor spacing distribution P(s) against the
Gaussian Unitary Ensemble (GUE) Wigner surmise:
    P(s) = (32 / pi^2) * s^2 * exp(-4/pi * s^2)
"""

import sys
import json
import math
import time
from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

def riemann_siegel_theta(t: float) -> float:
    """
    Riemann-Siegel theta function theta(t) via asymptotic Stirling expansion.
    Accurate to > 10^-12 for t >= 1000.
    """
    t_2 = t / 2.0
    term1 = t_2 * math.log(t / (2.0 * math.pi)) - t_2 - (math.pi / 8.0)
    term2 = 1.0 / (48.0 * t)
    term3 = 7.0 / (5760.0 * (t ** 3))
    term4 = 31.0 / (80640.0 * (t ** 5))
    return term1 + term2 + term3 - term4

def hardy_z(t: float) -> float:
    """
    Hardy's Z-function Z(t) = exp(i * theta(t)) * zeta(1/2 + it).
    Z(t) is real-valued on the critical line Re(s) = 1/2.
    Real zeros of Z(t) correspond to non-trivial zeros of zeta(s).
    """
    th = riemann_siegel_theta(t)
    a = math.sqrt(t / (2.0 * math.pi))
    N = int(math.floor(a))
    p = a - N
    
    # Vectorized main sum: 2 * sum_{n=1}^N cos(theta(t) - t * ln(n)) / sqrt(n)
    n = np.arange(1, N + 1, dtype=np.float64)
    phases = th - t * np.log(n)
    cos_terms = np.cos(phases) / np.sqrt(n)
    main_sum = 2.0 * float(np.sum(cos_terms))
    
    # Riemann-Siegel remainder term C_0(p)
    denom = math.cos(2.0 * math.pi * p)
    if abs(denom) < 1e-12:
        # Taylor expansion near p = 0.5 where cos(2*pi*p) approaches 0
        dp = p - 0.5
        c0 = -1.0 / (2.0 * math.pi) * (1.0 + (math.pi**2 / 3.0) * (dp**2))
    else:
        num = math.cos(2.0 * math.pi * (p**2 - p - 1.0 / 16.0))
        c0 = num / denom
        
    remainder = ((-1.0) ** (N - 1)) * (a ** (-0.5)) * c0
    return main_sum + remainder

def find_critical_zeros(t_start: float = 1000.0, t_end: float = 1050.0, scan_step: float = 0.02) -> list[float]:
    """
    Scans the critical interval [t_start, t_end] with high density and isolates
    all zero crossings using bracketed bisection down to machine tolerance.
    """
    ts = np.arange(t_start, t_end + scan_step, scan_step)
    zs = np.array([hardy_z(t) for t in ts])
    
    signs = np.sign(zs)
    # Detect sign changes
    crossings = np.where(signs[:-1] * signs[1:] <= 0)[0]
    
    zeros = []
    for idx in crossings:
        a = float(ts[idx])
        b = float(ts[idx + 1])
        za = float(zs[idx])
        zb = float(zs[idx + 1])
        
        # Bisection / Brent refinement
        for _ in range(64):
            mid = (a + b) / 2.0
            zmid = hardy_z(mid)
            if abs(zmid) < 1e-13 or (b - a) < 1e-12:
                break
            if za * zmid <= 0:
                b = mid
                zb = zmid
            else:
                a = mid
                za = zmid
        zeros.append(mid)
        
    return zeros

def gue_wigner_surmise(s: np.ndarray) -> np.ndarray:
    """Gaussian Unitary Ensemble (GUE) Wigner surmise probability density."""
    return (32.0 / (math.pi ** 2)) * (s ** 2) * np.exp(-4.0 / math.pi * (s ** 2))

def poisson_distribution(s: np.ndarray) -> np.ndarray:
    """Poisson distribution for uncorrelated random eigenvalues."""
    return np.exp(-s)

def gue_cdf(s: float) -> float:
    """Analytical cumulative distribution function of the GUE Wigner surmise."""
    # Integral of (32/pi^2) * x^2 * exp(-4/pi * x^2) from 0 to s
    # = erf(2 * s / sqrt(pi)) - (4 * s / pi) * exp(-4/pi * s^2)
    k = 2.0 / math.sqrt(math.pi)
    erf_term = math.erf(k * s)
    exp_term = (4.0 * s / math.pi) * math.exp(-4.0 / math.pi * (s ** 2))
    return erf_term - exp_term

def analyze_spacings(zeros: list[float]):
    """
    Computes unfolded normalized spacings s_k and compares against GUE and Poisson.
    """
    z_arr = np.array(zeros, dtype=np.float64)
    diffs = np.diff(z_arr)
    midpoints = (z_arr[:-1] + z_arr[1:]) / 2.0
    
    # Local mean spacing: Delta_bar(t) = 2*pi / ln(t / (2*pi))
    mean_spacings = 2.0 * math.pi / np.log(midpoints / (2.0 * math.pi))
    normalized_spacings = diffs / mean_spacings
    
    mean_s = float(np.mean(normalized_spacings))
    var_s = float(np.var(normalized_spacings))
    std_s = float(np.std(normalized_spacings))
    min_s = float(np.min(normalized_spacings))
    max_s = float(np.max(normalized_spacings))
    
    # Kolmogorov-Smirnov test against GUE CDF
    sorted_s = np.sort(normalized_spacings)
    n = len(sorted_s)
    ks_stat = 0.0
    for i, val in enumerate(sorted_s):
        emp_cdf = (i + 1) / n
        theo_cdf = gue_cdf(val)
        ks_stat = max(ks_stat, abs(emp_cdf - theo_cdf))
        
    # Level repulsion index: fraction of spacings with s < 0.3
    level_repulsion_ratio = float(np.sum(normalized_spacings < 0.3)) / n
    
    # Histogram binning for density comparison
    bins = np.linspace(0.0, 2.5, 11)
    counts, _ = np.histogram(normalized_spacings, bins=bins, density=True)
    bin_centers = (bins[:-1] + bins[1:]) / 2.0
    
    gue_vals = gue_wigner_surmise(bin_centers)
    poisson_vals = poisson_distribution(bin_centers)
    
    mse_gue = float(np.mean((counts - gue_vals) ** 2))
    mse_poisson = float(np.mean((counts - poisson_vals) ** 2))
    
    return {
        "raw_diffs": diffs.tolist(),
        "normalized_spacings": normalized_spacings.tolist(),
        "statistics": {
            "count": int(n),
            "mean": mean_s,
            "variance": var_s,
            "std_dev": std_s,
            "min_spacing": min_s,
            "max_spacing": max_s,
            "ks_statistic_vs_gue": ks_stat,
            "level_repulsion_ratio_s_lt_0_3": level_repulsion_ratio,
            "mse_vs_gue_density": mse_gue,
            "mse_vs_poisson_density": mse_poisson
        },
        "histogram": {
            "bin_centers": bin_centers.tolist(),
            "empirical_density": counts.tolist(),
            "gue_density": gue_vals.tolist(),
            "poisson_density": poisson_vals.tolist()
        }
    }

def main():
    print("================================================================================")
    print(" Project Chimera: Prologue to Project Riemann")
    print(" Riemann-Siegel High-Precision Zero Calculator & Quantum Chaos GUE Analyzer")
    print(" Target Interval: t in [1000.0, 1050.0] on the Critical Line Re(s) = 1/2")
    print("================================================================================")
    
    t0 = time.time()
    t_start = 1000.0
    t_end = 1050.0
    
    print(f"\n[1/3] Scanning critical line t in [{t_start}, {t_end}] using Riemann-Siegel Z(t)...")
    zeros = find_critical_zeros(t_start, t_end, scan_step=0.02)
    elapsed_scan = time.time() - t0
    
    print(f"  -> Located {len(zeros)} non-trivial zeros in {elapsed_scan * 1000.0:.2f} ms")
    print("\nFirst 10 Isolated Non-Trivial Zeros:")
    print("  Index | Zero Coordinate (gamma_k) | Residual |Z(gamma_k)|")
    print("  ------+---------------------------+-----------------------")
    for i, z in enumerate(zeros[:10]):
        res = hardy_z(z)
        print(f"  #{i+1:3d}  | {z:19.10f}       | {abs(res):10.2e}")
    if len(zeros) > 10:
        print(f"  ... ({len(zeros) - 10} additional zeros computed)")
        
    print("\n[2/3] Computing Spectral Unfolding & Nearest-Neighbor Spacings s_k...")
    analysis = analyze_spacings(zeros)
    stats = analysis["statistics"]
    
    print(f"  -> Total Spacings Analyzed: {stats['count']}")
    print(f"  -> Mean Normalized Spacing <s_k>: {stats['mean']:.4f} (Theoretical: 1.0000)")
    print(f"  -> Spacing Variance Var(s_k):     {stats['variance']:.4f} (GUE: 0.1780 | Poisson: 1.0000)")
    print(f"  -> Min Spacing (Level Repulsion): {stats['min_spacing']:.4f}")
    print(f"  -> Spacings with s < 0.3:         {stats['level_repulsion_ratio_s_lt_0_3'] * 100.0:.1f}% (Poisson predicts 25.9%)")
    print(f"  -> Kolmogorov-Smirnov vs GUE:     {stats['ks_statistic_vs_gue']:.4f}")
    print(f"  -> Mean Squared Error vs GUE:     {stats['mse_vs_gue_density']:.6f}")
    print(f"  -> Mean Squared Error vs Poisson: {stats['mse_vs_poisson_density']:.6f}")
    
    ratio_proof = stats['mse_vs_poisson_density'] / max(stats['mse_vs_gue_density'], 1e-9)
    print(f"\n[+] GUE Alignment Ratio: GUE model fits {ratio_proof:.1f}x better than Poisson!")
    
    print("\n[3/3] Exporting GUE Baseline Dataset...")
    out_data = {
        "metadata": {
            "experiment": "Project Riemann: GUE Spectral Spacing Baseline",
            "interval": [t_start, t_end],
            "formula": "Riemann-Siegel asymptotic formula with C0(p) remainder",
            "total_zeros": len(zeros),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
            "accelerator": "Apple Silicon Accelerate / NumPy ASIMD"
        },
        "zeros": [{"index": i + 1, "gamma": z, "residual": hardy_z(z)} for i, z in enumerate(zeros)],
        "spectral_analysis": analysis
    }
    
    out_file = DATA_DIR / "riemann_gue_baseline.json"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out_data, f, indent=2)
        
    print(f"  -> Dataset saved to: {out_file} ({out_file.stat().st_size / 1024.0:.1f} KB)")
    print("================================================================================")
    print(" Project Riemann Prologue Complete.")
    print("================================================================================")

if __name__ == "__main__":
    main()
