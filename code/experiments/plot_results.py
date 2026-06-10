#!/usr/bin/env python3
"""
Paper figure reproduction from processed results.

Requires: outputs/processed/main_comparison.json (from run_main.py)

Generates:
  outputs/figures/fig8_cost_comparison.png   — stacked bar (travel/lateness/congestion)
  outputs/figures/fig9_otdr_comparison.png   — OTDR + avg delay dual-axis
  outputs/figures/fig10_ces_comparison.png   — CES by algorithm
  outputs/figures/fig11_dispatch.png         — dispatch strategy event gains
  outputs/figures/fig12_convergence.png      — convergence by epoch
  outputs/figures/fig13_ablation_tabu.png    — tabu memory ablation
  outputs/figures/fig13b_ablation_rrd.png    — RRD event ablation
  outputs/figures/fig14_memory.png           — memory mechanism diagnostics
  outputs/figures/fig15_robustness.png       — traffic uncertainty robustness
"""

import os, sys, json, csv
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

FIGS_DIR = PROJECT_ROOT / 'outputs' / 'figures'
PROCESSED_DIR = PROJECT_ROOT / 'outputs' / 'processed'
RAW_DIR = PROJECT_ROOT / 'outputs' / 'raw_runs'
FIGS_DIR.mkdir(parents=True, exist_ok=True)

COLORS = ['#2196F3', '#FF9800', '#4CAF50', '#9C27B0', '#F44336']
ALG_ORDER = ['Static-VRPTW', 'TA-VRPTW-Greedy', 'ALNS-Base', 'T-ALNS', 'T-ALNS-RRD']
ALG_LABELS = ['Static-VRPTW', 'TA-Greedy', 'ALNS', 'T-ALNS', 'T-ALNS-RRD']
ALG_COLORS = dict(zip(ALG_ORDER, COLORS))


def _read_csv(path):
    if not path.exists():
        return []
    with open(path, newline='') as f:
        return list(csv.DictReader(f))


def _as_float(row, key, default=0.0):
    try:
        value = row.get(key, default)
        if value in ('', None):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _latest_raw_run_dir():
    if not RAW_DIR.exists():
        return None
    run_dirs = [p for p in RAW_DIR.iterdir() if p.is_dir()]
    if not run_dirs:
        return None
    return max(run_dirs, key=lambda p: p.stat().st_mtime)


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


def plot_fig11_dispatch():
    rows = _read_csv(PROCESSED_DIR / 'rrd_dispatch_comparison.csv')
    if not rows:
        print('Skip: rrd_dispatch_comparison.csv not found')
        return

    modes = ['none', 'greedy', 'rollout']
    means = []
    latencies = []
    for mode in modes:
        subset = [r for r in rows if r.get('dispatch_mode') == mode]
        reductions = [_as_float(r, 'cost_reduction') for r in subset if r.get('cost_reduction') not in ('', None)]
        response = [_as_float(r, 'response_time_ms') for r in subset]
        means.append(float(np.mean(reductions)) if reductions else 0.0)
        latencies.append(float(np.mean(response)) if response else 0.0)

    fig, ax1 = plt.subplots(figsize=(9, 5), dpi=150)
    x = np.arange(len(modes))
    colors = ['#9E9E9E', '#FF9800', '#F44336']
    ax1.bar(x, means, 0.55, color=colors, edgecolor='white', label='Cost reduction')
    ax1.set_ylabel('Mean Event Cost Reduction', fontsize=11)
    ax1.set_xticks(x)
    ax1.set_xticklabels(['No Dispatch', 'Greedy', 'Rollout'])
    ax1.set_title('Fig 11: Real-Time Dispatch Effectiveness', fontsize=13, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3, linewidth=0.5)

    for i, value in enumerate(means):
        ax1.text(i, value + max(1.0, max(means) * 0.02), f'{value:.1f}',
                 ha='center', fontsize=9, fontweight='bold')

    ax2 = ax1.twinx()
    ax2.plot(x, latencies, 'o-', color='#263238', linewidth=2, label='Response time')
    ax2.set_ylabel('Mean Response Time (ms)', fontsize=11)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc='upper left')

    plt.tight_layout()
    fig.savefig(FIGS_DIR / 'fig11_dispatch.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print('Saved: fig11_dispatch.png')


def plot_fig12_convergence():
    run_dir = _latest_raw_run_dir()
    if run_dir is None:
        print('Skip: no raw run directories found')
        return

    histories = {alg: [] for alg in ALG_ORDER}
    key_to_alg = {
        'static': 'Static-VRPTW',
        'ta_greedy': 'TA-VRPTW-Greedy',
        'alns': 'ALNS-Base',
        't_alns': 'T-ALNS',
        't_alns_rrd': 'T-ALNS-RRD',
    }

    for path in run_dir.glob('*_history.json'):
        with open(path) as f:
            payload = json.load(f)
        alg = payload.get('algorithm')
        if alg not in histories:
            for key, alg_name in key_to_alg.items():
                if path.name.startswith(key + '_'):
                    alg = alg_name
                    break
        values = payload.get('history', [])
        if alg in histories and values:
            histories[alg].append([float(v) for v in values])

    present = [alg for alg in ALG_ORDER if histories[alg]]
    if not present:
        print(f'Skip: no histories found in {run_dir}')
        return

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=150)
    for alg in present:
        max_len = max(len(h) for h in histories[alg])
        padded = []
        for h in histories[alg]:
            if len(h) < max_len:
                h = h + [h[-1]] * (max_len - len(h))
            padded.append(h)
        mean_curve = np.mean(np.array(padded), axis=0)
        x = np.arange(1, len(mean_curve) + 1)
        ax.plot(x, mean_curve, linewidth=2, color=ALG_COLORS.get(alg), label=alg)

    ax.set_title('Fig 12: Convergence Trajectories', fontsize=13, fontweight='bold')
    ax.set_xlabel('Iteration')
    ax.set_ylabel('Best Objective Value')
    ax.grid(alpha=0.3, linewidth=0.5)
    ax.legend(fontsize=9)
    plt.tight_layout()
    fig.savefig(FIGS_DIR / 'fig12_convergence.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print('Saved: fig12_convergence.png')


def plot_fig13_ablation():
    rows = _read_csv(PROCESSED_DIR / 'ablation_table.csv')
    if not rows:
        print('Skip: ablation_table.csv not found')
        return

    labels = [r.get('variant', '?') for r in rows]
    totals = [_as_float(r, 'total_mean') for r in rows]
    otdr = [_as_float(r, 'otdr_mean') for r in rows]

    fig, ax1 = plt.subplots(figsize=(11, 5.5), dpi=150)
    x = np.arange(len(labels))
    ax1.bar(x, totals, 0.55, color='#7E57C2', edgecolor='white', label='Total cost')
    ax1.set_ylabel('Total Cost')
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=20, ha='right')
    ax1.set_title('Fig 13: Tabu Component Ablation', fontsize=13, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3, linewidth=0.5)

    ax2 = ax1.twinx()
    ax2.plot(x, otdr, 'o-', color='#009688', linewidth=2, label='OTDR')
    ax2.set_ylabel('OTDR (%)')
    ax2.set_ylim(0, 105)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc='upper right')
    plt.tight_layout()
    fig.savefig(FIGS_DIR / 'fig13_ablation_tabu.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print('Saved: fig13_ablation_tabu.png')


def plot_fig13b_rrd_ablation():
    rows = _read_csv(PROCESSED_DIR / 'ablation_rrd_table.csv')
    if not rows:
        print('Skip: ablation_rrd_table.csv not found')
        return

    labels = [r.get('configuration', '?') for r in rows]
    totals = [_as_float(r, 'total_mean') for r in rows]
    otdr = [_as_float(r, 'otdr_mean') for r in rows]

    fig, ax1 = plt.subplots(figsize=(11, 5.5), dpi=150)
    x = np.arange(len(labels))
    ax1.bar(x, totals, 0.55, color='#607D8B', edgecolor='white', label='Total cost')
    ax1.set_ylabel('Total Cost')
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=18, ha='right')
    ax1.set_title('Fig 13b: Dynamic Event Ablation', fontsize=13, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3, linewidth=0.5)

    ax2 = ax1.twinx()
    ax2.plot(x, otdr, 'o-', color='#E91E63', linewidth=2, label='OTDR')
    ax2.set_ylabel('OTDR (%)')
    ax2.set_ylim(0, 105)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc='upper right')
    plt.tight_layout()
    fig.savefig(FIGS_DIR / 'fig13b_ablation_rrd.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print('Saved: fig13b_ablation_rrd.png')


def plot_fig14_memory():
    rows = _read_csv(PROCESSED_DIR / 'memory_analysis.csv')
    if not rows:
        print('Skip: memory_analysis.csv not found')
        return

    labels = [r.get('memory_component', '?') for r in rows]
    metrics = [
        ('cycling_prevention', 'Cycling Prevention', '#3F51B5'),
        ('diversification_score', 'Diversification', '#009688'),
        ('search_efficiency', 'Search Efficiency', '#FF9800'),
    ]
    x = np.arange(len(labels))
    width = 0.22

    fig, ax1 = plt.subplots(figsize=(12, 5.8), dpi=150)
    for idx, (key, label, color) in enumerate(metrics):
        values = [_as_float(r, key) for r in rows]
        ax1.bar(x + (idx - 1) * width, values, width, color=color,
                edgecolor='white', label=label)

    ax1.set_ylabel('Normalized Diagnostic Score')
    ax1.set_ylim(0, 1.1)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, rotation=18, ha='right')
    ax1.set_title('Fig 14: Memory Mechanism Diagnostics', fontsize=13, fontweight='bold')
    ax1.grid(axis='y', alpha=0.3, linewidth=0.5)

    ax2 = ax1.twinx()
    overhead = [_as_float(r, 'memory_overhead_mb') for r in rows]
    ax2.plot(x, overhead, 'o-', color='#263238', linewidth=2, label='Memory overhead')
    ax2.set_ylabel('Memory Overhead (MB)')

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=9, loc='upper left')
    plt.tight_layout()
    fig.savefig(FIGS_DIR / 'fig14_memory.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print('Saved: fig14_memory.png')


def plot_fig15_robustness():
    rows = _read_csv(PROCESSED_DIR / 'robustness_sigma.csv')
    if not rows:
        print('Skip: robustness_sigma.csv not found')
        return

    algs = [a for a in ALG_ORDER if any(r.get('algorithm') == a for r in rows)]
    sigmas = sorted({float(r.get('sigma')) for r in rows if r.get('sigma') not in ('', None)})
    if not algs or not sigmas:
        print('Skip: robustness_sigma.csv has no plottable data')
        return

    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=150)
    for alg in algs:
        y = []
        for sigma in sigmas:
            match = [r for r in rows if r.get('algorithm') == alg and abs(float(r.get('sigma')) - sigma) < 1e-9]
            y.append(_as_float(match[0], 'total_mean') if match else np.nan)
        ax.plot(sigmas, y, 'o-', linewidth=2, label=alg, color=ALG_COLORS.get(alg))

    ax.set_title('Fig 15: Robustness Under Traffic Uncertainty', fontsize=13, fontweight='bold')
    ax.set_xlabel('Traffic Uncertainty Sigma')
    ax.set_ylabel('Mean Total Cost')
    ax.grid(alpha=0.3, linewidth=0.5)
    ax.legend(fontsize=9)
    plt.tight_layout()
    fig.savefig(FIGS_DIR / 'fig15_robustness.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print('Saved: fig15_robustness.png')


def write_report_summary(results):
    main_rows = _read_csv(PROCESSED_DIR / 'main_comparison.csv')
    dispatch_rows = _read_csv(PROCESSED_DIR / 'rrd_dispatch_comparison.csv')

    lines = [
        '# Reproduction Figure Summary',
        '',
        '## Main Algorithm Comparison',
        '',
        '| Algorithm | Total | OTDR | CES |',
        '|---|---:|---:|---:|',
    ]
    for alg in ALG_ORDER:
        row = next((r for r in main_rows if r.get('algorithm') == alg), None)
        if row:
            lines.append(
                f"| {alg} | {_as_float(row, 'total_mean'):.1f} | "
                f"{_as_float(row, 'otdr_mean'):.1f}% | {_as_float(row, 'ces_mean'):.2f} |")

    if dispatch_rows:
        lines.extend(['', '## Dispatch Comparison', '', '| Mode | Mean Cost Reduction | Mean Response Time (ms) |', '|---|---:|---:|'])
        for mode in ['none', 'greedy', 'rollout']:
            subset = [r for r in dispatch_rows if r.get('dispatch_mode') == mode]
            reductions = [_as_float(r, 'cost_reduction') for r in subset if r.get('cost_reduction') not in ('', None)]
            response = [_as_float(r, 'response_time_ms') for r in subset]
            lines.append(f"| {mode} | {(np.mean(reductions) if reductions else 0):.1f} | {(np.mean(response) if response else 0):.1f} |")

    expected_figures = [
        'fig8_cost_comparison.png',
        'fig9_otdr_comparison.png',
        'fig10_ces_comparison.png',
        'fig11_dispatch.png',
        'fig12_convergence.png',
        'fig13_ablation_tabu.png',
        'fig13b_ablation_rrd.png',
        'fig14_memory.png',
        'fig15_robustness.png',
    ]
    lines.extend(['', '## Generated Figures', ''])
    for name in expected_figures:
        if (FIGS_DIR / name).exists():
            lines.append(f'- {name}')

    out = PROJECT_ROOT / 'outputs' / 'report' / 'REPORT_SUMMARY.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(lines) + '\n')
    print(f'Saved: {out.relative_to(PROJECT_ROOT)}')


def main():
    results = load_results()
    plot_fig8_cost_comparison(results)
    plot_fig9_otdr(results)
    plot_fig10_ces(results)
    plot_fig11_dispatch()
    plot_fig12_convergence()
    plot_fig13_ablation()
    plot_fig13b_rrd_ablation()
    plot_fig14_memory()
    plot_fig15_robustness()
    write_report_summary(results)
    print('\nAll figures generated.')


if __name__ == '__main__':
    main()
