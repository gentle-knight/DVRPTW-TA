"""
Destroy operators for ALNS (Sect 3.3.1, Eq.15).

random_removal: uniform random selection of α·n customers.
worst_removal: remove customers with largest route cost contribution.
relatedness_removal: Shaw removal — remove customers similar to a seed.
"""

import numpy as np
from .solution import N_DEPOT


def _list_customers(solution):
    result = []
    for v, route in enumerate(solution.routes):
        for pos, cid in enumerate(route.customer_nodes()):
            result.append((v, pos, cid))
    return result


def _remove_at(solution, positions_reversed):
    removed = []
    for v, pos, cid in sorted(positions_reversed, key=lambda x: -x[1]):
        del solution.routes[v].nodes[pos + 1]
        removed.append(cid)
    return removed


def random_removal(solution, alpha=0.3, rng=None):
    all_custs = _list_customers(solution)
    n_remove = max(1, min(int(alpha * len(all_custs)), len(all_custs)))

    if rng is None:
        rng = np.random.RandomState()
    selected_idx = rng.choice(len(all_custs), size=n_remove, replace=False)

    return _remove_at(solution, [all_custs[i] for i in selected_idx])


def worst_removal(solution, alpha=0.3, traffic=None, demands=None,
                  service_times=None, windows_open=None, windows_close=None,
                  lambda_1=1.0, lambda_2=0.5, rng=None):
    all_custs = _list_customers(solution)
    n_total = len(all_custs)
    n_remove = max(1, min(int(alpha * n_total), n_total))

    if rng is None:
        rng = np.random.RandomState()

    deltas = np.zeros(n_total)
    for idx, (v, pos, cid) in enumerate(all_custs):
        route = solution.routes[v]
        nodes = route.customer_nodes()
        trial_nodes = [N_DEPOT] + nodes[:pos] + nodes[pos+1:] + [N_DEPOT]
        from .solution import Route
        trial = Route(trial_nodes)
        trial.departure_time = route.departure_time
        cost_removed, _ = trial.compute_cost(
            traffic, demands, service_times, windows_open, windows_close,
            lambda_1=lambda_1, lambda_2=lambda_2)
        cost_full, _ = route.compute_cost(
            traffic, demands, service_times, windows_open, windows_close,
            lambda_1=lambda_1, lambda_2=lambda_2)
        deltas[idx] = cost_full - cost_removed

    worst_idx = np.argsort(-deltas)[:n_remove]
    return _remove_at(solution, [all_custs[i] for i in worst_idx])


def relatedness_removal(solution, alpha=0.3, traffic=None, demands=None,
                        windows_open=None, windows_close=None,
                        rng=None, det_p=5):
    all_custs = _list_customers(solution)
    n_total = len(all_custs)
    n_remove = max(1, min(int(alpha * n_total), n_total))

    if rng is None:
        rng = np.random.RandomState()

    cust_ids = [c for (_, _, c) in all_custs]
    cust_tw = [(windows_open[c], windows_close[c]) for c in cust_ids]
    cust_dem = [demands[c] for c in cust_ids]

    travel_max = 0.0
    for i, ci in enumerate(cust_ids):
        for j, cj in enumerate(cust_ids):
            if i >= j:
                continue
            t = traffic.free_flow_time(ci, cj)
            if t > travel_max:
                travel_max = t
    travel_max = max(travel_max, 1.0)

    tw_span = max(1.0, max(wc - wo for wo, wc in cust_tw))
    dem_span = max(1.0, max(cust_dem) - min(cust_dem))

    seed_idx = rng.randint(0, n_total)
    removed_set = set()
    removed_list = []
    current_seed = seed_idx

    while len(removed_list) < n_remove and len(removed_set) < n_total:
        removed_set.add(current_seed)
        removed_list.append(current_seed)
        if len(removed_list) >= n_remove:
            break

        relatedness = np.full(n_total, np.inf)
        for i in range(n_total):
            if i in removed_set:
                continue
            t = traffic.free_flow_time(cust_ids[current_seed], cust_ids[i])
            tw_diff = abs(cust_tw[current_seed][0] - cust_tw[i][0])
            dem_diff = abs(cust_dem[current_seed] - cust_dem[i])
            R = 0.4 * t / travel_max + 0.35 * tw_diff / tw_span + 0.25 * dem_diff / dem_span
            relatedness[i] = R

        candidates = np.argsort(relatedness)[:det_p]
        picked = candidates[rng.randint(0, min(det_p, len(candidates)))]
        current_seed = picked

    return _remove_at(solution, [all_custs[i] for i in removed_list])
