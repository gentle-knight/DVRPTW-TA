"""
Static Vehicle Routing Problem with Time Windows (Static-VRPTW) baseline.

Planning: uses period-average travel time across all 12 intervals.
Evaluation: uses same dynamic TrafficManager as other algorithms.
No congestion cost during planning, no time-dependent optimization.

Corresponds to Baseline 1 in the paper (Sect 4.5).
"""

import numpy as np
from core.solution import Route, N_DEPOT, Solution
from core.initialization import build_greedy_init


class StaticTrafficManager:
    def __init__(self, base_traffic):
        avg_tt = np.mean(base_traffic.tensor[:, :, :, 0], axis=2)
        avg_tt[avg_tt >= 9999] = base_traffic._fallback_tt
        self.tt = avg_tt

    def travel_time(self, i, j, _departure):
        ok = (0 <= i < self.tt.shape[0] and 0 <= j < self.tt.shape[1])
        return float(self.tt[i, j]) if ok else 5.0

    def congestion_cost(self, i, j, _departure):
        return 0.0

    def adjusted_time(self, i, j, _departure):
        return self.travel_time(i, j, 0)

    def free_flow_time(self, i, j):
        return self.travel_time(i, j, 0)


def run_static_vrptw(traffic, demands, service_times, windows_open, windows_close,
                     n_vehicles=4, capacity=120.0, lambda_1=1.0, lambda_2=0.5,
                     seed=42):
    static_tm = StaticTrafficManager(traffic)
    sol = build_greedy_init(
        static_tm, demands, service_times, windows_open, windows_close,
        n_vehicles=n_vehicles, capacity=capacity,
        lambda_1=lambda_1, lambda_2=lambda_2, seed=seed)
    return sol, static_tm
