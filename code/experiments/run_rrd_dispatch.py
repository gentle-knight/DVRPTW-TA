#!/usr/bin/env python3
"""
RRD dispatch strategy comparison: same event sequence × 3 dispatch modes.

Modes:
  none     — event exists but no dispatch action taken
  greedy   — pick candidate with lowest immediate cost (no rollout)
  rollout  — full rollout evaluation + argmin adjusted_cost

All three modes run on the same seed, same event perturbation,
same snapshot at event_iter.

Output: outputs/processed/rrd_dispatch_comparison.csv
"""

import sys, json, csv, argparse, time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from traffic.traffic_manager import TrafficManager
from core.solution import load_customer_data
from dispatch.t_alns_rrd import run_t_alns_rrd

PROCESSED_DIR = PROJECT_ROOT / 'outputs' / 'processed'
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--instance', default='medium', choices=['easy', 'medium'])
    parser.add_argument('--seeds', type=int, default=10)
    parser.add_argument('--iters', type=int, default=600)
    args = parser.parse_args()

    csv_path = PROJECT_ROOT / 'datasets' / 'customers' / (
        'customers_47.csv' if args.instance == 'easy' else 'customers_47_medium.csv')

    tm = TrafficManager(theta=1.0, beta=0.5)
    demands, service_times, windows_open, windows_close = load_customer_data(csv_path=csv_path)

    print(f'RRD Dispatch Comparison')
    print(f'  Instance: {args.instance}  Seeds: {args.seeds}  Iters: {args.iters}')

    all_rows = []

    for seed in range(1, args.seeds + 1):
        for mode in ['none', 'greedy', 'rollout']:
            t0 = time.time()
            _, _, dlog = run_t_alns_rrd(
                tm, demands, service_times, windows_open, windows_close,
                max_iter=args.iters, seed=seed, verbose=False,
                dispatch_mode=mode)
            elapsed = time.time() - t0

            for entry in dlog:
                row = {
                    'seed': seed,
                    'dispatch_mode': mode,
                    'event_type': entry.get('event_type', '?'),
                    'event_iter': entry.get('iter', 0),
                    'success': entry.get('success', False),
                    'action': entry.get('action', '?'),
                    'event_cost_baseline': None,
                    'event_cost_strategy': entry.get('post_cost', None),
                    'cost_reduction': None,
                    'response_time_ms': entry.get('response_time_ms', 0),
                    'route_change_ratio': entry.get('route_change_ratio', 0),
                    'candidates_count': entry.get('candidates_count', 0),
                    'runtime_sec': elapsed,
                }
                all_rows.append(row)

            print(f'  seed={seed:2d} mode={mode:7s}: {len(dlog)} events logged')

    # Compute cost_reduction: for each (seed, event_iter), baseline=none cost
    none_costs = {}
    for row in all_rows:
        if row['dispatch_mode'] == 'none' and row['success']:
            key = (row['seed'], row['event_iter'])
            none_costs[key] = row['event_cost_strategy']

    for row in all_rows:
        key = (row['seed'], row['event_iter'])
        if key in none_costs:
            row['event_cost_baseline'] = none_costs[key]
            if row['event_cost_strategy'] is not None and row['event_cost_baseline'] is not None:
                row['cost_reduction'] = row['event_cost_baseline'] - row['event_cost_strategy']

    csv_out = PROCESSED_DIR / 'rrd_dispatch_comparison.csv'
    fieldnames = ['seed', 'dispatch_mode', 'event_type', 'event_iter', 'success', 'action',
                  'event_cost_baseline', 'event_cost_strategy', 'cost_reduction',
                  'response_time_ms', 'route_change_ratio', 'candidates_count', 'runtime_sec']
    with open(csv_out, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(all_rows)

    print(f'\nSaved: {csv_out}')

    # Summary
    import pandas as pd
    df = pd.read_csv(csv_out)
    for mode in ['none', 'greedy', 'rollout']:
        subset = df[df['dispatch_mode'] == mode]
        if len(subset) > 0:
            cr = subset['cost_reduction'].dropna()
            print(f'  {mode:7s}: mean cost_reduction={cr.mean():.2f} (n={len(cr)})')

    print('\nDone.')


if __name__ == '__main__':
    main()
