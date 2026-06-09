#!/usr/bin/env python3
"""
Ablation study runner: isolates contribution of each Tabu memory component.

Usage:
  python experiments/run_ablation.py                          # default: 10 seeds, 600 iters
  python experiments/run_ablation.py --seeds 5 --iters 300    # quick: 5 seeds, 300 iters
"""

import os, sys, json, csv, time, argparse
from pathlib import Path
from datetime import datetime
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from traffic.traffic_manager import TrafficManager
from core.solution import load_customer_data
from core.alns import run_alns
from utils.evaluation import compute_metrics, metrics_header

PROCESSED_DIR = PROJECT_ROOT / 'outputs' / 'processed'
RAW_DIR = PROJECT_ROOT / 'outputs' / 'raw_runs'
for d in [PROCESSED_DIR, RAW_DIR]:
    d.mkdir(parents=True, exist_ok=True)

MAX_ITER = 600
LAMBDA_1 = 1.0
LAMBDA_2 = 0.5


def run_ablation_variant(name, tm, demands, service_times, windows_open, windows_close,
                         enable_move=True, enable_solution=True, enable_frequency=True,
                         max_iter=600, seeds=None):
    from core.initialization import build_greedy_init
    from core.destroy import random_removal, worst_removal, relatedness_removal
    from core.repair import greedy_insertion, regret2_insertion, tw_aware_insertion
    from tabu.move_tabu import MoveTabuList
    from tabu.solution_tabu import SolutionTabuMemory
    from tabu.frequency import FrequencyMemory

    if seeds is None:
        seeds = range(1, 11)

    rows = []
    DESTROY_OPS = {'random': random_removal, 'worst': worst_removal, 'related': relatedness_removal}
    REPAIR_OPS = {'greedy': greedy_insertion, 'regret2': regret2_insertion, 'tw_aware': tw_aware_insertion}
    destroy_names = list(DESTROY_OPS.keys())
    repair_names = list(REPAIR_OPS.keys())

    REACTION_FACTOR = 0.1
    COOLING_RATE = 0.99975
    SEGMENT_SIZE = 100
    MAX_ATTEMPTS = 10

    for seed in seeds:
        rng_seed = np.random.RandomState(seed).randint(0, 99999)

        current = build_greedy_init(
            tm, demands, service_times, windows_open, windows_close,
            n_vehicles=4, capacity=120.0, lambda_1=LAMBDA_1, lambda_2=LAMBDA_2,
            seed=rng_seed)

        best = current.copy()
        best_cost, best_detail = best.compute_cost(
            tm, demands, service_times, windows_open, windows_close, LAMBDA_1, LAMBDA_2)
        current_cost = best_cost

        move_tabu = MoveTabuList(tenure=7) if enable_move else MoveTabuList(tenure=0)
        sol_tabu = SolutionTabuMemory(tenure=15 if enable_solution else 0)
        freq_memory = FrequencyMemory(n_customers=len(demands)-1, n_vehicles=4)

        d_weights = {n: 1.0 for n in destroy_names}
        r_weights = {n: 1.0 for n in repair_names}
        d_seg_rewards = {n: 0.0 for n in destroy_names}
        r_seg_rewards = {n: 0.0 for n in repair_names}

        T_sa = 0.05 * best_cost

        for it in range(1, max_iter + 1):
            iter_rng = np.random.RandomState(np.random.RandomState(seed + it).randint(0, 2**31 - 1))

            d_sum = sum(d_weights.values())
            r_sum = sum(r_weights.values())
            d_p = np.array([d_weights[n]/max(d_sum,1e-8) for n in destroy_names])
            r_p = np.array([r_weights[n]/max(r_sum,1e-8) for n in repair_names])

            found_valid = False
            working = None
            removed = None
            used_d = None
            used_r = None

            for attempt in range(MAX_ATTEMPTS):
                d_name = iter_rng.choice(destroy_names, p=d_p)
                r_name = iter_rng.choice(repair_names, p=r_p)

                candidate = current.copy()
                alpha = iter_rng.uniform(0.10, 0.40)

                if d_name == 'random':
                    cand_removed = random_removal(candidate, alpha=alpha, rng=iter_rng)
                elif d_name == 'worst':
                    cand_removed = worst_removal(
                        candidate, alpha=alpha, traffic=tm, demands=demands,
                        service_times=service_times, windows_open=windows_open,
                        windows_close=windows_close, lambda_1=LAMBDA_1, lambda_2=LAMBDA_2, rng=iter_rng)
                else:
                    cand_removed = relatedness_removal(
                        candidate, alpha=alpha, traffic=tm, demands=demands,
                        windows_open=windows_open, windows_close=windows_close, rng=iter_rng)

                REPAIR_OPS[r_name](
                    candidate, cand_removed, tm, demands, service_times,
                    windows_open, windows_close, LAMBDA_1, LAMBDA_2,
                    capacity=120.0, rng=iter_rng)

                if sol_tabu.is_tabu(candidate, it):
                    continue
                if move_tabu.is_tabu(cand_removed, it):
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
                        working, alpha=alpha, traffic=tm, demands=demands,
                        service_times=service_times, windows_open=windows_open,
                        windows_close=windows_close, lambda_1=LAMBDA_1, lambda_2=LAMBDA_2, rng=iter_rng)
                else:
                    removed = relatedness_removal(
                        working, alpha=alpha, traffic=tm, demands=demands,
                        windows_open=windows_open, windows_close=windows_close, rng=iter_rng)
                REPAIR_OPS[r_name](
                    working, removed, tm, demands, service_times,
                    windows_open, windows_close, LAMBDA_1, LAMBDA_2,
                    capacity=120.0, rng=iter_rng)
                used_d = d_name
                used_r = r_name

            new_cost, _ = working.compute_cost(
                tm, demands, service_times, windows_open, windows_close, LAMBDA_1, LAMBDA_2)
            delta = new_cost - current_cost

            reward = 0.5
            accepted = False
            if new_cost < best_cost:
                accepted = True
                best = working.copy()
                best_cost = new_cost
                current = working.copy()
                current_cost = new_cost
                reward = 10.0
            elif delta < 0:
                accepted = True
                current = working.copy()
                current_cost = new_cost
                reward = 5.0
            else:
                prob = np.exp(-delta / max(T_sa, 1e-8))
                if iter_rng.random() < prob:
                    accepted = True
                    current = working.copy()
                    current_cost = new_cost
                    reward = 2.0

            if accepted:
                move_tabu.add(removed, used_d, used_r, it)
                sol_tabu.add(working, it)
                if enable_frequency:
                    freq_memory.update(working)

            d_seg_rewards[used_d] += reward
            r_seg_rewards[used_r] += reward

            if it % SEGMENT_SIZE == 0:
                for n in destroy_names:
                    d_weights[n] = (1.0 - REACTION_FACTOR) * d_weights[n] + REACTION_FACTOR * d_seg_rewards[n]
                    d_seg_rewards[n] = 0.0
                for n in repair_names:
                    r_weights[n] = (1.0 - REACTION_FACTOR) * r_weights[n] + REACTION_FACTOR * r_seg_rewards[n]
                    r_seg_rewards[n] = 0.0

            T_sa *= COOLING_RATE

        m = compute_metrics(best, tm, demands, service_times, windows_open, windows_close, LAMBDA_1, LAMBDA_2)
        m['variant'] = name
        m['seed'] = seed
        rows.append(m)

    return rows


def main():
    parser = argparse.ArgumentParser(description='T-ALNS-RRD Ablation Study Runner')
    parser.add_argument('--seeds', type=int, default=10, help='Number of random seeds (default: 10)')
    parser.add_argument('--iters', type=int, default=600, help='Max ALNS iterations (default: 600)')
    parser.add_argument('--instance', type=str, default='easy', choices=['easy', 'medium'],
                        help='Instance difficulty (default: easy)')
    args = parser.parse_args()

    n_seeds = args.seeds
    max_iter = args.iters

    print('T-ALNS-RRD Ablation Study Runner')
    print(f'  Variants: no_tabu, move_only, soln_only, freq_only, full')
    print(f'  Seeds: {n_seeds}')
    print(f'  Max iterations: {max_iter}')

    tm = TrafficManager(theta=1.0, beta=0.5)
    demands, service_times, windows_open, windows_close = load_customer_data(
        csv_path=PROJECT_ROOT / 'datasets' / 'customers' / f'customers_47{"" if args.instance == "easy" else "_medium"}.csv')

    variants = {
        'no_tabu':    (False, False, False),
        'move_only':  (True,  False, False),
        'soln_only':  (False, True,  False),
        'freq_only':  (False, False, True),
        'full':       (True,  True,  True),
    }

    seeds = list(range(1, n_seeds + 1))
    all_rows = []

    for name, (move, soln, freq) in variants.items():
        print(f'\n{name}: move={move} solution={soln} frequency={freq}')
        rows = run_ablation_variant(
            name, tm, demands, service_times, windows_open, windows_close,
            enable_move=move, enable_solution=soln, enable_frequency=freq,
            max_iter=max_iter, seeds=seeds)

        for m in rows:
            print(f'  seed={m["seed"]:2d}: total={m["total"]:7.1f} OTDR={m["otdr"]:5.1f}% CES={m["ces"]:5.2f}')

        means = {}
        stds = {}
        for k in metrics_header():
            vals = [r[k] for r in rows]
            means[k] = float(np.mean(vals))
            stds[k] = float(np.std(vals))

        summary = {'variant': name, 'n_seeds': n_seeds}
        for k in metrics_header():
            summary[f'{k}_mean'] = means[k]
            summary[f'{k}_std'] = stds[k]
        all_rows.append(summary)

        print(f'  MEAN: total={means["total"]:.1f}±{stds["total"]:.1f} OTDR={means["otdr"]:.1f}%')

    csv_path = PROCESSED_DIR / 'ablation_table.csv'
    fieldnames = list(all_rows[0].keys())
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)
    print(f'\nSaved: {csv_path}')

    print(f'\n{"Variant":15s} {"Total":>12s} {"OTDR":>8s} {"CES":>8s}')
    print('-' * 50)
    for row in all_rows:
        print(f'{row["variant"]:15s} {row["total_mean"]:7.1f}±{row["total_std"]:.1f} {row["otdr_mean"]:6.1f}% {row["ces_mean"]:7.2f}')


if __name__ == '__main__':
    main()
