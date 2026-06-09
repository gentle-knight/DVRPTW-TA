#!/usr/bin/env python3
"""
Visualize Phase 1 results — 47 customer nodes + 1 depot on Shanghai road network.

Run from project root:
    python3 datasets/customers/visualize_nodes.py
"""

import os, sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from utils.visualization import (
    load_graph,
    draw_road_network, draw_road_legend,
    draw_customers, draw_depot,
    draw_density_contours, draw_sample_labels,
    set_map_bounds, finalize_map,
    TW_COLORS,
)

# ── Paths ──
GRAPH_PATH = PROJECT_ROOT / 'datasets' / 'network' / 'shanghai_road_graph.pkl'
CUSTOMER_PATH = PROJECT_ROOT / 'datasets' / 'customers' / 'customers_47.csv'
OUTPUT_DIR = PROJECT_ROOT / 'outputs' / 'figures'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Density kernels (same as select_nodes.py) ──
COMMERCIAL_KERNELS = [
    {'center': (121.447, 31.229), 'sigma': (0.012, 0.010), 'weight': 1.2},
    {'center': (121.473, 31.230), 'sigma': (0.015, 0.012), 'weight': 1.0},
    {'center': (121.468, 31.236), 'sigma': (0.008, 0.005), 'weight': 0.8},
    {'center': (121.462, 31.221), 'sigma': (0.008, 0.005), 'weight': 0.7},
    {'center': (121.487, 31.226), 'sigma': (0.010, 0.008), 'weight': 0.6},
]
RESIDENTIAL_KERNELS = [
    {'center': (121.455, 31.255), 'sigma': (0.020, 0.015), 'weight': 0.9},
    {'center': (121.475, 31.205), 'sigma': (0.018, 0.014), 'weight': 0.8},
    {'center': (121.435, 31.240), 'sigma': (0.015, 0.012), 'weight': 0.7},
    {'center': (121.480, 31.215), 'sigma': (0.014, 0.010), 'weight': 0.5},
]
ALL_KERNELS = COMMERCIAL_KERNELS + [
    {'center': k['center'], 'sigma': k['sigma'], 'weight': k['weight'] * 0.6}
    for k in RESIDENTIAL_KERNELS
]

# ── Load data ──
G = load_graph(GRAPH_PATH)
customers = pd.read_csv(CUSTOMER_PATH)
depot_row = customers[customers['id'] == 0].iloc[0]
customer_rows = customers[customers['id'] > 0]

nodes_lon = np.array([data['x'] for _, data in G.nodes(data=True)])
nodes_lat = np.array([data['y'] for _, data in G.nodes(data=True)])

# ── Compute stats ──
total_demand = customer_rows['demand_kg'].sum()
fleet_cap = 4 * 120
morning_mask = customer_rows['tw_group'] == 'morning'
afternoon_mask = customer_rows['tw_group'] == 'afternoon'
evening_mask = customer_rows['tw_group'] == 'evening'

# ── Create figure ──
fig = plt.figure(figsize=(22, 11), dpi=150)
gs = fig.add_gridspec(1, 2, width_ratios=[1.6, 1],
                       left=0.04, right=0.98, top=0.94, bottom=0.04,
                       wspace=0.02)

# ── Panel A: Map ──
ax_map = fig.add_subplot(gs[0, 0])
draw_road_network(ax_map, G)
draw_density_contours(ax_map, ALL_KERNELS, nodes_lon, nodes_lat)
draw_customers(ax_map, customer_rows)
draw_depot(ax_map, depot_row)
draw_sample_labels(ax_map, customer_rows, max_labels=14)
set_map_bounds(ax_map, G)
finalize_map(ax_map, '', G)
ax_map.set_title('')
from matplotlib.lines import Line2D
road_handles = [
    Line2D([0],[0],color='#c62828',lw=1.3,label='Motorway / Trunk'),
    Line2D([0],[0],color='#f57c00',lw=0.7,label='Secondary'),
    Line2D([0],[0],color='#455a64',lw=0.4,label='Residential'),
]
tw_handles = [
    Line2D([0],[0],marker='o',color='w',markerfacecolor=TW_COLORS['morning'],
           markersize=7, label='Morning (9–12)'),
    Line2D([0],[0],marker='o',color='w',markerfacecolor=TW_COLORS['afternoon'],
           markersize=7, label='Afternoon (13–16)'),
    Line2D([0],[0],marker='o',color='w',markerfacecolor=TW_COLORS['evening'],
           markersize=7, label='Evening (17–20)'),
    Line2D([0],[0],marker='s',color='w',markerfacecolor='#d32f2f',
           markersize=8, label='Depot (Warehouse)'),
]
all_handles = road_handles + tw_handles
legend1 = ax_map.legend(handles=road_handles, loc='lower left',
                        fontsize=7, framealpha=0.8, title='Roads', title_fontsize=8)
legend2 = ax_map.legend(handles=tw_handles, loc='upper right',
                        fontsize=7, framealpha=0.8, title='Nodes', title_fontsize=8)
ax_map.add_artist(legend1)

# ── Panel B: Statistics ──
ax_stats = fig.add_subplot(gs[0, 1])
ax_stats.axis('off')
ax_stats.set_xlim(0, 1)
ax_stats.set_ylim(0, 1)

stats_data = [
    ('', ''),
    ('NETWORK', ''),
    ('  Nodes (total)', f'{len(G.nodes):,}'),
    ('  Edges (total)', f'{len(G.edges):,}'),
    ('  Area', '8 × 10 km² (Jing\'an–Huangpu)'),
    ('', ''),
    ('NODE SELECTION', ''),
    ('  Depot', f'1  ({depot_row["lon"]:.4f}°, {depot_row["lat"]:.4f}°)'),
    ('  Customers', '47'),
    ('', ''),
    ('DEMAND', ''),
    ('  Total', f'{total_demand:.1f} kg'),
    ('  Fleet capacity', f'{fleet_cap} kg (4 × 120 kg)'),
    ('  Utilization', f'{100*total_demand/fleet_cap:.1f}%'),
    ('  Mean per customer', f'{total_demand/47:.1f} kg'),
    ('  Range', f'[{customer_rows["demand_kg"].min():.1f}, {customer_rows["demand_kg"].max():.1f}] kg'),
    ('', ''),
    ('TIME WINDOWS', ''),
    (f'  Morning  (9–12)', f'{morning_mask.sum():2d} customers  ({customer_rows[morning_mask]["demand_kg"].sum():.1f} kg)'),
    (f'  Afternoon (13–16)', f'{afternoon_mask.sum():2d} customers  ({customer_rows[afternoon_mask]["demand_kg"].sum():.1f} kg)'),
    (f'  Evening  (17–20)', f'{evening_mask.sum():2d} customers  ({customer_rows[evening_mask]["demand_kg"].sum():.1f} kg)'),
    ('', ''),
    ('DENSITY MODEL (Gaussian Mixture)', ''),
    ('  Jing\'an Temple', 'σ=(0.012,0.010) w=1.2'),
    ('  People\'s Square', 'σ=(0.015,0.012) w=1.0'),
    ('  Nanjing Rd corridor', 'σ=(0.008,0.005) w=0.8'),
    ('  Huaihai Rd', 'σ=(0.008,0.005) w=0.7'),
    ('  Old City / Yuyuan', 'σ=(0.010,0.008) w=0.6'),
    ('  + 4 residential kernels', 'w=0.4–0.9 (×0.6 weight)'),
]

y = 0.96
for label, value in stats_data:
    is_header = value == '' and (label == '' or label.isupper() or 'DENSITY' in label)
    if label == '' and value == '':
        y -= 0.012
        continue
    if is_header:
        ax_stats.text(0.04, y, label, fontsize=10, fontweight='bold',
                      fontfamily='monospace', color='#333333', va='top')
        y -= 0.036
    else:
        color = TW_COLORS.get(label.split('(')[0].strip().lower().split()[0], '#444444')
        ax_stats.text(0.04, y, f'{label}', fontsize=8.5,
                      fontfamily='monospace', color='#555555', va='top')
        ax_stats.text(0.56, y, f'{value}', fontsize=8.5,
                      fontfamily='monospace', color='#333333', va='top')
        y -= 0.025

# ── Demand bar chart inset in stats panel ──
sorted_demands = np.sort(customer_rows['demand_kg'].values)
ax_demand_inset = ax_stats.inset_axes([0.45, 0.02, 0.52, 0.18])
ax_demand_inset.bar(range(1, 48), sorted_demands, width=0.9,
                     color='#546e7a', edgecolor='white', linewidth=0.3)
ax_demand_inset.axhline(y=sorted_demands.mean(), color='#d32f2f',
                         linestyle='--', linewidth=1, label=f'Mean={sorted_demands.mean():.1f}')
ax_demand_inset.set_xticks([1, 15, 30, 47])
ax_demand_inset.set_xticklabels(['1', '15', '30', '47'], fontsize=6)
ax_demand_inset.set_yticks([3, 6, 9, 12])
ax_demand_inset.set_yticklabels(['3', '6', '9', '12'], fontsize=6)
ax_demand_inset.set_xlabel('Customer (sorted)', fontsize=6)
ax_demand_inset.set_ylabel('kg', fontsize=6)
ax_demand_inset.legend(fontsize=6, loc='upper left')
ax_demand_inset.set_ylim(0, 14)

for spine in ax_demand_inset.spines.values():
    spine.set_linewidth(0.5)

fig.suptitle('Phase 1 — Customer Node Selection on Shanghai Jing\'an–Huangpu Road Network\n'
             'T-ALNS-RRD: Tabu-guided ALNS with Rollout-based Real-Time Dispatch',
             fontsize=14, fontweight='bold')

output_path = OUTPUT_DIR / 'phase1_node_selection.png'
fig.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
plt.close(fig)

print(f'Saved: {output_path}')
