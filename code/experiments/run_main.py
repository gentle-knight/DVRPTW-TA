#!/usr/bin/env python3
"""
Main experiment runner: 5 algorithms × N seeds → comparison table.

Usage:
  python experiments/run_main.py                          # default: 30 seeds, 800 iters
  python experiments/run_main.py --seeds 10 --iters 400   # quick: 10 seeds, 400 iters
  python experiments/run_main.py --algo ALNS-Base,T-ALNS --seeds 20  # specific algorithms only
"""

import os, sys, time, json, csv, argparse
from pathlib import Path
from datetime import datetime

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from traffic.traffic_manager import TrafficManager
from core.solution import load_customer_data
from core.alns import run_alns
from tabu.t_alns import run_t_alns_full
from dispatch.t_alns_rrd import run_t_alns_rrd
from baselines import run_static_vrptw, run_ta_greedy
from utils.evaluation import compute_metrics, metrics_header

OUTPUT_DIR = PROJECT_ROOT / 'outputs'
RAW_DIR = OUTPUT_DIR / 'raw_runs'
PROCESSED_DIR = OUTPUT_DIR / 'processed'
for d in [RAW_DIR, PROCESSED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

LAMBDA_1 = 1.0
LAMBDA_2 = 0.5

ALL_ALGORITHMS = {
    'Static-VRPTW': 'static',
    'TA-VRPTW-Greedy': 'ta_greedy',
    'ALNS-Base': 'alns',
    'T-ALNS': 't_alns',
    'T-ALNS-RRD': 't_alns_rrd',
}

def run_one(alg_name, seed, max_iter, tm, demands, service_times, windows_open, windows_close, t_max=600):
    t0 = time.time()

    if alg_name == 'Static-VRPTW':
        sol, static_tm = run_static_vrptw(tm, demands, service_times, windows_open, windows_close, seed=seed)
        m = compute_metrics(sol, tm, demands, service_times, windows_open, windows_close, LAMBDA_1, LAMBDA_2)
        pm = compute_metrics(sol, static_tm, demands, service_times, windows_open, windows_close, LAMBDA_1, LAMBDA_2)
        m['planning_total'] = pm['total']
        m['planning_travel'] = pm['travel']
        m['planning_lateness'] = pm['lateness']
    elif alg_name == 'TA-VRPTW-Greedy':
        sol = run_ta_greedy(tm, demands, service_times, windows_open, windows_close, seed=seed)
        m = compute_metrics(sol, tm, demands, service_times, windows_open, windows_close, LAMBDA_1, LAMBDA_2)
    elif alg_name == 'ALNS-Base':
        _, m, _ = run_alns(tm, demands, service_times, windows_open, windows_close,
                           max_iter=max_iter, lambda_1=LAMBDA_1, lambda_2=LAMBDA_2,
                           seed=seed, verbose=False, t_max=t_max)
    elif alg_name == 'T-ALNS':
        _, m, _, _ = run_t_alns_full(tm, demands, service_times, windows_open, windows_close,
                                     max_iter=max_iter, lambda_1=LAMBDA_1, lambda_2=LAMBDA_2,
                                     seed=seed, verbose=False, t_max=t_max)
    elif alg_name == 'T-ALNS-RRD':
        _, m, _ = run_t_alns_rrd(tm, demands, service_times, windows_open, windows_close,
                                 max_iter=max_iter, lambda_1=LAMBDA_1, lambda_2=LAMBDA_2,
                                 seed=seed, verbose=False, t_max=t_max)
    else:
        raise ValueError(f'Unknown algorithm: {alg_name}')

    elapsed = time.time() - t0
    m['algorithm'] = alg_name
    m['seed'] = seed
    m['runtime_sec'] = elapsed
    return m


def main():
    parser = argparse.ArgumentParser(description='T-ALNS-RRD Main Experiment Runner')
    parser.add_argument('--seeds', type=int, default=30, help='Number of random seeds (default: 30)')
    parser.add_argument('--iters', type=int, default=1000, help='Max ALNS iterations (default: 1000)')
    parser.add_argument('--tmax', type=int, default=600, help='Max runtime per seed in seconds (default: 600)')
    parser.add_argument('--algo', type=str, default=None,
                        help='Comma-separated algorithm names. Default: all 5')
    parser.add_argument('--instance', type=str, default='easy', choices=['easy', 'medium'],
                        help='Instance difficulty (default: easy)')
    args = parser.parse_args()

    n_seeds = args.seeds
    max_iter = args.iters
    if args.algo:
        selected = {k: ALL_ALGORITHMS[k] for k in args.algo.split(',') if k in ALL_ALGORITHMS}
    else:
        selected = ALL_ALGORITHMS

    print(f'T-ALNS-RRD Main Experiment Runner')
    print(f'  Algorithms: {list(selected.keys())}')
    print(f'  Seeds: {n_seeds}')
    print(f'  Max iterations: {max_iter}')
    print()

    tm = TrafficManager(theta=1.0, beta=0.5)
    demands, service_times, windows_open, windows_close = load_customer_data(
        csv_path=PROJECT_ROOT / 'datasets' / 'customers' / f'customers_47{"" if args.instance == "easy" else "_medium"}.csv')

    run_id = datetime.now().strftime('run_%Y%m%d_%H%M%S')
    run_dir = RAW_DIR / run_id
    run_dir.mkdir(exist_ok=True)

    all_rows = []

    for alg_display, alg_key in selected.items():
        print(f'\n{"="*60}')
        print(f'Running {alg_display} ({alg_key})...')
        alg_rows = []

        for seed in range(1, n_seeds + 1):
            m = run_one(alg_display, seed, max_iter, tm, demands, service_times, windows_open, windows_close, t_max=args.tmax)
            alg_rows.append(m)

            print(f'  seed={seed:2d}: total={m["total"]:7.1f} travel={m["travel"]:7.1f} '
                  f'late={m["lateness"]:5.1f} cong={m["congestion"]:5.2f} '
                  f'OTDR={m["otdr"]:5.1f}% CES={m["ces"]:5.2f} time={m["runtime_sec"]:.1f}s')

            row_path = run_dir / f'{alg_key}_seed{seed:02d}.json'
            with open(row_path, 'w') as f:
                json.dump({k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                           for k, v in m.items()}, f, indent=2)

        means = {}
        stds = {}
        for k in metrics_header() + ['runtime_sec']:
            values = [r[k] for r in alg_rows]
            means[k] = np.mean(values)
            stds[k] = np.std(values)

        summary = {
            'algorithm': alg_display,
            'n_seeds': n_seeds,
        }
        for k in metrics_header() + ['runtime_sec']:
            summary[f'{k}_mean'] = means[k]
            summary[f'{k}_std'] = stds[k]
        all_rows.append(summary)

        print(f'  MEAN: total={means["total"]:.1f}±{stds["total"]:.1f} '
              f'OTDR={means["otdr"]:.1f}±{stds["otdr"]:.1f}% '
              f'CES={means["ces"]:.1f}±{stds["ces"]:.1f} '
              f'runtime={means["runtime_sec"]:.1f}s')

    csv_path = PROCESSED_DIR / 'main_comparison.csv'
    fieldnames = list(all_rows[0].keys())
    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f'\nSaved: {csv_path}')
    print(f'Raw runs: {run_dir}')

    metallic = {}
    for row in all_rows:
        metallic[row['algorithm']] = {k: row[k] for k in fieldnames}
    metallic_path = PROCESSED_DIR / 'main_comparison.json'
    with open(metallic_path, 'w') as f:
        json.dump(metallic, f, indent=2)
    print(f'Metadata: {metallic_path}')

    print('\n=== Main Comparison Summary ===')
    print(f'{"Algorithm":20s} {"Total":>10s} {"Travel":>10s} {"Lateness":>8s} {"Congestion":>10s} {"OTDR":>7s} {"CES":>8s}')
    print('-' * 80)
    for row in all_rows:
        print(f'{row["algorithm"]:20s} {row["total_mean"]:10.1f} {row["travel_mean"]:10.1f} '
              f'{row["lateness_mean"]:8.1f} {row["congestion_mean"]:10.2f} '
              f'{row["otdr_mean"]:6.1f}% {row["ces_mean"]:8.2f}')


if __name__ == '__main__':
    main()
