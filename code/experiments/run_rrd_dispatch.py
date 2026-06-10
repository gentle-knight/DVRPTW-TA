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
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from traffic.traffic_manager import TrafficManager
from core.solution import load_customer_data
from dispatch.t_alns_rrd import run_t_alns_rrd

PROCESSED_DIR = PROJECT_ROOT / 'outputs' / 'processed'
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def parse_event_iters(raw):
    if raw is None or raw.strip() == '':
        return None
    return tuple(int(x.strip()) for x in raw.split(',') if x.strip())


def parse_event_types(raw):
    if raw is None or raw.strip() == '':
        return None
    return tuple(x.strip() for x in raw.split(',') if x.strip())


def run_one(seed, mode, instance, iters, tmax, event_iterations, event_sequence):
    csv_path = PROJECT_ROOT / 'datasets' / 'customers' / (
        'customers_47.csv' if instance == 'easy' else 'customers_47_medium.csv')

    tm = TrafficManager(theta=1.0, beta=0.5)
    demands, service_times, windows_open, windows_close = load_customer_data(csv_path=csv_path)

    t0 = time.time()
    _, _, dlog, _ = run_t_alns_rrd(
        tm, demands, service_times, windows_open, windows_close,
        max_iter=iters, seed=seed, verbose=False,
        dispatch_mode=mode, t_max=tmax,
        event_iterations=event_iterations or (250, 500, 750, 875),
        event_sequence=event_sequence)
    elapsed = time.time() - t0
    return dlog, elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--instance', default='medium', choices=['easy', 'medium'])
    parser.add_argument('--seeds', type=int, default=10)
    parser.add_argument('--iters', type=int, default=600)
    parser.add_argument('--tmax', type=int, default=600)
    parser.add_argument('--event-iters', type=str, default=None,
                        help='Comma-separated event iterations. Default: 250,500,750,875. Use 40,80 for quick tests.')
    parser.add_argument('--event-types', type=str, default=None,
                        help='Comma-separated event types, e.g. E1_TRAFFIC,E2_URGENT.')
    parser.add_argument('--parallel', type=int, default=1,
                        help='Parallel worker processes (default: 1). For i5-12600KF, 4-6 is practical.')
    args = parser.parse_args()
    event_iterations = parse_event_iters(args.event_iters)
    event_sequence = parse_event_types(args.event_types)

    print(f'RRD Dispatch Comparison')
    print(f'  Instance: {args.instance}  Seeds: {args.seeds}  Iters: {args.iters}')
    print(f'  Parallel workers: {args.parallel}')
    if event_iterations:
        print(f'  Event iterations: {event_iterations}')
    if event_sequence:
        print(f'  Event types: {event_sequence}')

    all_rows = []
    jobs = [(seed, mode) for seed in range(1, args.seeds + 1)
            for mode in ['none', 'greedy', 'rollout']]
    results = {}

    if args.parallel > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=args.parallel) as executor:
            futures = {
                executor.submit(
                    run_one, seed, mode, args.instance, args.iters, args.tmax,
                    event_iterations, event_sequence): (seed, mode)
                for seed, mode in jobs
            }
            for future in as_completed(futures):
                seed, mode = futures[future]
                results[(seed, mode)] = future.result()
                print(f'  seed={seed:2d} mode={mode:7s}: done')
    else:
        for seed, mode in jobs:
            results[(seed, mode)] = run_one(
                seed, mode, args.instance, args.iters, args.tmax,
                event_iterations, event_sequence)
            print(f'  seed={seed:2d} mode={mode:7s}: done')

    for seed in range(1, args.seeds + 1):
        for mode in ['none', 'greedy', 'rollout']:
            dlog, elapsed = results[(seed, mode)]
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
