#!/usr/bin/env python3
"""
Phase 1: Select 47 customer nodes + 1 depot from Shanghai OSM road network.

Paper specs:
  - 47 customers distributed by weighted spatial density (commercial/residential)
  - 1 depot at central warehouse hub
  - d_i in [3, 12] kg, s_i = 4 min
  - Time windows: morning (9-12), afternoon (13-16), evening (17-20)
  - 4 homogeneous vehicles, Q=120 kg, max 10h operation

Geography (Jing'an-Huangpu known landmarks):
  Jing'an Temple:         121.447, 31.229  (commercial hub)
  People's Square:        121.473, 31.230  (city center)
  Nanjing Rd Corridor:    121.468, 31.236  (retail strip)
  Huaihai Rd:             121.462, 31.221  (high-end commercial)
  Old City/Yuyuan:        121.487, 31.226  (traditional commercial)
  Zhabei North:           121.455, 31.255  (mixed residential)
  Huangpu South:          121.475, 31.205  (residential)
  Jing'an West:           121.435, 31.240  (residential)
"""

import os, sys, pickle, random
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from collections import defaultdict
from scipy.stats import multivariate_normal

random.seed(42)
np.random.seed(42)

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
NETWORK_DIR = os.path.join(DATA_DIR, 'datasets', 'network')
CUSTOMER_DIR = os.path.join(DATA_DIR, 'datasets', 'customers')
FIGS_DIR = os.path.join(DATA_DIR, 'outputs', 'figures')
os.makedirs(CUSTOMER_DIR, exist_ok=True)
os.makedirs(FIGS_DIR, exist_ok=True)

graph_path = os.path.join(NETWORK_DIR, 'shanghai_road_graph.pkl')
with open(graph_path, 'rb') as f:
    G = pickle.load(f)

nodes_lon = np.array([data['x'] for _, data in G.nodes(data=True)])
nodes_lat = np.array([data['y'] for _, data in G.nodes(data=True)])
node_ids = list(G.nodes())

print(f"Loaded graph: {len(node_ids)} nodes")

# ── Step 1: Define density kernels ──

COMMERCIAL_KERNELS = [
    {'center': (121.447, 31.229), 'sigma': (0.012, 0.010), 'weight': 1.2},  # Jing'an Temple
    {'center': (121.473, 31.230), 'sigma': (0.015, 0.012), 'weight': 1.0},  # People's Square
    {'center': (121.468, 31.236), 'sigma': (0.008, 0.005), 'weight': 0.8},  # Nanjing Rd corridor
    {'center': (121.462, 31.221), 'sigma': (0.008, 0.005), 'weight': 0.7},  # Huaihai Rd
    {'center': (121.487, 31.226), 'sigma': (0.010, 0.008), 'weight': 0.6},  # Old City
]

RESIDENTIAL_KERNELS = [
    {'center': (121.455, 31.255), 'sigma': (0.020, 0.015), 'weight': 0.9},  # Zhabei north
    {'center': (121.475, 31.205), 'sigma': (0.018, 0.014), 'weight': 0.8},  # Huangpu south
    {'center': (121.435, 31.240), 'sigma': (0.015, 0.012), 'weight': 0.7},  # Jing'an west
    {'center': (121.480, 31.215), 'sigma': (0.014, 0.010), 'weight': 0.5},  # South residential
]

def kernel_density(lon, lat, kernels):
    d = np.zeros(len(lon))
    for k in kernels:
        delta_lon = (lon - k['center'][0]) / k['sigma'][0]
        delta_lat = (lat - k['center'][1]) / k['sigma'][1]
        d += k['weight'] * np.exp(-0.5 * (delta_lon**2 + delta_lat**2))
    return d

weight_commercial = kernel_density(nodes_lon, nodes_lat, COMMERCIAL_KERNELS)
weight_residential = kernel_density(nodes_lon, nodes_lat, RESIDENTIAL_KERNELS)
weight_total = weight_commercial * 0.55 + weight_residential * 0.45

# Normalize
weight_total /= weight_total.sum()

# Add base uniform component (10%) to ensure non-zero probability
weight_total = weight_total * 0.9 + 0.1 / len(node_ids)

# ── Step 2: Sample 47 customers ──

sampled_indices = np.random.choice(
    len(node_ids), size=47, replace=False, p=weight_total
)

customer_ids = [node_ids[i] for i in sampled_indices]
customer_lon = nodes_lon[sampled_indices]
customer_lat = nodes_lat[sampled_indices]

# ── Step 3: Place depot at central warehouse ──

DEPOT_CENTER = (121.465, 31.229)
dist_to_depot = np.sqrt((nodes_lon - DEPOT_CENTER[0])**2 + (nodes_lat - DEPOT_CENTER[1])**2)
# Exclude sampled customer indices
available = np.ones(len(node_ids), dtype=bool)
available[sampled_indices] = False
available_indices = np.where(available)[0]
depot_idx = available_indices[np.argmin(dist_to_depot[available_indices])]
depot_id = node_ids[depot_idx]
depot_lon = nodes_lon[depot_idx]
depot_lat = nodes_lat[depot_idx]

# ── Step 4: Assign demand, time windows, service time ──

np.random.seed(2024)
demands = np.random.uniform(3, 12, 47).round(1)
service_times = np.full(47, 4.0)

# Split customers into three time window groups
tw_order = np.random.permutation(47)
n_morning = 16
n_afternoon = 16
n_evening = 15

time_windows = np.empty(47, dtype=object)
for i in range(47):
    pos = tw_order[i]
    if i < n_morning:
        time_windows[pos] = ('09:00', '12:00')
    elif i < n_morning + n_afternoon:
        time_windows[pos] = ('13:00', '16:00')
    else:
        time_windows[pos] = ('17:00', '20:00')

tw_groups = np.full(47, '', dtype=object)
for i, tw in enumerate(time_windows):
    if tw == ('09:00', '12:00'):
        tw_groups[i] = 'morning'
    elif tw == ('13:00', '16:00'):
        tw_groups[i] = 'afternoon'
    else:
        tw_groups[i] = 'evening'

# ── Step 5: Save CSV ──

output_path = os.path.join(CUSTOMER_DIR, 'customers_47.csv')
with open(output_path, 'w') as f:
    f.write('id,node_id,lon,lat,demand_kg,service_min,window_start,window_end,tw_group\n')
    # Depot is node 0
    f.write(f'0,{depot_id},{depot_lon:.6f},{depot_lat:.6f},0,0,,,depot\n')
    for i in range(47):
        f.write(f'{i+1},{customer_ids[i]},{customer_lon[i]:.6f},{customer_lat[i]:.6f},'
                f'{demands[i]:.1f},4,{time_windows[i][0]},{time_windows[i][1]},{tw_groups[i]}\n')

# ── Step 6: Validation stats ──

total_demand = demands.sum()
fleet_capacity = 4 * 120
print(f"\nTotal demand: {total_demand:.1f} kg / Fleet capacity: {fleet_capacity} kg ({100*total_demand/fleet_capacity:.1f}%)")
print(f"Demand range: [{demands.min():.1f}, {demands.max():.1f}] kg")
print(f"Time window distribution:")
for g in ['morning', 'afternoon', 'evening']:
    count = sum(tw_groups == g)
    sub_demand = demands[tw_groups == g].sum()
    print(f"  {g}: {count} customers, {sub_demand:.1f} kg")
print(f"Depot: node {depot_id} ({depot_lon:.4f}, {depot_lat:.4f})")

# ── Step 7: Visualization ──

print("\nGenerating visualization...")
fig, axes = plt.subplots(1, 2, figsize=(20, 10), dpi=150)

# Panel A: Road network + selected nodes
ax = axes[0]
# Light road background
for (u, v), edges in defaultdict(list, {}).items():
    pass  # build edge_pairs

edge_pairs = defaultdict(list)
for u, v, k, data in G.edges(keys=True, data=True):
    edge_pairs[(u, v)].append((k, data))

pos = {n: (data['x'], data['y']) for n, data in G.nodes(data=True)}
for (u, v), edges in edge_pairs.items():
    k, data = edges[0]
    hwy = data.get('highway', 'unclassified')
    if isinstance(hwy, list): hwy = hwy[0]
    if hwy in ('motorway', 'trunk', 'primary', 'secondary'):
        c, lw, al = '#cccccc', 0.3, 0.4
    else:
        c, lw, al = '#e8e8e8', 0.2, 0.3
    ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]],
            color=c, linewidth=lw, alpha=al, solid_capstyle='round')

# Plot customers by time window
tw_colors = {'morning': '#2196F3', 'afternoon': '#FF9800', 'evening': '#9C27B0'}
tw_labels = {'morning': 'Morning (9-12)', 'afternoon': 'Afternoon (13-16)', 'evening': 'Evening (17-20)'}

for tw_group in ['morning', 'afternoon', 'evening']:
    mask = tw_groups == tw_group
    ax.scatter(customer_lon[mask], customer_lat[mask],
               c=tw_colors[tw_group], s=60, edgecolors='white', linewidths=0.8,
               zorder=5, label=tw_labels[tw_group], alpha=0.85)

# Depot
ax.scatter(depot_lon, depot_lat, c='#d32f2f', s=250, marker='s',
           edgecolors='black', linewidths=1.5, zorder=6, label='Depot')

# Density contours
x_grid = np.linspace(nodes_lon.min(), nodes_lon.max(), 100)
y_grid = np.linspace(nodes_lat.min(), nodes_lat.max(), 100)
X, Y = np.meshgrid(x_grid, y_grid)
Z = np.zeros_like(X)
for k in COMMERCIAL_KERNELS:
    dx = (X - k['center'][0]) / k['sigma'][0]
    dy = (Y - k['center'][1]) / k['sigma'][1]
    Z += k['weight'] * np.exp(-0.5 * (dx**2 + dy**2))
for k in RESIDENTIAL_KERNELS:
    dx = (X - k['center'][0]) / k['sigma'][0]
    dy = (Y - k['center'][1]) / k['sigma'][1]
    Z += k['weight'] * 0.6 * np.exp(-0.5 * (dx**2 + dy**2))

# Contour at 25%, 50%, 75%
levels = [np.percentile(Z[Z > 0], p) for p in [25, 50, 75]]
cs = ax.contour(X, Y, Z, levels=levels, colors='#555555', linewidths=0.8, alpha=0.5, zorder=3)
ax.clabel(cs, inline=True, fontsize=7, fmt='%.0f%%')

# Mark commercial centers
for k in COMMERCIAL_KERNELS:
    ax.text(k['center'][0], k['center'][1], '✧', fontsize=14, ha='center', va='center',
            color='#444444', alpha=0.4, zorder=4)

ax.legend(loc='lower left', fontsize=8, framealpha=0.9)
ax.set_title('Panel A: Node Selection\n47 Customers + 1 Depot on Shanghai Jing\'an–Huangpu Network',
             fontsize=11, fontweight='bold')
ax.set_xlabel('Longitude'); ax.set_ylabel('Latitude')
ax.set_aspect('equal')
bbox = G.graph.get('bbox')
if bbox:
    ax.set_xlim(bbox[1], bbox[3]); ax.set_ylim(bbox[0], bbox[2])

# Panel B: Statistics
ax2 = axes[1]
ax2.axis('off')

stats_lines = [
    "DEMAND DISTRIBUTION",
    f"  Total: {total_demand:.1f} kg / Fleet: {fleet_capacity} kg ({100*total_demand/fleet_capacity:.1f}%)",
    f"  Range: [{demands.min():.1f}, {demands.max():.1f}] kg, Mean: {demands.mean():.1f} kg",
    f"  Std: {demands.std():.1f} kg",
    "",
    "TIME WINDOW DISTRIBUTION",
]
for g, color in [('morning', '#2196F3'), ('afternoon', '#FF9800'), ('evening', '#9C27B0')]:
    count = sum(tw_groups == g)
    sub_demand = demands[tw_groups == g].sum()
    stats_lines.append(f"  ● {g.capitalize():10s}  {count:2d} customers  ({sub_demand:.1f} kg)")

stats_lines += [
    "",
    "VEHICLE FLEET",
    "  4 homogeneous vehicles",
    "  Capacity: 120 kg each",
    "  Max operation: 10 hours",
    "  Customer-to-vehicle ratio: 11.75:1",
    "",
    "SPATIAL COVERAGE",
    f"  Area: ~80 km² (8×10 km²)",
    f"  Study zone: Jing'an–Huangpu districts",
    f"  Road network: 3,500 nodes / 8,106 edges",
    f"  Depot: ({depot_lon:.4f}, {depot_lat:.4f})",
    "",
    "ROAD TYPE DISTRIBUTION (sampled)",
]

# Count road types near sampled nodes
hwy_counts = defaultdict(int)
for nid in customer_ids:
    for _, v, data in G.out_edges(nid, data=True):
        hwy = data.get('highway', 'unclassified')
        if isinstance(hwy, list): hwy = hwy[0]
        hwy_counts[hwy] += 1
total_hwy = sum(hwy_counts.values())
for hwy, count in sorted(hwy_counts.items(), key=lambda x: -x[1])[:6]:
    stats_lines.append(f"  {hwy:20s}: {count:4d} ({100*count/total_hwy:.1f}%)")

y_pos = 1.0
for line in stats_lines:
    weight = 'bold' if line.startswith(('DEMAND', 'TIME', 'VEHICLE', 'SPATIAL', 'ROAD')) and not line.startswith('  ') else 'normal'
    color = '#333333' if weight == 'bold' else '#555555'
    ax2.text(0.05, y_pos, line, fontsize=9, fontfamily='monospace', weight=weight, color=color, va='top')
    y_pos -= 0.035 if line else 0.015

ax2.set_xlim(0, 1); ax2.set_ylim(0, 1.05)

fig.suptitle('T-ALNS-RRD Phase 1 — Customer Node Selection & Configuration',
             fontsize=14, fontweight='bold', y=0.98)
plt.tight_layout(rect=[0, 0, 1, 0.96])
fig_path = os.path.join(FIGS_DIR, 'phase1_node_selection.png')
fig.savefig(fig_path, dpi=150, bbox_inches='tight')
print(f"Saved: {fig_path}")

# ── Step 8: Additional demand-only histogram ──
fig2, ax3 = plt.subplots(figsize=(10, 4), dpi=120)
ax3.bar(range(1, 48), sorted(demands), color='#2196F3', edgecolor='white', linewidth=0.5)
ax3.axhline(y=demands.mean(), color='#d32f2f', linestyle='--', linewidth=1.5,
            label=f'Mean = {demands.mean():.1f} kg')
ax3.axhline(y=120/4, color='#FF9800', linestyle=':', linewidth=1,
            label=f'Per-vehicle avg limit = 30 kg')
ax3.set_xlabel('Customer ID (sorted by demand)')
ax3.set_ylabel('Demand (kg)')
ax3.set_title('Customer Demand Distribution (d_i ∈ [3, 12] kg)')
ax3.legend(fontsize=9)
ax3.set_ylim(0, 14)
fig2.tight_layout()
hist_path = os.path.join(FIGS_DIR, 'phase1_demand_histogram.png')
fig2.savefig(hist_path, dpi=120, bbox_inches='tight')
print(f"Saved: {hist_path}")
plt.close('all')

print(f"\nCustomer data saved to: {output_path}")
print("Phase 1 complete.")
