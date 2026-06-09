"""
Traffic-Aware VRPTW Greedy (TA-VRPTW-Greedy) baseline.

Uses time-dependent travel times and congestion penalties via TrafficManager,
but only performs greedy insertion without metaheuristic optimization.

Corresponds to Baseline 2 in the paper (Sect 4.5).
"""

import numpy as np
from core.initialization import build_greedy_init


def run_ta_greedy(traffic, demands, service_times, windows_open, windows_close,
                  n_vehicles=4, capacity=120.0, lambda_1=1.0, lambda_2=0.5,
                  seed=42):
    sol = build_greedy_init(
        traffic, demands, service_times, windows_open, windows_close,
        n_vehicles=n_vehicles, capacity=capacity,
        lambda_1=lambda_1, lambda_2=lambda_2, seed=seed)
    return sol
