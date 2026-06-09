"""
Repair operators for ALNS (Sect 3.3.1, Eqs. 16–17).

greedy_insertion: insert each customer at cheapest position.
regret2_insertion: insert customer with max (cost_2nd_best − cost_best).
tw_aware_insertion: prioritize customers with tightest time windows.
"""

import numpy as np
from .solution import Route, N_DEPOT


def _eval_insertion(route, cid, traffic, demands, service_times,
                    windows_open, windows_close, lambda_1, lambda_2):
    nodes = route.customer_nodes()
    best_cost = float('inf')
    second_best = float('inf')
    best_nodes = None

    for pos in range(len(nodes) + 1):
        trial_nodes = [N_DEPOT] + nodes[:pos] + [cid] + nodes[pos:] + [N_DEPOT]
        trial = Route(trial_nodes)
        trial.departure_time = route.departure_time
        cost, _ = trial.compute_cost(
            traffic, demands, service_times, windows_open, windows_close,
            lambda_1=lambda_1, lambda_2=lambda_2)
        if cost < best_cost:
            second_best = best_cost
            best_cost = cost
            best_nodes = trial_nodes
        elif cost < second_best:
            second_best = cost

    return best_nodes, best_cost, second_best


def greedy_insertion(solution, removed_customers, traffic, demands,
                     service_times, windows_open, windows_close,
                     lambda_1=1.0, lambda_2=0.5, rng=None):
    if rng is None:
        rng = np.random.RandomState()
    shuffled = list(removed_customers)
    rng.shuffle(shuffled)

    for cid in shuffled:
        best_nodes = None
        best_cost_val = float('inf')
        best_v = -1
        for v, route in enumerate(solution.routes):
            nodes, cost, _ = _eval_insertion(
                route, cid, traffic, demands, service_times,
                windows_open, windows_close, lambda_1, lambda_2)
            if nodes is not None and cost < best_cost_val:
                best_cost_val = cost
                best_nodes = nodes
                best_v = v
        if best_nodes is None:
            raise RuntimeError(f'Cannot reinsert customer {cid}')
        solution.routes[best_v].nodes = best_nodes


def regret2_insertion(solution, removed_customers, traffic, demands,
                      service_times, windows_open, windows_close,
                      lambda_1=1.0, lambda_2=0.5, rng=None):
    remaining = set(removed_customers)

    while remaining:
        best_regret = -1.0
        best_cid = None
        best_info = None

        for cid in list(remaining):
            best_nodes = None
            best_cost = float('inf')
            second_cost = float('inf')
            best_v = -1

            for v, route in enumerate(solution.routes):
                nodes, c1, c2 = _eval_insertion(
                    route, cid, traffic, demands, service_times,
                    windows_open, windows_close, lambda_1, lambda_2)
                if nodes is not None and c1 < best_cost:
                    second_cost = best_cost
                    best_cost = c1
                    best_nodes = nodes
                    best_v = v
                elif nodes is not None and c1 < second_cost:
                    second_cost = c1

            if best_nodes is None:
                continue
            regret = second_cost - best_cost
            if regret > best_regret:
                best_regret = regret
                best_cid = cid
                best_info = (best_v, best_nodes)

        if best_cid is None:
            best_cid = next(iter(remaining))
            for v, route in enumerate(solution.routes):
                nodes, cost, _ = _eval_insertion(
                    route, best_cid, traffic, demands, service_times,
                    windows_open, windows_close, lambda_1, lambda_2)
                if nodes is not None:
                    best_info = (v, nodes)
                    break

        solution.routes[best_info[0]].nodes = best_info[1]
        remaining.discard(best_cid)


def tw_aware_insertion(solution, removed_customers, traffic, demands,
                       service_times, windows_open, windows_close,
                       lambda_1=1.0, lambda_2=0.5, rng=None):
    remaining = set(removed_customers)

    while remaining:
        best_score = float('inf')
        best_cid = None
        best_info = None

        for cid in list(remaining):
            best_nodes = None
            best_cost = float('inf')
            best_v = -1

            for v, route in enumerate(solution.routes):
                nodes, cost, _ = _eval_insertion(
                    route, cid, traffic, demands, service_times,
                    windows_open, windows_close, lambda_1, lambda_2)
                if nodes is not None and cost < best_cost:
                    best_cost = cost
                    best_nodes = nodes
                    best_v = v

            if best_nodes is None:
                continue

            tw_tightness = 1.0 / max(1.0, windows_close[cid] - windows_open[cid])
            score = best_cost - 50.0 * tw_tightness
            if score < best_score:
                best_score = score
                best_cid = cid
                best_info = (best_v, best_nodes)

        if best_cid is None:
            best_cid = next(iter(remaining))
            for v, route in enumerate(solution.routes):
                nodes, cost, _ = _eval_insertion(
                    route, best_cid, traffic, demands, service_times,
                    windows_open, windows_close, lambda_1, lambda_2)
                if nodes is not None:
                    best_info = (v, nodes)
                    break

        solution.routes[best_info[0]].nodes = best_info[1]
        remaining.discard(best_cid)
