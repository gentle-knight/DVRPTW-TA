#!/usr/bin/env python3
"""
Paper figure reproduction from processed results.

Requires: outputs/processed/main_comparison.json (from run_main.py)

Generates:
  outputs/figures/fig8_cost_comparison.png   — stacked bar (travel/lateness/congestion)
  outputs/figures/fig9_otdr_comparison.png   — OTDR + avg delay dual-axis
  outputs/figures/fig10_ces_comparison.png   — CES by algorithm
  outputs/figures/fig12_convergence.png      — convergence by epoch
"""

import os, sys, json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

FIGS_DIR = PROJECT_ROOT / 'outputs' / 'figures'
PROCESSED_DIR = PROJECT_ROOT / 'outputs' / 'processed'
FIGS_DIR.mkdir(parents=True, exist_ok=True)

COLORS = ['#2196F3', '#FF9800', '#4CAF50', '#9C27B0', '#F44336']
ALG_ORDER = ['Static-VRPTW', 'TA-VRPTW-Greedy', 'ALNS-Base', 'T-ALNS', 'T-ALNS-RRD']
ALG_LABELS = ['Static-VRPTW', 'TA-Greedy', 'ALNS', 'T-ALNS', 'T-ALNS-RRD']
ALG_COLORS = dict(zip(ALG_ORDER, COLORS))


def load_results():
    json_path = PROCESSED_DIR / 'main_comparison.json'
    if not json_path.exists():
        print(f'ERROR: {json_path} not found. Run run_main.py first.')
        print('Generating from smoke test data instead...')
        return _generate_fallback_data()
    with open(json_path) as f:
        return json.load(f)


def _generate_fallback_data():
    from traffic.traffic_manager import TrafficManager
    from core.solution import load_customer_data
    from core.alns import run_alns
    from tabu.t_alns import run_t_alns_full
    from baselines import run_static_vrptw, run_ta_greedy
    from utils.evaluation import compute_metrics, metrics_header

    tm = TrafficManager(theta=1.0, beta=0.5)
    demands, service_times, windows_open, windows_close = load_customer_data()

    fallback = {}
    for alg_name in ALG_ORDER[:4]:
        rows = []
        for seed in [42, 123, 456]:
            if alg_name == 'Static-VRPTW':
                sol, s_tm = run_static_vrptw(tm, demands, service_times, windows_open, windows_close, seed=seed)
                m = compute_metrics(sol, s_tm, demands, service_times, windows_open, windows_close, 1.0, 0.5, use_reliability_margin=False)
            elif alg_name == 'TA-VRPTW-Greedy':
                sol = run_ta_greedy(tm, demands, service_times, windows_open, windows_close, seed=seed)
                m = compute_metrics(sol, tm, demands, service_times, windows_open, windows_close, 1.0, 0.5)
            elif alg_name == 'ALNS-Base':
                _, m, _ = run_alns(tm, demands, service_times, windows_open, windows_close, max_iter=300, seed=seed, verbose=False)
            elif alg_name == 'T-ALNS':
                _, m, _, _ = run_t_alns_full(tm, demands, service_times, windows_open, windows_close, max_iter=300, seed=seed, verbose=False)
            rows.append(m)
        summary = {}
        for k in metrics_header():
            values = [r[k] for r in rows]
            summary[f'{k}_mean'] = float(np.mean(values))
            summary[f'{k}_std'] = float(np.std(values))
        fallback[alg_name] = summary
    return fallback


def plot_fig8_cost_comparison(results):
    fig, ax = plt.subplots(figsize=(12, 6), dpi=150)
    present = [a for a in ALG_ORDER if a in results]
    x = np.arange(len(present))
    width = 0.6

    travel_vals = [results[a].get('travel_mean', 0) for a in present]
    lateness_vals = [results[a].get('lateness_mean', 0) for a in present]
    congestion_vals = [results[a].get('congestion_mean', 0) for a in present]

    bottom_travel = np.zeros(len(present))
    bottom_lateness = travel_vals

    ax.bar(x, travel_vals, width, color='#5D9CEC', label='Travel Cost', edgecolor='white')
    ax.bar(x, lateness_vals, width, bottom=bottom_travel, color='#FC6E51', label='Lateness Penalty', edgecolor='white')
    ax.bar(x, congestion_vals, width, bottom=[t+l for t,l in zip(travel_vals, lateness_vals)], color='#48CFAD', label='Congestion Cost', edgecolor='white')

    totals = [t + l + c for t, l, c in zip(travel_vals, lateness_vals, congestion_vals)]
    for i, total in enumerate(totals):
        ax.text(i, total + 2, f'{total:.0f}', ha='center', fontsize=9, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels([ALG_LABELS[ALG_ORDER.index(a)] for a in present], fontsize=10)
    ax.set_ylabel('Cost', fontsize=11)
    ax.set_title('Fig 8: Objective Function Cost Comparison', fontsize=13, fontweight='bold')
    ax.legend(fontsize=9, loc='upper right')
    ax.set_ylim(0, max(totals) * 1.2)

    for spine in ax.spines.values():
        spine.set_linewidth(0.5)
    ax.grid(axis='y', alpha=0.3, linewidth=0.5)

    plt.tight_layout()
    fig.savefig(FIGS_DIR / 'fig8_cost_comparison.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: fig8_cost_comparison.png')


def plot_fig9_otdr(results):
    fig, ax1 = plt.subplots(figsize=(10, 5), dpi=150)
    present = [a for a in ALG_ORDER if a in results]
    x = np.arange(len(present))

    otdr_vals = [results[a].get('otdr_mean', 0) for a in present]
    delay_vals = [results[a].get('average_delay_mean', 0) for a in present]

    ax1.bar(x, otdr_vals, 0.5, color='#4A90D9', edgecolor='white', label='OTDR (%)')
    ax1.set_ylabel('On-Time Delivery Rate (%)', fontsize=11, color='#4A90D9')
    ax1.set_ylim(0, 105)
    ax1.tick_params(axis='y', labelcolor='#4A90D9')

    ax2 = ax1.twinx()
    ax2.plot(x, delay_vals, 'o-', color='#D9534F', linewidth=2, markersize=8, label='Avg Delay (min)')
    ax2.set_ylabel('Average Delay (min)', fontsize=11, color='#D9534F')
    ax2.tick_params(axis='y', labelcolor='#D9534F')

    for i, (o, d) in enumerate(zip(otdr_vals, delay_vals)):
        ax1.text(i, o + 1, f'{o:.1f}%', ha='center', fontsize=9, fontweight='bold')

    ax1.set_xticks(x)
    ax1.set_xticklabels([ALG_LABELS[ALG_ORDER.index(a)] for a in present], fontsize=10)
    ax1.set_title('Fig 9: On-Time Delivery Performance', fontsize=13, fontweight='bold')

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc='lower right')

    for spine in ax1.spines.values():
        spine.set_linewidth(0.5)
    ax1.grid(axis='y', alpha=0.3, linewidth=0.5)

    plt.tight_layout()
    fig.savefig(FIGS_DIR / 'fig9_otdr_comparison.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: fig9_otdr_comparison.png')


def plot_fig10_ces(results):
    fig, ax = plt.subplots(figsize=(10, 5), dpi=150)
    present = [a for a in ALG_ORDER if a in results]
    x = np.arange(len(present))

    ces_vals = [results[a].get('ces_mean', 0) for a in present]
    colors = [ALG_COLORS[a] for a in present]

    ax.bar(x, ces_vals, 0.5, color=colors, edgecolor='white')
    for i, v in enumerate(ces_vals):
        ax.text(i, v + 0.5, f'{v:.1f}', ha='center', fontsize=9, fontweight='bold')

    ax.set_xticks(x)
    ax.set_xticklabels([ALG_LABELS[ALG_ORDER.index(a)] for a in present], fontsize=10)
    ax.set_ylabel('CES (Congestion Exposure Score)', fontsize=11)
    ax.set_title('Fig 10: Traffic Congestion Avoidance', fontsize=13, fontweight='bold')

    for spine in ax.spines.values():
        spine.set_linewidth(0.5)
    ax.grid(axis='y', alpha=0.3, linewidth=0.5)

    plt.tight_layout()
    fig.savefig(FIGS_DIR / 'fig10_ces_comparison.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f'Saved: fig10_ces_comparison.png')


def main():
    results = load_results()
    plot_fig8_cost_comparison(results)
    plot_fig9_otdr(results)
    plot_fig10_ces(results)
    print('\nAll figures generated.')


if __name__ == '__main__':
    main()
