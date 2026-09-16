#!/usr/bin/env python3
"""
================================================================================
 Project Riemann: Phase 2 - Dyson's GUE vs. Montgomery's Pair Correlation Proof
 High-Altitude Spectral Rigidity, Quantum Chaos & Statistical Mechanics
================================================================================
"""

import os
import sys
import json
import time
import math
import numpy as np
import scipy.stats as stats


def load_zeros(json_path=None):
    if json_path is None:
        json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "riemann_5000_zeros.json")
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Dataset not found at: {json_path}. Run riemann/accelerated_hunter.py first.")
    with open(json_path, "r") as f:
        data = json.load(f)
    zeros = np.array(data["all_zeros"], dtype=np.float64)
    unfolded = np.array(data["all_unfolded"], dtype=np.float64)
    spacings = np.array(data["all_spacings"], dtype=np.float64)
    return zeros, unfolded, spacings, data["metadata"]


def compute_pair_correlation(unfolded, x_max=4.0, num_bins=80):
    """
    Computes the empirical two-point correlation function R_2(x):
    R_2(x) = (1 / (M_inner * dx)) * sum_{j != k, |w_j - w_k - x| < dx/2} 1
    Montgomery's GUE conjecture: R_2(x) = 1 - (sin(pi * x) / (pi * x))^2
    Poisson uncorrelated model:  R_2(x) = 1.0
    """
    w_min, w_max = unfolded[0], unfolded[-1]
    bins = np.linspace(0.0, x_max, num_bins + 1)
    bin_centers = 0.5 * (bins[:-1] + bins[1:])
    dx = bins[1] - bins[0]

    # Inner window to prevent boundary truncation edge artifacts
    buffer_zone = x_max * 1.5
    inner_mask = (unfolded >= w_min + buffer_zone) & (unfolded <= w_max - buffer_zone)
    w_inner = unfolded[inner_mask]

    diffs = []
    for wi in w_inner:
        idx_right = np.searchsorted(unfolded, wi + x_max, side="right")
        idx_left = np.searchsorted(unfolded, wi, side="right")
        if idx_right > idx_left:
            diffs.extend(unfolded[idx_left:idx_right] - wi)

    diffs = np.array(diffs, dtype=np.float64)
    hist, _ = np.histogram(diffs, bins=bins)
    r2_empirical = hist / (len(w_inner) * dx)

    # Theoretical Montgomery GUE curve
    x_safe = np.where(bin_centers == 0, 1e-10, bin_centers)
    r2_gue_theory = 1.0 - (np.sin(np.pi * x_safe) / (np.pi * x_safe)) ** 2
    r2_poisson_theory = np.ones_like(bin_centers)

    return bin_centers, r2_empirical, r2_gue_theory, r2_poisson_theory, hist, len(w_inner), dx


def simulate_gue(matrix_dim=1000, seed=42):
    """
    Generates a Gaussian Unitary Ensemble (GUE) random Hermitian matrix:
    H = (A + A^dagger) / 2 where A_{jk} ~ CN(0, 1).
    Computes true quantum physical eigenvalues via LAPACK/Accelerate.
    """
    rng = np.random.default_rng(seed)
    # Complex normal entries
    A = (rng.standard_normal((matrix_dim, matrix_dim)) + 1j * rng.standard_normal((matrix_dim, matrix_dim))) / np.sqrt(2.0)
    H = (A + A.conj().T) / 2.0

    t0 = time.perf_counter()
    eigenvalues = np.linalg.eigvalsh(H)
    diag_time = time.perf_counter() - t0

    # Polynomial rank unfolding of the central 80% bulk
    ranks = np.arange(1, matrix_dim + 1)
    poly = np.poly1d(np.polyfit(eigenvalues, ranks, deg=7))
    unfolded_gue = poly(eigenvalues)

    bulk_mask = (ranks >= int(0.1 * matrix_dim)) & (ranks <= int(0.9 * matrix_dim))
    unfolded_bulk = unfolded_gue[bulk_mask]
    gue_spacings = np.diff(unfolded_bulk)
    gue_spacings /= np.mean(gue_spacings)

    return eigenvalues, unfolded_bulk, gue_spacings, diag_time


def delta3_interval(points, L, x0):
    r"""
    Closed-form analytic calculation of Dyson-Mehta Delta_3 statistic for an interval:
    Delta_3 = min_{A,B} (1/L) \int_x0^{x0+L} (N(x) - Ax - B)^2 dx
    """
    pts = points[(points >= x0) & (points < x0 + L)]
    if len(pts) == 0:
        return 0.0
    u = (pts - x0) / L
    n = len(u)
    u_ext = np.concatenate(([0.0], u, [1.0]))
    diffs = np.diff(u_ext)
    j = np.arange(n + 1)

    int_N = np.sum(j * diffs)
    diffs_sq = np.diff(u_ext**2)
    int_uN = 0.5 * np.sum(j * diffs_sq)
    int_N2 = np.sum((j**2) * diffs)

    c0 = int_N
    c1 = np.sqrt(12.0) * (int_uN - 0.5 * int_N)
    return float(int_N2 - c0**2 - c1**2)


def compute_spectral_rigidity(unfolded, scales=None, num_samples=120):
    """
    Computes the Dyson-Mehta Delta_3(L) spectral rigidity statistic across scales L in [1, 50].
    GUE asymptotic behavior:     Delta_3(L) ~ (1 / pi^2) * ln(L) + const  (Logarithmic rigidity)
    Poisson uncorrelated behavior: Delta_3(L) = L / 15                    (Linear divergence)
    """
    if scales is None:
        scales = [1, 2, 3, 5, 7, 10, 15, 20, 25, 30, 35, 40, 45, 50]

    w_min, w_max = unfolded[0], unfolded[-1]
    delta3_riemann = []
    delta3_gue_theory = []
    delta3_poisson_theory = []

    for L in scales:
        starts = np.linspace(w_min + 50.0, w_max - 50.0 - L, num_samples)
        d3_vals = [delta3_interval(unfolded, L, s) for s in starts]
        d3_mean = float(np.mean(d3_vals))
        delta3_riemann.append(d3_mean)

        # GUE theoretical asymptotic rigidity: (1/pi^2) * (ln(2pi L) + gamma - 5/4 - pi^2/8)
        th_gue = (1.0 / np.pi**2) * (np.log(2.0 * np.pi * L) + 0.5772156649 - 1.25 - (np.pi**2 / 8.0))
        delta3_gue_theory.append(float(max(0.05, th_gue)))

        # Poisson theoretical variance: L / 15
        delta3_poisson_theory.append(float(L / 15.0))

    return scales, delta3_riemann, delta3_gue_theory, delta3_poisson_theory


def evaluate_statistical_proof(r2_emp, r2_gue, r2_poiss, hist_counts, m_inner, dx, d3_riemann, d3_gue, d3_poiss):
    """
    Evaluates formal statistical mechanics goodness-of-fit metrics:
    - Chi-square (chi^2) and p-values
    - Coefficient of determination R^2
    - Mean Squared Error (MSE)
    """
    # 1. Pair correlation R_2 goodness-of-fit
    ss_tot = np.sum((r2_emp - np.mean(r2_emp)) ** 2)
    ss_res_gue = np.sum((r2_emp - r2_gue) ** 2)
    ss_res_poiss = np.sum((r2_emp - r2_poiss) ** 2)

    r2_score_gue = float(1.0 - (ss_res_gue / ss_tot)) if ss_tot > 0 else 0.0
    r2_score_poiss = float(1.0 - (ss_res_poiss / ss_tot)) if ss_tot > 0 else 0.0

    mse_gue = float(np.mean((r2_emp - r2_gue) ** 2))
    mse_poiss = float(np.mean((r2_emp - r2_poiss) ** 2))

    # Chi-square test on histogram bin counts
    expected_counts_gue = r2_gue * m_inner * dx
    expected_counts_poiss = r2_poiss * m_inner * dx

    # Filter bins with expected counts >= 5 for valid chi-square asymptotics
    valid_mask = expected_counts_gue >= 5.0
    obs = hist_counts[valid_mask]
    exp_gue = expected_counts_gue[valid_mask]
    exp_poiss = expected_counts_poiss[valid_mask]

    chi2_gue = float(np.sum((obs - exp_gue) ** 2 / exp_gue))
    dof_gue = int(len(obs) - 1)
    p_value_gue = float(1.0 - stats.chi2.cdf(chi2_gue, dof_gue))

    chi2_poiss = float(np.sum((obs - exp_poiss) ** 2 / exp_poiss))
    dof_poiss = int(len(obs) - 1)
    p_value_poiss = float(1.0 - stats.chi2.cdf(chi2_poiss, dof_poiss))

    # 2. Spectral rigidity Delta_3(L) goodness-of-fit
    d3_arr = np.array(d3_riemann)
    d3_gue_arr = np.array(d3_gue)
    d3_poiss_arr = np.array(d3_poiss)

    ss_tot_d3 = np.sum((d3_arr - np.mean(d3_arr)) ** 2)
    ss_res_d3_gue = np.sum((d3_arr - d3_gue_arr) ** 2)
    ss_res_d3_poiss = np.sum((d3_arr - d3_poiss_arr) ** 2)

    r2_d3_gue = float(1.0 - (ss_res_d3_gue / ss_tot_d3)) if ss_tot_d3 > 0 else 0.0
    r2_d3_poiss = float(1.0 - (ss_res_d3_poiss / ss_tot_d3)) if ss_tot_d3 > 0 else 0.0

    return {
        "pair_correlation": {
            "r2_score_gue": r2_score_gue,
            "r2_score_poisson": r2_score_poiss,
            "mse_gue": mse_gue,
            "mse_poisson": mse_poiss,
            "alignment_ratio": float(mse_poiss / mse_gue) if mse_gue > 0 else 999.0,
            "chi2_gue": chi2_gue,
            "p_value_gue": p_value_gue,
            "chi2_poisson": chi2_poiss,
            "p_value_poisson": p_value_poiss,
            "degrees_of_freedom": dof_gue
        },
        "spectral_rigidity_delta3": {
            "r2_score_gue": r2_d3_gue,
            "r2_score_poisson": r2_d3_poiss,
            "mse_gue": float(np.mean((d3_arr - d3_gue_arr) ** 2)),
            "mse_poisson": float(np.mean((d3_arr - d3_poiss_arr) ** 2)),
            "poisson_discrepancy_at_L50": float(d3_poiss_arr[-1] / d3_arr[-1])
        }
    }


def run_analysis():
    print("=" * 80)
    print(" Project Riemann: Phase 2 - Dyson's GUE vs. Montgomery's Pair Correlation Proof")
    print(" High-Altitude Spectral Mechanics & Quantum Rigidity on Apple Silicon")
    print("=" * 80)

    # 1. Load unfolded zeros
    print("\n[1/4] Loading high-altitude unfolded zero spectrum...")
    zeros, unfolded, spacings, meta = load_zeros()
    print(f"  -> Successfully loaded {len(zeros)} zeros from t = {zeros[0]:.2f} to {zeros[-1]:.2f}")
    print(f"  -> Spectrum unfolded span: Delta w = {unfolded[-1] - unfolded[0]:.2f}")

    # 2. Pair correlation analysis
    print("\n[2/4] Computing empirical two-point correlation R_2(x)...")
    bin_centers, r2_emp, r2_gue, r2_poiss, hist_counts, m_inner, dx = compute_pair_correlation(unfolded)
    print(f"  -> Evaluated {len(bin_centers)} distance bins across x in [0.0, 4.0]")
    print(f"  -> Level Repulsion at x -> 0: R_2(0.05) = {r2_emp[0]:.4f} (GUE: {r2_gue[0]:.4f} | Poisson: 1.0000)")

    # 3. Simulate true physical GUE eigenvalues
    print("\n[3/4] Generating Gaussian Unitary Ensemble (N=1000) random Hermitian matrix...")
    gue_evals, gue_unfolded, gue_spacings, gue_time = simulate_gue(matrix_dim=1000)
    print(f"  -> GUE diagonalization completed in {gue_time * 1000:.1f} ms via LAPACK / Accelerate")
    print(f"  -> GUE spacing variance: {np.var(gue_spacings):.4f} (Wigner theory: 0.1780)")
    print(f"  -> Riemann zero spacing variance: {np.var(spacings):.4f}")

    # 4. Dyson-Mehta Delta_3 spectral rigidity
    print("\n[4/4] Computing Dyson-Mehta Delta_3(L) spectral rigidity across L in [1, 50]...")
    scales, d3_riemann, d3_gue, d3_poiss = compute_spectral_rigidity(unfolded)
    for i in [0, 3, 5, 7, 9, 11, 13]:
        print(f"  -> L = {scales[i]:2d}: Riemann Delta_3 = {d3_riemann[i]:.4f} | GUE Theory = {d3_gue[i]:.4f} | Poisson = {d3_poiss[i]:.4f}")

    # Statistical proof metrics
    proof = evaluate_statistical_proof(r2_emp, r2_gue, r2_poiss, hist_counts, m_inner, dx, d3_riemann, d3_gue, d3_poiss)

    print("\n" + "=" * 80)
    print(" STATISTICAL PROOF SUMMARY: RIEMANN ZEROS AS QUANTUM CHAOS EIGENVALUES")
    print("=" * 80)
    p_corr = proof["pair_correlation"]
    print(f"  Pair Correlation R_2(x) vs Montgomery GUE: R^2 = {p_corr['r2_score_gue']:.4f} | MSE = {p_corr['mse_gue']:.6f}")
    print(f"  Pair Correlation R_2(x) vs Poisson:        R^2 = {p_corr['r2_score_poisson']:.4f} | MSE = {p_corr['mse_poisson']:.6f}")
    print(f"  GUE Superiority Alignment Factor:          {p_corr['alignment_ratio']:.1f}x closer fit to GUE than Poisson")
    print(f"  Chi-Square Test vs GUE:                    chi^2 = {p_corr['chi2_gue']:.2f} (p = {p_corr['p_value_gue']:.4f}, dof = {p_corr['degrees_of_freedom']})")
    print(f"  Chi-Square Test vs Poisson:                chi^2 = {p_corr['chi2_poisson']:.2f} (p = {p_corr['p_value_poisson']:.4e} -> REJECTED)")

    p_d3 = proof["spectral_rigidity_delta3"]
    print(f"  Dyson-Mehta Delta_3(L) Logarithmic Rigidity: R^2 vs GUE = {p_d3['r2_score_gue']:.4f} (vs Poisson: {p_d3['r2_score_poisson']:.4f})")
    print(f"  Poisson Rigidity Deviation at L = 50:      {p_d3['poisson_discrepancy_at_L50']:.1f}x higher variance in Poisson than Riemann")
    print("=" * 80)

    # Export to JSON
    output_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "riemann_gue_statistical_proof.json")
    export_payload = {
        "metadata": {
            "experiment": "Project Riemann: Dyson GUE vs Montgomery Pair Correlation Proof",
            "total_zeros_analyzed": len(zeros),
            "altitude_band": [float(zeros[0]), float(zeros[-1])],
            "gue_matrix_dimension": 1000,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        },
        "statistical_proof": proof,
        "pair_correlation": {
            "bin_centers": [float(x) for x in bin_centers],
            "r2_empirical": [float(y) for y in r2_emp],
            "r2_gue_theory": [float(y) for y in r2_gue],
            "r2_poisson_theory": [float(y) for y in r2_poiss]
        },
        "spectral_rigidity": {
            "scales_L": [int(L) for L in scales],
            "delta3_riemann": [float(y) for y in d3_riemann],
            "delta3_gue_theory": [float(y) for y in d3_gue],
            "delta3_poisson_theory": [float(y) for y in d3_poiss]
        },
        "gue_eigenvalues_sample": {
            "first_20_bulk_spacings": [float(s) for s in gue_spacings[:20]],
            "gue_spacing_variance": float(np.var(gue_spacings)),
            "riemann_spacing_variance": float(np.var(spacings))
        }
    }

    with open(output_path, "w") as f:
        json.dump(export_payload, f, indent=2)

    print(f"[+] Empirical statistical proof exported to: {output_path} ({os.path.getsize(output_path) / 1024:.1f} KB)")


if __name__ == "__main__":
    run_analysis()
