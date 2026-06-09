#!/usr/bin/env python3
"""
Phase 2: Generate time-indexed traffic tensor for 48 nodes × 12 intervals × 3 params.

Paper: DVRPTW-TA with t_ij(T_i), ρ_ij(T_i), η_ij(h) — Eqs. (8)–(10)

Data flow:
  OSM graph → all-pairs shortest paths → road-type composition per O-D pair
  → time-dependent speed factors × 12 intervals
  → traffic_tensor.npz [48, 48, 12, 3]

Outputs:
  datasets/traffic/traffic_tensor.npz
  datasets/traffic/traffic_metadata.json
  outputs/figures/phase2_traffic_profile.png
"""

import os, sys, json, pickle, time as time_mod
from collections import defaultdict, Counter
from pathlib import Path

import numpy as np
import networkx as nx

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from utils.visualization import load_graph

GRAPH_PATH = PROJECT_ROOT / 'datasets' / 'network' / 'shanghai_road_graph.pkl'
CUSTOMER_PATH = PROJECT_ROOT / 'datasets' / 'customers' / 'customers_47.csv'
TRAFFIC_DIR = PROJECT_ROOT / 'datasets' / 'traffic'
OUTPUT_DIR = PROJECT_ROOT / 'outputs' / 'figures'
TRAFFIC_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Constants ──

H = 12
INTERVAL_START_HOUR = 6
INTERVAL_LABELS = [
    f'{h:02d}:00–{(h+1)%24:02d}:00'
    for h in range(INTERVAL_START_HOUR, INTERVAL_START_HOUR + H)
]

DEFAULT_SPEEDS_KMH = {
    'motorway':      60, 'motorway_link':  50,
    'trunk':         55, 'trunk_link':     45,
    'primary':       50, 'primary_link':   40,
    'secondary':     40, 'secondary_link': 35,
    'tertiary':      30, 'tertiary_link':  25,
    'residential':   20,
    'living_street': 15,
    'unclassified':  20,
    'service':       15,
}

# Time-dependent speed multipliers (relative to free-flow at hour h)
# Higher = more congestion = slower = longer travel time
# Based on typical Shanghai urban traffic patterns
CONGESTION_MULTIPLIER = np.array([
    1.15,   # 06:00–07:00  pre-peak, slight congestion building
    1.55,   # 07:00–08:00  morning peak
    1.70,   # 08:00–09:00  morning peak (worst)
    1.30,   # 09:00–10:00  post-peak
    1.05,   # 10:00–11:00  off-peak
    0.95,   # 11:00–12:00  off-peak (best flow)
    1.10,   # 12:00–13:00  midday
    1.00,   # 13:00–14:00  off-peak
    1.00,   # 14:00–15:00  off-peak
    1.05,   # 15:00–16:00  off-peak
    1.40,   # 16:00–17:00  afternoon pre-peak
    1.65,   # 17:00–18:00  evening peak
])

# Congestion density γ_ij^(h) ∈ [0,1] per road-type × hour
# Higher for arterials during peak hours
CONGESTION_DENSITY_BASE = {
    'motorway': 0.6, 'trunk': 0.5, 'primary': 0.4,
    'secondary': 0.25, 'tertiary': 0.15,
    'residential': 0.05, 'other': 0.02,
}

# ── Load data ──

G = load_graph(GRAPH_PATH)

customers = pd = __import__('pandas')
customers_df = pd.read_csv(CUSTOMER_PATH)

node_osm_ids = customers_df['node_id'].tolist()
node_labels = customers_df['id'].tolist()
n_nodes = len(node_osm_ids)
assert n_nodes == 48, f"Expected 48 nodes, got {n_nodes}"

osm_id_to_idx = {osm_id: idx for idx, osm_id in enumerate(node_osm_ids)}
idx_to_label = {i: node_labels[i] for i in range(n_nodes)}
print(f"Loaded {n_nodes} nodes (1 depot + 47 customers)")

# ── Step 1: Compute road-type composition of the network ──

def get_edge_speed(data):
    maxspeed = data.get('maxspeed', None)
    hwy = data.get('highway', 'unclassified')
    if isinstance(hwy, list):
        hwy = hwy[0]
    if isinstance(maxspeed, list):
        maxspeed = maxspeed[0]
    if maxspeed is not None:
        try:
            return float(str(maxspeed).split()[0])
        except (ValueError, AttributeError):
            pass
    return DEFAULT_SPEEDS_KMH.get(hwy, 20)

def get_hwy_class(data):
    hwy = data.get('highway', 'unclassified')
    if isinstance(hwy, list):
        hwy = hwy[0]
    if hwy in ('motorway', 'motorway_link', 'trunk', 'trunk_link'):
        return 'arterial'
    elif hwy in ('primary', 'primary_link', 'secondary', 'secondary_link'):
        return 'collector'
    elif hwy in ('tertiary', 'tertiary_link'):
        return 'tertiary'
    elif hwy in ('residential', 'living_street'):
        return 'residential'
    else:
        return 'service'

# Build weighted graph for shortest path (travel time in minutes)
# Fall back to Haversine distance if OSM 'length' attribute is missing
import math

def haversine_m(lon1, lat1, lon2, lat2):
    R = 6371000
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

print("Building travel-time weighted graph...")
missing_length = 0
for u, v, k, data in G.edges(keys=True, data=True):
    speed = get_edge_speed(data)
    length = data.get('length', None)
    if length is None or length <= 0:
        lon1, lat1 = G.nodes[u].get('x', 0), G.nodes[u].get('y', 0)
        lon2, lat2 = G.nodes[v].get('x', 0), G.nodes[v].get('y', 0)
        length = haversine_m(lon1, lat1, lon2, lat2) if (lon1 and lon2) else 50.0
        data['length'] = length
        missing_length += 1
    if speed > 0 and length > 0:
        travel_time_min = (length / 1000) / speed * 60
    else:
        travel_time_min = 0.5
    data['travel_time_free'] = travel_time_min
    data['speed_kmh'] = speed
    data['hwy_class'] = get_hwy_class(data)

print(f"  Edges with missing length (filled via Haversine): {missing_length}")

# ── Step 2: All-pairs shortest paths ──

print("Computing all-pairs shortest paths (48 nodes, ~2256 O-D pairs)...")
start_t = time_mod.time()

Gu = G.to_undirected()

travel_time_free = np.zeros((n_nodes, n_nodes), dtype=np.float32)
total_length = np.zeros((n_nodes, n_nodes), dtype=np.float32)
road_class_dist = np.zeros((n_nodes, n_nodes, 5), dtype=np.float32)

class_names = ['arterial', 'collector', 'tertiary', 'residential', 'service']
class_idx = {name: i for i, name in enumerate(class_names)}

pair_count = 0
for i in range(n_nodes):
    src = node_osm_ids[i]
    try:
        lengths, paths = nx.single_source_dijkstra(
            Gu, src, weight='travel_time_free'
        )
    except Exception:
        print(f"  Warning: Dijkstra failed from node {i} ({src}), skipping")
        continue

    for j in range(n_nodes):
        if i == j:
            travel_time_free[i, j] = 0.0
            total_length[i, j] = 0.0
            continue

        dst = node_osm_ids[j]
        if dst not in lengths:
            travel_time_free[i, j] = 9999.0
            total_length[i, j] = 0.0
            continue

        pair_count += 1
        travel_time_free[i, j] = lengths[dst]
        path = paths[dst]

        path_length = 0.0
        path_classes = np.zeros(5, dtype=np.float32)
        for p in range(len(path) - 1):
            edge_data = G.get_edge_data(path[p], path[p+1])
            if not edge_data:
                edge_data = G.get_edge_data(path[p+1], path[p])
            if edge_data:
                e = edge_data[list(edge_data.keys())[0]]
                path_length += e.get('length', 0)
                cls = e.get('hwy_class', 'service')
                if cls in class_idx:
                    path_classes[class_idx[cls]] += e.get('length', 0)

        total_length[i, j] = path_length
        road_class_dist[i, j] = path_classes

    if (i + 1) % 10 == 0:
        print(f"  Node {i+1}/{n_nodes} done ({time_mod.time() - start_t:.1f}s)")

elapsed = time_mod.time() - start_t
print(f"All-pairs done in {elapsed:.1f}s ({pair_count} valid O-D pairs)")

# ── Step 3: Time-dependent traffic tensor ──

# T[i, j, h, 0] = travel time (minutes)
# T[i, j, h, 1] = congestion density γ ∈ [0,1]
# T[i, j, h, 2] = reliability margin η (minutes)

traffic_tensor = np.zeros((n_nodes, n_nodes, H, 3), dtype=np.float32)

# Compute road-class proportions for each O-D pair
road_class_prop = np.zeros((n_nodes, n_nodes, 5), dtype=np.float32)
for i in range(n_nodes):
    for j in range(n_nodes):
        total_len = road_class_dist[i, j].sum()
        if total_len > 0:
            road_class_prop[i, j] = road_class_dist[i, j] / total_len

# Congestion density contribution per class
congestion_density_per_class = np.array([
    CONGESTION_DENSITY_BASE['motorway'],     # arterial
    CONGESTION_DENSITY_BASE['primary'],       # collector
    CONGESTION_DENSITY_BASE['tertiary'],      # tertiary
    CONGESTION_DENSITY_BASE['residential'],   # residential
    CONGESTION_DENSITY_BASE['other'],         # service
])

# Sensitivity: arterials get more congestion amplification during peaks
# than residential streets (they fill up faster)
PEAK_AMPLIFICATION_PER_CLASS = np.array([1.8, 1.5, 1.2, 0.8, 0.5])

print("Building time-dependent traffic tensor...")
for h in range(H):
    multiplier = CONGESTION_MULTIPLIER[h]
    peak_ratio = (multiplier - 1.0) / 0.7  # normalized peak intensity [0, 1]

    for i in range(n_nodes):
        for j in range(n_nodes):
            if i == j:
                continue
            if travel_time_free[i, j] >= 9999:
                traffic_tensor[i, j, h, 0] = 9999.0
                continue

            free_time = travel_time_free[i, j]
            props = road_class_prop[i, j]

            # Travel time = free-flow × congestion_multiplier weighted by road class
            class_weighted_mult = (
                multiplier
                + peak_ratio * (props * PEAK_AMPLIFICATION_PER_CLASS).sum() * 0.3
            )
            travel_time = free_time * class_weighted_mult
            traffic_tensor[i, j, h, 0] = travel_time

            # Congestion density γ ∈ [0, 1]
            base_density = (props * congestion_density_per_class).sum()
            time_density = min(1.0, peak_ratio * 1.2)
            traffic_tensor[i, j, h, 1] = min(1.0, base_density + time_density * 0.4)

            # Reliability margin η (minutes) — std deviation proportional to travel time
            variability = 0.05 + peak_ratio * 0.20
            traffic_tensor[i, j, h, 2] = travel_time * variability

# ── Step 4: Save ──

np.savez_compressed(
    TRAFFIC_DIR / 'traffic_tensor.npz',
    tensor=traffic_tensor,
    travel_time_free=travel_time_free,
    total_length=total_length,
    road_class_dist=road_class_dist,
    road_class_prop=road_class_prop,
    congestion_multiplier=CONGESTION_MULTIPLIER,
    congestion_density_base=congestion_density_per_class,
)

metadata = {
    'n_nodes': n_nodes,
    'n_intervals': H,
    'interval_labels': INTERVAL_LABELS,
    'interval_start_hour': INTERVAL_START_HOUR,
    'node_osm_ids': [int(x) for x in node_osm_ids],
    'node_labels': [int(x) for x in node_labels],
    'congestion_multiplier': CONGESTION_MULTIPLIER.tolist(),
    'description': 'Traffic tensor for DVRPTW-TA: t_ij(h), γ_ij(h), η_ij(h)',
    'paper_equations': 'Eqs. (8), (9), (10)',
}
with open(TRAFFIC_DIR / 'traffic_metadata.json', 'w') as f:
    json.dump(metadata, f, indent=2)

print(f"\nSaved: traffic_tensor.npz ({os.path.getsize(TRAFFIC_DIR / 'traffic_tensor.npz')/1024:.0f} KB)")
print(f"Saved: traffic_metadata.json")

# ── Step 5: Validation stats ──

valid_mask = (travel_time_free < 9999) & (travel_time_free > 0)
print(f"\nValidation:")
print(f"  Valid O-D pairs: {valid_mask.sum()} / {n_nodes*(n_nodes-1)}")
print(f"  Free-flow travel time: {travel_time_free[valid_mask].min():.1f} – {travel_time_free[valid_mask].max():.1f} min")
print(f"  Mean free-flow: {travel_time_free[valid_mask].mean():.1f} min")
print(f"  Peak hour (h=2, 08-09): mean time ×{traffic_tensor[:,:,2,0][valid_mask].mean()/travel_time_free[valid_mask].mean():.2f}")
print(f"  Off-peak (h=7, 13-14): mean time ×{traffic_tensor[:,:,7,0][valid_mask].mean()/travel_time_free[valid_mask].mean():.2f}")

road_comp = road_class_prop[valid_mask].mean(axis=0)
for i, name in enumerate(class_names):
    print(f"  Avg {name}: {road_comp[i]*100:.1f}%")

# ── Step 6: Visualization ──

fig = plt.figure(figsize=(20, 12), dpi=150)
gs = fig.add_gridspec(2, 3, left=0.05, right=0.97, top=0.92, bottom=0.06,
                       hspace=0.30, wspace=0.28)

# A: Travel time heatmap (peak hour h=2 = 08:00-09:00)
ax_a = fig.add_subplot(gs[0, 0])
peak_h = 2
tt_peak = traffic_tensor[:, :, peak_h, 0].copy()
tt_peak[tt_peak >= 9999] = np.nan
im_a = ax_a.imshow(tt_peak, cmap='YlOrRd', aspect='auto', vmin=0)
ax_a.set_title(f'Travel Time — Peak Hour ({INTERVAL_LABELS[peak_h]})', fontsize=10, fontweight='bold')
ax_a.set_xlabel('Destination Node ID'); ax_a.set_ylabel('Origin Node ID')
cbar_a = plt.colorbar(im_a, ax=ax_a, shrink=0.8)
cbar_a.set_label('Minutes', fontsize=8)
ax_a.set_xticks([0, 10, 20, 30, 40, 47])
ax_a.set_yticks([0, 10, 20, 30, 40, 47])

# B: Travel time heatmap (off-peak h=7 = 13:00-14:00)
ax_b = fig.add_subplot(gs[0, 1])
off_h = 7
tt_off = traffic_tensor[:, :, off_h, 0].copy()
tt_off[tt_off >= 9999] = np.nan
im_b = ax_b.imshow(tt_off, cmap='YlOrRd', aspect='auto', vmin=0)
ax_b.set_title(f'Travel Time — Off-Peak ({INTERVAL_LABELS[off_h]})', fontsize=10, fontweight='bold')
ax_b.set_xlabel('Destination Node ID'); ax_b.set_ylabel('Origin Node ID')
cbar_b = plt.colorbar(im_b, ax=ax_b, shrink=0.8)
cbar_b.set_label('Minutes', fontsize=8)
ax_b.set_xticks([0, 10, 20, 30, 40, 47])
ax_b.set_yticks([0, 10, 20, 30, 40, 47])

# C: Congestion multiplier over time
ax_c = fig.add_subplot(gs[0, 2])
hours = np.arange(INTERVAL_START_HOUR, INTERVAL_START_HOUR + H)
ax_c.fill_between(hours, 1.0, CONGESTION_MULTIPLIER, alpha=0.3, color='#e65100')
ax_c.plot(hours, CONGESTION_MULTIPLIER, 'o-', color='#e65100', linewidth=2, markersize=6)
ax_c.axhline(y=1.0, color='#999999', linestyle='--', linewidth=0.8, label='Free-flow')
ax_c.set_xticks(hours)
ax_c.set_xticklabels([f'{h:02d}:00' for h in hours], rotation=45, fontsize=7)
ax_c.set_ylabel('Congestion Multiplier', fontsize=9)
ax_c.set_title('Time-Dependent Congestion Profile', fontsize=10, fontweight='bold')
ax_c.legend(fontsize=8)
ax_c.set_ylim(0.8, 2.0)
ax_c.grid(axis='y', alpha=0.3, linewidth=0.5)

# D: Road type composition histogram (averaged across all O-D pairs)
ax_d = fig.add_subplot(gs[1, 0])
colors_road = ['#c62828', '#e65100', '#689f38', '#455a64', '#90a4ae']
roads_avg = road_class_prop[valid_mask].mean(axis=0) * 100
ax_d.bar(class_names, roads_avg, color=colors_road, edgecolor='white', linewidth=0.5)
ax_d.set_title('Average Road-Type Composition per O-D Pair', fontsize=10, fontweight='bold')
ax_d.set_ylabel('% of Path Length', fontsize=9)
ax_d.tick_params(axis='x', rotation=30, labelsize=8)

# E: Travel time distribution histogram (free-flow)
ax_e = fig.add_subplot(gs[1, 1])
tt_values = travel_time_free[valid_mask]
ax_e.hist(tt_values, bins=40, color='#546e7a', edgecolor='white', alpha=0.85)
ax_e.axvline(x=tt_values.mean(), color='#d32f2f', linestyle='--', linewidth=1.5,
             label=f'Mean = {tt_values.mean():.1f} min')
ax_e.axvline(x=np.median(tt_values), color='#FF9800', linestyle=':', linewidth=1.5,
             label=f'Median = {np.median(tt_values):.1f} min')
ax_e.set_title('Free-Flow Travel Time Distribution', fontsize=10, fontweight='bold')
ax_e.set_xlabel('Travel Time (minutes)', fontsize=9)
ax_e.set_ylabel('Frequency', fontsize=9)
ax_e.legend(fontsize=8)

# F: Congestion density heatmap (peak vs off-peak difference)
ax_f = fig.add_subplot(gs[1, 2])
gamma_diff = traffic_tensor[:, :, peak_h, 1] - traffic_tensor[:, :, off_h, 1]
gamma_diff[travel_time_free >= 9999] = np.nan
im_f = ax_f.imshow(gamma_diff, cmap='Reds', aspect='auto', vmin=0, vmax=0.5)
ax_f.set_title(f'Δ Congestion Density (Peak − Off-Peak)', fontsize=10, fontweight='bold')
ax_f.set_xlabel('Destination Node ID'); ax_f.set_ylabel('Origin Node ID')
cbar_f = plt.colorbar(im_f, ax=ax_f, shrink=0.8)
cbar_f.set_label('γ difference', fontsize=8)
ax_f.set_xticks([0, 10, 20, 30, 40, 47])
ax_f.set_yticks([0, 10, 20, 30, 40, 47])

fig.suptitle('Phase 2 — Traffic Tensor & Congestion Profiles\n'
             'DVRPTW-TA: 48 nodes × 12 intervals × 3 parameters = 82,944 entries',
             fontsize=13, fontweight='bold')

output_path = OUTPUT_DIR / 'phase2_traffic_profile.png'
fig.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
plt.close(fig)
print(f"Saved: {output_path}")
print("\nPhase 2 complete.")
