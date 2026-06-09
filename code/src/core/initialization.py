"""
Greedy initial solution construction (Sect 3.3.1).

Builds a feasible starting solution by inserting customers one-by-one
at the earliest feasible, cost-minimizing position. Uses full forward
propagation for cost evaluation (no incremental delta).

Corresponds to the S⁰ construction step in Algorithm 1.
"""

import numpy as np
from .solution import Solution, Route, N_DEPOT


def build_greedy_init(traffic, demands, service_times, windows_open, windows_close,
                      n_vehicles=4, capacity=120.0, lambda_1=1.0, lambda_2=0.5,
                      seed=None):
    if seed is not None:
        rng = np.random.RandomState(seed)
    else:
        rng = np.random.RandomState(42)

    n_customers = len(demands) - 1
    customer_ids = list(range(1, n_customers + 1))
    rng.shuffle(customer_ids)

    sol = Solution([Route() for _ in range(n_vehicles)])

    for cid in customer_ids:
        best_cost = float('inf')
        best_route_idx = -1
        best_position = -1
        best_route_copy = None

        demand_c = demands[cid]

        for v, route in enumerate(sol.routes):
            if route.total_demand(demands) + demand_c > capacity:
                continue

            nodes = route.customer_nodes()
            for pos in range(len(nodes) + 1):
                trial = route.copy()
                trial.nodes = trial.nodes[:1] + nodes[:pos] + [cid] + nodes[pos:] + [N_DEPOT]
                cost, _ = trial.compute_cost(
                    traffic, demands, service_times, windows_open, windows_close,
                    lambda_1=lambda_1, lambda_2=lambda_2,
                )
                if cost < best_cost:
                    best_cost = cost
                    best_route_idx = v
                    best_position = pos
                    best_route_copy = trial

        if best_route_idx == -1:
            for v, route in enumerate(sol.routes):
                nodes = route.customer_nodes()
                for pos in range(len(nodes) + 1):
                    trial = route.copy()
                    trial.nodes = trial.nodes[:1] + nodes[:pos] + [cid] + nodes[pos:] + [N_DEPOT]
                    if trial.total_demand(demands) <= capacity:
                        best_route_idx = v
                        best_position = pos
                        best_route_copy = trial
                        break
                if best_route_idx != -1:
                    break

        if best_route_idx == -1:
            raise RuntimeError(f"Cannot assign customer {cid}: all vehicles full or infeasible")

        sol.routes[best_route_idx] = best_route_copy

    return sol
