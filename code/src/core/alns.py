"""
Adaptive Large Neighborhood Search engine (Sect 3.3.1, Algorithm 1).

Full ALNS: 3 destroy + 3 repair operators, SA acceptance (Eqs.20–21),
adaptive operator weights (Eqs.18–19), traffic-aware cost evaluation.
"""

import time
import numpy as np
from .solution import Solution, Route, N_DEPOT
from .initialization import build_greedy_init
from .destroy import random_removal, worst_removal, relatedness_removal
from .repair import greedy_insertion, regret2_insertion, tw_aware_insertion


def compute_metrics(solution, traffic, demands, service_times,
                     windows_open, windows_close, lambda_1, lambda_2):
    n_customers = len(demands) - 1
    cost, details = solution.compute_cost(
        traffic, demands, service_times, windows_open, windows_close,
        lambda_1=lambda_1, lambda_2=lambda_2)

    ontime = 0
    for rd, route in zip(details['route_details'], solution.routes):
        customers = route.customer_nodes()
        for i in range(len(customers)):
            if rd['latenesses'][i] == 0:
                ontime += 1

    return {
        'travel': details['travel_cost'],
        'lateness': details['lateness_penalty'],
        'congestion': details['congestion_cost'],
        'total': cost,
        'otdr': ontime / n_customers * 100,
        'ces': details['congestion_cost'],
    }


DESTROY_OPS = {'random': random_removal, 'worst': worst_removal, 'related': relatedness_removal}
REPAIR_OPS = {'greedy': greedy_insertion, 'regret2': regret2_insertion, 'tw_aware': tw_aware_insertion}

REWARD_SIGMA1 = 10.0
REWARD_SIGMA2 = 5.0
REWARD_SIGMA3 = 2.0
REWARD_SIGMA4 = 0.5


def run_alns(traffic, demands, service_times, windows_open, windows_close,
             max_iter=1000, lambda_1=1.0, lambda_2=0.5,
             cooling_rate=0.99975, reaction_factor=0.1,
             segment_size=100, seed=42, verbose=True):

    rng = np.random.RandomState(seed)

    t0 = time.time()
    current = build_greedy_init(
        traffic, demands, service_times, windows_open, windows_close,
        n_vehicles=4, capacity=120.0, lambda_1=lambda_1, lambda_2=lambda_2,
        seed=rng.randint(0, 99999))

    best = current.copy()
    best_cost, _ = best.compute_cost(
        traffic, demands, service_times, windows_open, windows_close,
        lambda_1=lambda_1, lambda_2=lambda_2)
    current_cost = best_cost
    m0 = compute_metrics(best, traffic, demands, service_times, windows_open, windows_close, lambda_1, lambda_2)

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
    accepted_worse = 0

    if verbose:
        print(f'ALNS | iter={0:5d} | T={T:.1f} | travel={m0["travel"]:7.1f} '
              f'late={m0["lateness"]:6.1f} cong={m0["congestion"]:5.2f} '
              f'total={m0["total"]:7.1f} OTDR={m0["otdr"]:5.1f}% CES={m0["ces"]:5.2f} | init')

    for it in range(1, max_iter + 1):
        iter_rng = np.random.RandomState(rng.randint(0, 2**31 - 1))

        d_probs = np.array([d_weights[n] for n in destroy_names])
        d_probs /= d_probs.sum()
        d_name = iter_rng.choice(destroy_names, p=d_probs)

        r_probs = np.array([r_weights[n] for n in repair_names])
        r_probs /= r_probs.sum()
        r_name = iter_rng.choice(repair_names, p=r_probs)

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
            rng=iter_rng)

        new_cost, _ = working.compute_cost(
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
            current = working.copy()
            current_cost = new_cost
            improvements += 1
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
                accepted_worse += 1

        d_seg_rewards[d_name] += reward
        r_seg_rewards[r_name] += reward

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
            tag = '*BEST' if is_new_best else 'acc'
            print(f'ALNS | iter={it:5d} | T={T:.1f} | travel={m["travel"]:7.1f} '
                  f'late={m["lateness"]:6.1f} cong={m["congestion"]:5.2f} '
                  f'total={m["total"]:7.1f} OTDR={m["otdr"]:5.1f}% CES={m["ces"]:5.2f} '
                  f'| {d_name}/{r_name} {tag}')

    elapsed = time.time() - t0
    final = compute_metrics(best, traffic, demands, service_times, windows_open, windows_close, lambda_1, lambda_2)

    if verbose:
        print(f'\nALNS done | {max_iter} iters {elapsed:.1f}s | {improvements} improvements | {accepted_worse} acc-worse')
        print(f'  travel={final["travel"]:.1f} late={final["lateness"]:.1f} cong={final["congestion"]:.2f} '
              f'total={final["total"]:.1f} OTDR={final["otdr"]:.1f}% CES={final["ces"]:.2f}')
        dw = ', '.join(f'{n}={w:.2f}' for n, w in sorted(d_weights.items()))
        rw = ', '.join(f'{n}={w:.2f}' for n, w in sorted(r_weights.items()))
        print(f'  weights d: {{{dw}}}')
        print(f'  weights r: {{{rw}}}')

    return best, final, history
