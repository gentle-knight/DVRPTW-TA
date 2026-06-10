"""
Tabu-enhanced ALNS engine (Sect 3.3.2, Algorithm 2).

Full version: Move Tabu + Solution Tabu + Frequency Memory +
Aspiration Criteria + Diversification Intensity.

Tracks per-iteration statistics for convergence and diversity analysis.
"""

import time
import numpy as np
from .move_tabu import MoveTabuList
from .solution_tabu import SolutionTabuMemory
from .frequency import FrequencyMemory
from .aspiration import check_aspiration
from .diversification import (
    compute_intensity, adjust_probabilities, compute_diversity_scores
)

from core.solution import Route, N_DEPOT
from core.initialization import build_greedy_init
from core.destroy import random_removal, worst_removal, relatedness_removal
from core.repair import greedy_insertion, regret2_insertion, tw_aware_insertion
from core.local_search import polish_solution
from utils.evaluation import compute_metrics

DESTROY_OPS = {'random': random_removal, 'worst': worst_removal, 'related': relatedness_removal}
REPAIR_OPS = {'greedy': greedy_insertion, 'regret2': regret2_insertion, 'tw_aware': tw_aware_insertion}

REWARD_SIGMA1 = 10.0
REWARD_SIGMA2 = 5.0
REWARD_SIGMA3 = 2.0
REWARD_SIGMA4 = 0.5


def run_t_alns_full(traffic, demands, service_times, windows_open, windows_close,
                    max_iter=1000, lambda_1=1.0, lambda_2=0.5,
                    cooling_rate=0.99975, reaction_factor=0.1, segment_size=100,
                    max_attempts=10, delta_max=0.8, eta=0.6,
                    aspiration_beta=0.3, aspiration_gamma=0.7,
                    seed=42, verbose=True, t_max=600):

    rng = np.random.RandomState(seed)
    n_vehicles = 4
    n_customers = len(demands) - 1

    t0 = time.time()
    current = build_greedy_init(
        traffic, demands, service_times, windows_open, windows_close,
        n_vehicles=n_vehicles, capacity=120.0, lambda_1=lambda_1, lambda_2=lambda_2,
        seed=rng.randint(0, 99999))

    best = current.copy()
    best_cost, best_detail = best.compute_cost(
        traffic, demands, service_times, windows_open, windows_close,
        lambda_1=lambda_1, lambda_2=lambda_2)
    current_cost = best_cost
    m0 = compute_metrics(best, traffic, demands, service_times, windows_open, windows_close, lambda_1, lambda_2)

    move_tabu = MoveTabuList(tenure=7)
    sol_tabu = SolutionTabuMemory(tenure=15, n_customers=n_customers)
    freq_memory = FrequencyMemory(n_customers=n_customers, n_vehicles=n_vehicles)
    freq_memory.update(current)

    destroy_names = list(DESTROY_OPS.keys())
    repair_names = list(REPAIR_OPS.keys())
    d_weights = {n: 1.0 for n in destroy_names}
    r_weights = {n: 1.0 for n in repair_names}
    d_seg_rewards = {n: 0.0 for n in destroy_names}
    r_seg_rewards = {n: 0.0 for n in repair_names}

    T_init = 0.05 * best_cost
    T = T_init

    history = []
    improvements = 0
    last_best_iter = 0
    tabu_reject_count = 0
    sol_revisit_count = 0
    total_candidates = 0
    accepted_worse_count = 0
    aspiration_count = 0

    if verbose:
        print(f'T-ALNS-FULL | iter={0:5d} | T={T:.1f} | travel={m0["travel"]:7.1f} '
              f'late={m0["lateness"]:6.1f} cong={m0["congestion"]:5.2f} '
              f'total={m0["total"]:7.1f} OTDR={m0["otdr"]:5.1f}% | init')

    for it in range(1, max_iter + 1):
        if time.time() - t0 > t_max:
            break
        iter_rng = np.random.RandomState(rng.randint(0, 2**31 - 1))

        delta_intensity = compute_intensity(
            it, last_best_iter, max_iter,
            move_tabu.size, max(1, move_tabu.tenure_max * 5),
            freq_memory.customer_vehicle_std(),
        )

        if delta_intensity > delta_max:
            div_scores_d = compute_diversity_scores(freq_memory, n_vehicles, destroy_names)
            div_scores_r = compute_diversity_scores(freq_memory, n_vehicles, repair_names)
            d_probs_arr = adjust_probabilities(d_weights, div_scores_d, eta)
            r_probs_arr = adjust_probabilities(r_weights, div_scores_r, eta)
        else:
            d_sum = sum(d_weights.values())
            r_sum = sum(r_weights.values())
            d_probs_arr = {n: d_weights[n] / d_sum for n in destroy_names}
            r_probs_arr = {n: r_weights[n] / r_sum for n in repair_names}

        d_p = np.array([d_probs_arr[n] for n in destroy_names])
        r_p = np.array([r_probs_arr[n] for n in repair_names])
        d_p /= d_p.sum()
        r_p /= r_p.sum()

        found_valid = False
        working = None
        removed = None
        used_d = None
        used_r = None

        for attempt in range(max_attempts):
            d_name = iter_rng.choice(destroy_names, p=d_p)
            r_name = iter_rng.choice(repair_names, p=r_p)

            candidate = current.copy()
            alpha = iter_rng.uniform(0.10, 0.40)

            if d_name == 'random':
                cand_removed = random_removal(candidate, alpha=alpha, rng=iter_rng)
            elif d_name == 'worst':
                cand_removed = worst_removal(
                    candidate, alpha=alpha, traffic=traffic, demands=demands,
                    service_times=service_times, windows_open=windows_open,
                    windows_close=windows_close, lambda_1=lambda_1, lambda_2=lambda_2,
                    rng=iter_rng)
            else:
                cand_removed = relatedness_removal(
                    candidate, alpha=alpha, traffic=traffic, demands=demands,
                    windows_open=windows_open, windows_close=windows_close,
                    rng=iter_rng)

            REPAIR_OPS[r_name](
                candidate, cand_removed, traffic, demands, service_times,
                windows_open, windows_close, lambda_1=lambda_1, lambda_2=lambda_2,
                capacity=120.0, rng=iter_rng)

            total_candidates += 1
            cand_cost, cand_detail = candidate.compute_cost(
                traffic, demands, service_times, windows_open, windows_close,
                lambda_1=lambda_1, lambda_2=lambda_2)

            is_tabu_move = move_tabu.is_tabu(cand_removed, it, d_name, r_name)
            is_tabu_sol = sol_tabu.is_tabu(candidate, it)

            if is_tabu_sol:
                sol_revisit_count += 1
            if is_tabu_move:
                tabu_reject_count += 1

            if is_tabu_move or is_tabu_sol:
                min_freq = float('inf')
                for cid in cand_removed:
                    fv = freq_memory.least_frequent_assignment(cid)
                    if fv < min_freq:
                        min_freq = fv
                sample_v = 0
                for v_idx, r in enumerate(candidate.routes):
                    if cand_removed[0] in r.customer_nodes():
                        sample_v = v_idx
                        break

                aspired, asp_reason = check_aspiration(
                    cand_cost, best_cost,
                    frequency=freq_memory,
                    min_freq_value=min_freq,
                    beta=aspiration_beta, gamma=aspiration_gamma,
                    new_congestion=cand_detail['congestion_cost'],
                    current_congestion=best_detail['congestion_cost'],
                )

                if aspired:
                    aspiration_count += 1
                else:
                    continue

            found_valid = True
            working = candidate
            removed = cand_removed
            used_d = d_name
            used_r = r_name
            break

        if not found_valid:
            d_name = iter_rng.choice(destroy_names, p=d_p)
            r_name = iter_rng.choice(repair_names, p=r_p)
            working = current.copy()
            alpha = iter_rng.uniform(0.10, 0.40)

            if d_name == 'random':
                removed = random_removal(working, alpha=alpha, rng=iter_rng)
            elif d_name == 'worst':
                removed = worst_removal(
                    working, alpha=alpha, traffic=traffic, demands=demands,
                    service_times=service_times, windows_open=windows_open,
                    windows_close=windows_close, lambda_1=lambda_1, lambda_2=lambda_2,
                    rng=iter_rng)
            else:
                removed = relatedness_removal(
                    working, alpha=alpha, traffic=traffic, demands=demands,
                    windows_open=windows_open, windows_close=windows_close,
                    rng=iter_rng)

            REPAIR_OPS[r_name](
                working, removed, traffic, demands, service_times,
                windows_open, windows_close, lambda_1=lambda_1, lambda_2=lambda_2,
                capacity=120.0, rng=iter_rng)

            total_candidates += 1
            used_d = d_name
            used_r = r_name

        new_cost, new_detail = working.compute_cost(
            traffic, demands, service_times, windows_open, windows_close,
            lambda_1=lambda_1, lambda_2=lambda_2)
        delta = new_cost - current_cost

        reward = REWARD_SIGMA4
        accepted = False
        is_new_best = new_cost < best_cost
        if is_new_best:
            accepted = True
            best = working.copy()
            best_cost = new_cost
            best_detail = new_detail
            current = working.copy()
            current_cost = new_cost
            improvements += 1
            last_best_iter = it
            move_tabu.report_improvement()
            reward = REWARD_SIGMA1
        elif delta < 0:
            accepted = True
            current = working.copy()
            current_cost = new_cost
            reward = REWARD_SIGMA2
        else:
            prob = np.exp(-delta / max(T, 1e-8))
            if iter_rng.random() < prob:
                accepted = True
                current = working.copy()
                current_cost = new_cost
                reward = REWARD_SIGMA3
                move_tabu.report_stagnation()
                accepted_worse_count += 1
            else:
                move_tabu.report_stagnation()

        if accepted:
            move_tabu.add(removed, used_d, used_r, it)
            sol_tabu.add(working, it)
            cong_weights = []
            for r in working.routes:
                _, rd = r.compute_cost(traffic, demands, service_times, windows_open, windows_close, lambda_1, lambda_2)
                cong_weights.append(rd['congestion_cost'])
            freq_memory.update(working, congestion_weights=cong_weights)

        d_seg_rewards[used_d] += reward
        r_seg_rewards[used_r] += reward

        if it % segment_size == 0:
            for n in destroy_names:
                d_weights[n] = (1.0 - reaction_factor) * d_weights[n] + reaction_factor * d_seg_rewards[n]
                d_seg_rewards[n] = 0.0
            for n in repair_names:
                r_weights[n] = (1.0 - reaction_factor) * r_weights[n] + reaction_factor * r_seg_rewards[n]
                r_seg_rewards[n] = 0.0

        T *= cooling_rate
        history.append(best_cost)

        if verbose and (it % 200 == 0 or (accepted and is_new_best)):
            m = compute_metrics(best, traffic, demands, service_times, windows_open, windows_close, lambda_1, lambda_2)
            tag = '*BEST' if is_new_best else ('acc' if accepted else 'rej')
            div_tag = 'DIV' if delta_intensity > delta_max else '   '
            print(f'T-ALNS-FULL | iter={it:5d} | T={T:.1f} | travel={m["travel"]:7.1f} '
                  f'late={m["lateness"]:6.1f} cong={m["congestion"]:5.2f} '
                  f'total={m["total"]:7.1f} OTDR={m["otdr"]:5.1f}% '
                  f'| rej={tabu_reject_count} rev={sol_revisit_count} asp={aspiration_count} {div_tag} | {tag}')

    best, best_cost, best_detail, polish_improvements = polish_solution(
        best, traffic, demands, service_times, windows_open, windows_close,
        lambda_1=lambda_1, lambda_2=lambda_2, capacity=120.0, max_passes=20)
    if history:
        history[-1] = best_cost

    elapsed = time.time() - t0
    final = compute_metrics(best, traffic, demands, service_times, windows_open, windows_close, lambda_1, lambda_2)

    stats = {
        'iterations': max_iter,
        'improvements': improvements,
        'tabu_reject_count': tabu_reject_count,
        'sol_revisit_count': sol_revisit_count,
        'aspiration_count': aspiration_count,
        'total_candidates': total_candidates,
        'accepted_worse_count': accepted_worse_count,
        'move_tabu_tenure_final': move_tabu.tenure,
        'polish_improvements': polish_improvements,
        'elapsed_sec': elapsed,
    }

    if verbose:
        print(f'\nT-ALNS-FULL done | {max_iter} iters {elapsed:.1f}s')
        print(f'  travel={final["travel"]:.1f} late={final["lateness"]:.1f} cong={final["congestion"]:.2f} total={final["total"]:.1f} OTDR={final["otdr"]:.1f}% CES={final["ces"]:.2f}')
        print(f'  improv={improvements} | tabu-rej={tabu_reject_count} sol-revisit={sol_revisit_count} aspir={aspiration_count} | acc-worse={accepted_worse_count}')

    return best, final, history, stats
