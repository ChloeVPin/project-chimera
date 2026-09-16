"""
Project Chimera: Statistical Analysis & Curve Fitting for Phase 1 Data
"""

import json
import math
import sys
from pathlib import Path

def fit_quadratic(x_vals, y_vals):
    n = len(x_vals)
    # Solve normal equations for y = a*x^2 + b*x + c
    sum_x = sum(x_vals)
    sum_x2 = sum(x**2 for x in x_vals)
    sum_x3 = sum(x**3 for x in x_vals)
    sum_x4 = sum(x**4 for x in x_vals)
    sum_y = sum(y_vals)
    sum_xy = sum(x * y for x, y in zip(x_vals, y_vals))
    sum_x2y = sum((x**2) * y for x, y in zip(x_vals, y_vals))

    # Matrix A * [a, b, c]^T = B
    # A = [[sum_x4, sum_x3, sum_x2],
    #      [sum_x3, sum_x2, sum_x],
    #      [sum_x2, sum_x,  n]]
    A = [
        [sum_x4, sum_x3, sum_x2, sum_x2y],
        [sum_x3, sum_x2, sum_x,  sum_xy],
        [sum_x2, sum_x,  float(n), sum_y]
    ]
    # Gaussian elimination with partial pivoting:
    for i in range(3):
        max_row = max(range(i, 3), key=lambda r: abs(A[r][i]))
        A[i], A[max_row] = A[max_row], A[i]
        pivot = A[i][i]
        if abs(pivot) < 1e-12:
            return 0, 0, 0, 0
        for j in range(i, 4):
            A[i][j] /= pivot
        for r in range(3):
            if r != i:
                factor = A[r][i]
                for j in range(i, 4):
                    A[r][j] -= factor * A[i][j]
    a, b, c = A[0][3], A[1][3], A[2][3]

    # R^2 calculation
    y_mean = sum_y / n
    ss_tot = sum((y - y_mean)**2 for y in y_vals)
    ss_res = sum((y - (a * x**2 + b * x + c))**2 for x, y in zip(x_vals, y_vals))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0

    return a, b, c, r2

def main():
    data_path = Path("data/phase1_rule110_results.json")
    if not data_path.exists():
        print(f"Error: {data_path} not found")
        sys.exit(1)

    with open(data_path, "r") as f:
        data = json.load(f)

    print("=================================================================")
    print("Project Chimera: Phase 1 Empirical Statistical Regressions")
    print("=================================================================\n")

    # 1. Temporal Scaling
    exp1a = [m for m in data["exp1A_temporal"] if m["success"]]
    x_s = [m["parameters"]["steps"] for m in exp1a]
    y_inst = [m["instantiationCount"] for m in exp1a]
    y_mem = [m["compilerMemoryUsedKB"] / 1024.0 for m in exp1a] # MB

    try:
        a_inst, b_inst, c_inst, r2_inst = fit_quadratic(x_s, y_inst)
        print(f"[+] Temporal Scaling (Instantiations vs Steps S, N={len(x_s)}):")
        print(f"    Model: Inst(S) = {a_inst:.4f} * S^2 + {b_inst:.4f} * S + {c_inst:.4f}")
        print(f"    R^2 Goodness of Fit: {r2_inst:.6f}")
    except Exception as e:
        print("Note on numpy:", e)

    # 2. Spatial Scaling
    exp1b = [m for m in data["exp1B_spatial"] if m["success"]]
    x_w = [m["parameters"]["width"] for m in exp1b]
    y_w_inst = [m["instantiationCount"] for m in exp1b]
    try:
        a_w, b_w, c_w, r2_w = fit_quadratic(x_w, y_w_inst)
        print(f"\n[+] Spatial Scaling (Instantiations vs Width W at S=10, N={len(x_w)}):")
        print(f"    Model: Inst(W) = {a_w:.4f} * W^2 + {b_w:.4f} * W + {c_w:.4f}")
        print(f"    R^2 Goodness of Fit: {r2_w:.6f}")
    except Exception as e:
        print("Note on numpy:", e)

    print("\n[+] Circuit Breaker Boundaries:")
    print("    - Non-TCO Stack Frame Depth Limit: 48 frames (Blows at S=49 with TS2589)")
    print("    - Tail-Call Fuel Counter Limit:    999 steps  (Blows at S=1000 with TS2589)")
    print("    - Fuel/Stack Tolerance Factor:    20.81x")

if __name__ == "__main__":
    main()
