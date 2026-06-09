"""
Rollout simulation for candidate dispatch actions (Sect 3.3.3, Eqs.35-41).

Each candidate action is evaluated via Monte Carlo rollout simulations
that inject traffic uncertainty (Eq.10 reliability margin) over a
fixed horizon. Returns rollout_cost, stability_penalty, recovery_penalty,
and a composite score with paper-aligned weights (Eq.40: 0.4/0.3/0.3).
"""

import numpy as np
from core.solution import N_DEPOT


def _single_rollout(solution, traffic, demands, service_times,
                    windows_open, windows_close, lambda_1, lambda_2,
                    horizon_minutes=60, blocked_arc=None, noise_scale=0.1):
    """Single trajectory rollout with traffic perturbation (Eq.10 via beta*eta)."""
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
                # inject noise: t' = t + beta * eta * epsilon  (Eq.10)
                eta = traffic.reliability_margin(prev, nid, T)
                tt = max(0.1, tt + np.random.normal(0, noise_scale * eta))
                travel_total += tt
                congestion_total += traffic.congestion_cost(prev, nid, T)
                T += tt
                break

            tt = traffic.travel_time(prev, nid, T)
            cc = traffic.congestion_cost(prev, nid, T)

            if blocked_arc and (prev, nid) == blocked_arc:
                tt *= 3.0

            eta = traffic.reliability_margin(prev, nid, T)
            tt = max(0.1, tt + np.random.normal(0, noise_scale * eta))

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


def rollout_cost(solution, traffic, demands, service_times,
                 windows_open, windows_close, lambda_1, lambda_2,
                 horizon_minutes=60, blocked_arc=None,
                 n_samples=1, noise_scale=0.0):
    """Rollout cost evaluation (Sect 3.3.3, Eq.36).

    With n_samples=1, noise_scale=0.0 (default): deterministic single trajectory.
    With n_samples>1, noise_scale>0: Monte Carlo with Eq.10 traffic perturbation.
    Returns (mean_cost, std_cost).
    """
    if n_samples <= 1 or noise_scale <= 0.0:
        c = _single_rollout(
            solution, traffic, demands, service_times,
            windows_open, windows_close, lambda_1, lambda_2,
            horizon_minutes=horizon_minutes, blocked_arc=blocked_arc,
            noise_scale=0.0,
        )
        return c, 0.0

    costs = []
    for _ in range(n_samples):
        c = _single_rollout(
            solution, traffic, demands, service_times,
            windows_open, windows_close, lambda_1, lambda_2,
            horizon_minutes=horizon_minutes, blocked_arc=blocked_arc,
            noise_scale=noise_scale,
        )
        costs.append(c)
    return float(np.mean(costs)), float(np.std(costs))


def stability_penalty(candidate_solution, original_solution):
    """Eq.41: Jaccard-based stability. Returns cost (lower = more stable).
    
    Scaled with factor 5.0 so penalty range [0, ~20] is small compared to
    typical route cost (~250), functioning as a tiebreaker."""
    penalty = 0.0
    for v, (c_route, o_route) in enumerate(zip(candidate_solution.routes, original_solution.routes)):
        c_set = set(c_route.customer_nodes())
        o_set = set(o_route.customer_nodes())
        union = len(c_set | o_set)
        intersection = len(c_set & o_set)
        if union > 0:
            jaccard = intersection / union
            penalty += (1.0 - jaccard) * 5.0
    return penalty


def recovery_penalty(candidate_solution, original_solution):
    """Eq.42: position deviation penalty. Returns cost (lower = better recovery).
    
    Scaled with factor 1.0 so penalty is a small tiebreaker relative to
    typical route cost (~250)."""
    penalty = 0.0
    for v, (c_route, o_route) in enumerate(zip(candidate_solution.routes, original_solution.routes)):
        c_custs = c_route.customer_nodes()
        o_custs = o_route.customer_nodes()
        for i, cid in enumerate(c_custs):
            if cid in o_custs:
                orig_pos = o_custs.index(cid)
                penalty += abs(i - orig_pos) * 1.0
    return penalty


def compute_diversion_bonus(candidate_solution, freq_memory):
    """Eq.39 diversification reward: higher for rarely-used assignments.
    
    Bonus is scaled to be a small tiebreaker (~5-10% of typical route cost)."""
    if freq_memory is None:
        return 0.0
    bonus = 0.0
    for v, route in enumerate(candidate_solution.routes):
        for pos, cid in enumerate(route.customer_nodes()):
            bonus += freq_memory.diversification_score(cid, v)
    return bonus * 0.3


def evaluate_candidate(candidate, original_solution, traffic, demands, service_times,
                       windows_open, windows_close, lambda_1, lambda_2,
                       horizon_minutes=60, blocked_arc=None, tabu_penalty=0.0,
                       freq_memory=None, omega_1=0.70, omega_2=0.15, omega_3=0.15,
                       n_samples=1, noise_scale=0.0,
                       extended_data=None):
    """Evaluate candidate with composite score (Eq.40).

    score = omega_1 * cost + omega_2 * stability + omega_3 * recovery
          - diversion_bonus + tabu_penalty

    Default weights (0.70/0.15/0.15) are tuned for synchronous simulation
    with post-dispatch optimization. The paper's weights (0.4/0.3/0.3) are
    designed for real-time dispatch without further optimization; override
    omega_1-3 to match the paper for that context.

    Uses exact compute_cost when n_samples=1/noise=0; falls back to
    short-horizon MC rollout when n_samples>1 for uncertainty simulation.
    Returns (score, cost, stability_penalty, recovery_penalty, mc_std).
    """
    eff_d, eff_st, eff_wo, eff_wc = demands, service_times, windows_open, windows_close
    if extended_data is not None:
        eff_d, eff_st, eff_wo, eff_wc = extended_data

    if candidate['name'] == 'subcontract':
        rc = candidate.get('subcontract_penalty', 50.0)
        mc_std = 0.0
    elif n_samples <= 1 and noise_scale <= 0.0:
        rc, _ = candidate['solution'].compute_cost(
            traffic, eff_d, eff_st, eff_wo, eff_wc, lambda_1, lambda_2)
        mc_std = 0.0
    else:
        rc, mc_std = rollout_cost(
            candidate['solution'], traffic, eff_d, eff_st,
            eff_wo, eff_wc, lambda_1, lambda_2,
            horizon_minutes=horizon_minutes, blocked_arc=blocked_arc,
            n_samples=n_samples, noise_scale=noise_scale,
        )

    sp = stability_penalty(candidate['solution'], original_solution)
    rp = recovery_penalty(candidate['solution'], original_solution)

    score = omega_1 * rc + omega_2 * sp + omega_3 * rp
    score += tabu_penalty
    diversion_bonus = compute_diversion_bonus(candidate['solution'], freq_memory)
    score -= diversion_bonus

    return score, rc, sp, rp, mc_std
