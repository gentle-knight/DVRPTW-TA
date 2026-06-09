"""
Rollout simulation for candidate dispatch actions (Sect 3.3.3, Eqs.35, 37).

For each candidate action, forward-simulate the affected routes for a
fixed horizon (60 min default) using the traffic manager. Returns
rollout_cost, stability_penalty, and recovery_penalty.
"""

import numpy as np
from core.solution import N_DEPOT


def rollout_cost(solution, traffic, demands, service_times,
                 windows_open, windows_close, lambda_1, lambda_2,
                 horizon_minutes=60,
                 blocked_arc=None):
    travel_total = 0.0
    congestion_total = 0.0
    lateness_total = 0.0

    for route in solution.routes:
        nodes = route.nodes
        T = route.departure_time
        prev = nodes[0]
        horizon_end = T + horizon_minutes

        for nid in nodes[1:]:
            if nid == N_DEPOT:
                tt = traffic.travel_time(prev, nid, T)
                if blocked_arc and (prev, nid) == blocked_arc:
                    tt *= 3.0
                travel_total += tt
                congestion_total += traffic.congestion_cost(prev, nid, T)
                T += tt
                break

            tt = traffic.travel_time(prev, nid, T)
            cc = traffic.congestion_cost(prev, nid, T)

            if blocked_arc and (prev, nid) == blocked_arc:
                tt *= 3.0

            travel_total += tt
            congestion_total += cc

            A = T + tt
            S = max(A, windows_open[nid])
            delta = max(0.0, S - windows_close[nid])
            lateness_total += delta
            T = S + service_times[nid]
            prev = nid

            if T >= horizon_end:
                break

    return travel_total + lambda_2 * congestion_total + lambda_1 * lateness_total


def stability_penalty(candidate_solution, original_solution):
    penalty = 0.0
    for v, (c_route, o_route) in enumerate(zip(candidate_solution.routes, original_solution.routes)):
        c_set = set(c_route.customer_nodes())
        o_set = set(o_route.customer_nodes())
        union = len(c_set | o_set)
        intersection = len(c_set & o_set)
        if union > 0:
            jaccard = intersection / union
            penalty += (1.0 - jaccard) * 20.0
    return penalty


def recovery_penalty(candidate_solution, original_solution):
    penalty = 0.0
    for v, (c_route, o_route) in enumerate(zip(candidate_solution.routes, original_solution.routes)):
        c_custs = c_route.customer_nodes()
        o_custs = o_route.customer_nodes()
        for i, cid in enumerate(c_custs):
            if cid in o_custs:
                orig_pos = o_custs.index(cid)
                penalty += abs(i - orig_pos) * 5.0
    return penalty


def evaluate_candidate(candidate, original_solution, traffic, demands, service_times,
                       windows_open, windows_close, lambda_1, lambda_2,
                       horizon_minutes=60, blocked_arc=None, tabu_penalty=0.0):
    if candidate['name'] == 'subcontract':
        rc = candidate.get('subcontract_penalty', 50.0)
    else:
        rc = rollout_cost(
            candidate['solution'], traffic, demands, service_times,
            windows_open, windows_close, lambda_1, lambda_2,
            horizon_minutes=horizon_minutes, blocked_arc=blocked_arc,
        )

    sp = stability_penalty(candidate['solution'], original_solution)
    rp = recovery_penalty(candidate['solution'], original_solution)
    tp = tabu_penalty

    score = rc + sp + rp + tp
    return score, rc, sp, rp
