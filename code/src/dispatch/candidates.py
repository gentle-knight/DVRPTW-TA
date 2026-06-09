"""
Candidate action generation for each event type (Sect 3.3.3).

E1_TRAFFIC: local reroute, customer reassignment, service postponement
E2_URGENT: urgent insertion, delayed insertion, subcontract
E4_TIME_RISK: local resequencing, tolerance relax
"""

import numpy as np
from core.solution import Route, N_DEPOT


def _copy_solution(solution):
    return solution.copy()


def generate_candidates_traffic(event, solution, traffic, demands, service_times,
                                windows_open, windows_close, lambda_1, lambda_2, rng):
    candidates = []
    v = event['vehicle']
    cust_b = event['affected_customer']
    blocked_tt = event['blocked_travel_time']

    route = solution.routes[v]
    custs = route.customer_nodes()
    pos = custs.index(cust_b)
    cust_a = custs[pos - 1] if pos > 0 else route.nodes[0]

    # Candidate set 0: k-shortest detours (paper: K_s=5, Δ_max=8 min)
    all_cust_ids = list(range(1, len(demands)))
    rng.shuffle(all_cust_ids)
    detour_samples = all_cust_ids[:min(30, len(all_cust_ids))]
    original_tt = traffic.travel_time(cust_a, cust_b, 0)
    # Collect all served customers across all routes (Eq.3: each served once)
    all_served = set()
    for r in solution.routes:
        all_served.update(r.customer_nodes())
    detours = []
    for mid_id in detour_samples:
        if mid_id == cust_a or mid_id == cust_b or mid_id in all_served:
            continue
        detour_time = traffic.travel_time(cust_a, mid_id, 0) + traffic.travel_time(mid_id, cust_b, 0)
        extra = detour_time - original_tt
        if extra <= 8.0:
            detours.append((mid_id, extra))
    detours.sort(key=lambda x: x[1])
    for mid_id, _ in detours[:5]:
        sol = solution.copy()
        r = sol.routes[v]
        c = r.customer_nodes()
        c.insert(pos, mid_id)
        r.nodes = [N_DEPOT] + c + [N_DEPOT]
        candidates.append({'name': f'detour_via_{mid_id}', 'solution': sol, 'cost': None})

    # Candidate 1: local reroute — swap position of affected customer
    if pos + 1 < len(custs):
        sol1 = solution.copy()
        r1 = sol1.routes[v]
        c1 = r1.customer_nodes()
        c1[pos], c1[pos + 1] = c1[pos + 1], c1[pos]
        r1.nodes = [N_DEPOT] + c1 + [N_DEPOT]
        candidates.append({'name': 'local_reroute', 'solution': sol1, 'cost': None})

    # Candidate 2: customer reassignment — move to another vehicle
    for v2 in range(len(solution.routes)):
        if v2 == v:
            continue
        sol2 = solution.copy()
        c2_list = sol2.routes[v].customer_nodes()
        del c2_list[pos]
        sol2.routes[v].nodes = [N_DEPOT] + c2_list + [N_DEPOT]

        target_route = sol2.routes[v2]
        target_custs = target_route.customer_nodes()
        best_pos = 0
        best_cost = float('inf')
        best_nodes = None
        for p in range(len(target_custs) + 1):
            trial_nodes = [N_DEPOT] + target_custs[:p] + [cust_b] + target_custs[p:] + [N_DEPOT]
            trial = Route(trial_nodes)
            trial.departure_time = target_route.departure_time
            c, _ = trial.compute_cost(traffic, demands, service_times, windows_open, windows_close, lambda_1, lambda_2)
            if c < best_cost:
                best_cost = c
                best_nodes = trial_nodes
        if best_nodes:
            sol2.routes[v2].nodes = best_nodes
            candidates.append({'name': f'reassign_to_V{v2+1}', 'solution': sol2, 'cost': None})

    # Candidate 3: service postponement — delay service and accept lateness
    sol3 = solution.copy()
    r3 = sol3.routes[v]
    c3 = r3.customer_nodes()
    if pos + 1 < len(c3):
        c3[pos], c3[pos + 1] = c3[pos + 1], c3[pos]
    r3.nodes = [N_DEPOT] + c3 + [N_DEPOT]
    candidates.append({'name': 'service_postponement', 'solution': sol3, 'cost': None})

    return candidates


def generate_candidates_urgent(event, solution, traffic, demands_orig, service_times_orig,
                               windows_open_orig, windows_close_orig, lambda_1, lambda_2, rng):
    candidates = []
    new_id = event['new_id']
    new_demand = event['demand']
    new_service = event['service_time']
    new_tw_open = event['tw_open']
    new_tw_close = event['tw_close']

    n = len(demands_orig)
    demands_ext = np.zeros(n + 1, dtype=np.float32)
    demands_ext[:n] = demands_orig
    demands_ext[new_id] = new_demand

    service_times_ext = np.zeros(n + 1, dtype=np.float32)
    service_times_ext[:n] = service_times_orig
    service_times_ext[new_id] = new_service

    windows_open_ext = np.zeros(n + 1, dtype=np.float32)
    windows_open_ext[:n] = windows_open_orig
    windows_open_ext[new_id] = new_tw_open

    windows_close_ext = np.zeros(n + 1, dtype=np.float32)
    windows_close_ext[:n] = windows_close_orig
    windows_close_ext[new_id] = new_tw_close

    # Candidate 1: urgent insertion — insert at cheapest position
    best_cost = float('inf')
    best_sol = None
    for v in range(len(solution.routes)):
        sol = solution.copy()
        route = sol.routes[v]
        custs = route.customer_nodes()
        for p in range(len(custs) + 1):
            trial_nodes = [N_DEPOT] + custs[:p] + [new_id] + custs[p:] + [N_DEPOT]
            trial = Route(trial_nodes)
            trial.departure_time = route.departure_time
            c, _ = trial.compute_cost(traffic, demands_ext, service_times_ext, windows_open_ext, windows_close_ext, lambda_1, lambda_2)
            if c < best_cost:
                best_cost = c
                sol.routes[v].nodes = trial_nodes
                best_sol = sol
    if best_sol:
        candidates.append({'name': 'urgent_insertion', 'solution': best_sol, 'cost': best_cost,
                           'extended_data': (demands_ext, service_times_ext, windows_open_ext, windows_close_ext)})

    # Candidate 2: delayed insertion (shift TW by 30min)
    windows_close_delayed = windows_close_ext.copy()
    windows_close_delayed[new_id] += 30
    best_cost_delayed = float('inf')
    best_sol_delayed = None
    for v in range(len(solution.routes)):
        sol = solution.copy()
        route = sol.routes[v]
        custs = route.customer_nodes()
        for p in range(len(custs) + 1):
            trial_nodes = [N_DEPOT] + custs[:p] + [new_id] + custs[p:] + [N_DEPOT]
            trial = Route(trial_nodes)
            trial.departure_time = route.departure_time
            c, _ = trial.compute_cost(traffic, demands_ext, service_times_ext, windows_open_ext, windows_close_delayed, lambda_1, lambda_2)
            if c < best_cost_delayed:
                best_cost_delayed = c
                sol.routes[v].nodes = trial_nodes
                best_sol_delayed = sol
    if best_sol_delayed:
        candidates.append({'name': 'delayed_insertion', 'solution': best_sol_delayed, 'cost': best_cost_delayed,
                           'extended_data': (demands_ext, service_times_ext, windows_open_ext, windows_close_delayed)})

    # Candidate 3: subcontract — keep current solution, pay penalty
    candidates.append({'name': 'subcontract', 'solution': solution.copy(), 'cost': None,
                       'subcontract_penalty': 50.0})

    return candidates


def generate_candidates_time_risk(event, solution, traffic, demands, service_times,
                                  windows_open, windows_close, lambda_1, lambda_2, rng):
    candidates = []
    v = event['vehicle']
    cust_at_risk = event['customer']

    route = solution.routes[v]
    custs = route.customer_nodes()
    pos = custs.index(cust_at_risk)

    # Candidate 1: local resequencing — move at-risk customer earlier in route
    if pos > 0:
        for offset in range(1, min(4, pos + 1)):
            sol = solution.copy()
            r = sol.routes[v]
            c = r.customer_nodes()
            new_pos = pos - offset
            c.insert(new_pos, c.pop(pos))
            r.nodes = [N_DEPOT] + c + [N_DEPOT]
            candidates.append({'name': f'resequence_earlier_by_{offset}', 'solution': sol, 'cost': None})

    # Candidate 2: swap with previous customer
    if pos > 0:
        sol = solution.copy()
        r = sol.routes[v]
        c = r.customer_nodes()
        c[pos], c[pos - 1] = c[pos - 1], c[pos]
        r.nodes = [N_DEPOT] + c + [N_DEPOT]
        candidates.append({'name': 'swap_with_prev', 'solution': sol, 'cost': None})

    # Candidate 3: tolerance relax — accept extended time window
    sol = solution.copy()
    candidates.append({'name': 'tolerance_relax', 'solution': sol, 'cost': None, 'relax_tolerance': True})

    return candidates


def generate_candidates_capacity(event, solution, traffic, demands, service_times,
                                 windows_open, windows_close, lambda_1, lambda_2, rng):
    candidates = []
    v = event['vehicle']
    route = solution.routes[v]
    custs = route.customer_nodes()

    # Load redistribution: move lightest customer to nearest feasible vehicle
    for v2 in range(len(solution.routes)):
        if v2 == v:
            continue
        target_route = solution.routes[v2]
        if target_route.total_demand(demands) > 100:
            continue

        sol = solution.copy()
        src_route = sol.routes[v]
        src_custs = src_route.customer_nodes()
        if not src_custs:
            continue

        # Find lightest customer to transfer
        best_cid = None
        best_demand = float('inf')
        best_pos_idx = -1
        for pos, cid in enumerate(src_custs):
            d = demands[cid]
            if d < best_demand:
                best_demand = d
                best_cid = cid
                best_pos_idx = pos

        if best_cid is None:
            continue

        del src_custs[best_pos_idx]
        src_route.nodes = [N_DEPOT] + src_custs + [N_DEPOT]

        tgt_custs = sol.routes[v2].customer_nodes()
        best_pos = 0
        best_cost = float('inf')
        best_nodes = None
        for p in range(len(tgt_custs) + 1):
            trial_nodes = [N_DEPOT] + tgt_custs[:p] + [best_cid] + tgt_custs[p:] + [N_DEPOT]
            trial = Route(trial_nodes)
            trial.departure_time = target_route.departure_time
            c, _ = trial.compute_cost(traffic, demands, service_times, windows_open, windows_close, lambda_1, lambda_2)
            if c < best_cost:
                best_cost = c
                best_nodes = trial_nodes
        if best_nodes:
            sol.routes[v2].nodes = best_nodes
            candidates.append({'name': f'redistribute_to_V{v2+1}', 'solution': sol, 'cost': None})

    return candidates
