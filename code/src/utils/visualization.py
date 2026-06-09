"""
Reusable visualization utilities for T-ALNS-RRD road network and routing plots.
All functions use Agg backend — suitable for headless rendering to files.
"""

import pickle
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
from matplotlib.collections import LineCollection
import numpy as np

# ── Color palettes ──

ROAD_COLORS = {
    'motorway':      '#c62828', 'motorway_link': '#d32f2f',
    'trunk':         '#d84315', 'trunk_link':    '#e64a19',
    'primary':       '#e65100', 'primary_link':  '#ef6c00',
    'secondary':     '#f57c00', 'secondary_link':'#fb8c00',
    'tertiary':      '#689f38', 'tertiary_link': '#7cb342',
    'residential':   '#455a64',
    'living_street': '#78909c',
    'unclassified':  '#90a4ae',
    'service':       '#b0bec5',
}

ROAD_LINEWIDTH = {
    'motorway': 1.5, 'motorway_link': 1.2, 'trunk': 1.3, 'trunk_link': 1.0,
    'primary': 1.0, 'primary_link': 0.8, 'secondary': 0.7, 'secondary_link': 0.6,
    'tertiary': 0.5, 'tertiary_link': 0.5,
    'residential': 0.4, 'living_street': 0.3,
    'unclassified': 0.3, 'service': 0.25,
}

ROAD_ALPHA = {
    'motorway': 0.9, 'motorway_link': 0.8, 'trunk': 0.85, 'trunk_link': 0.75,
    'primary': 0.75, 'primary_link': 0.7, 'secondary': 0.65, 'secondary_link': 0.6,
    'tertiary': 0.55, 'tertiary_link': 0.5,
    'residential': 0.4, 'living_street': 0.35,
    'unclassified': 0.3, 'service': 0.25,
}

TW_COLORS = {'morning': '#2196F3', 'afternoon': '#FF9800', 'evening': '#9C27B0'}
TW_LABELS = {'morning': 'Morning (9:00–12:00)', 'afternoon': 'Afternoon (13:00–16:00)', 'evening': 'Evening (17:00–20:00)'}

DEPOT_COLOR = '#d32f2f'
BACKGROUND_COLOR = '#fafafa'
FRAME_COLOR = '#dddddd'


def load_graph(graph_path):
    with open(graph_path, 'rb') as f:
        return pickle.load(f)


def _get_hwy(data):
    hwy = data.get('highway', 'unclassified')
    if isinstance(hwy, list):
        hwy = hwy[0]
    return hwy if hwy in ROAD_COLORS else 'unclassified'


def draw_road_network(ax, G, show_all=True):
    """
    Draw road network on given axes.
    Uses LineCollection for performance (all roads in one go).
    """
    pos = {n: (data['x'], data['y']) for n, data in G.nodes(data=True)}

    edge_pairs = defaultdict(list)
    for u, v, k, data in G.edges(keys=True, data=True):
        edge_pairs[(u, v)].append((k, data))

    segments_by_type = defaultdict(list)
    for (u, v), edges in edge_pairs.items():
        k, data = edges[0]
        hwy = _get_hwy(data)
        segments_by_type[hwy].append([(pos[u][0], pos[u][1]), (pos[v][0], pos[v][1])])

    # Draw from minor to major roads (z-order)
    draw_order = [
        'service', 'unclassified', 'living_street', 'residential',
        'tertiary_link', 'tertiary',
        'secondary_link', 'secondary',
        'primary_link', 'primary',
        'trunk_link', 'trunk',
        'motorway_link', 'motorway',
    ]

    for hwy in draw_order:
        segs = segments_by_type.get(hwy, [])
        if not segs:
            continue
        lc = LineCollection(segs, colors=ROAD_COLORS[hwy],
                           linewidths=ROAD_LINEWIDTH[hwy],
                           alpha=ROAD_ALPHA[hwy],
                           capstyle='round', joinstyle='round', zorder=1)
        ax.add_collection(lc)

    return pos


def draw_road_legend(ax):
    entries = [
        ('Motorway / Trunk', '#c62828', 1.3),
        ('Primary', '#e65100', 0.9),
        ('Secondary', '#f57c00', 0.7),
        ('Tertiary / Collector', '#689f38', 0.5),
        ('Residential', '#455a64', 0.4),
    ]
    handles = [Line2D([0],[0],color=c,lw=w,label=label) for label,c,w in entries]
    legend = ax.legend(handles=handles, loc='lower left', fontsize=7,
                       framealpha=0.85, title='Road Type', title_fontsize=8)
    return legend


def draw_customers(ax, customers_df):
    for tw_group in ['morning', 'afternoon', 'evening']:
        mask = customers_df['tw_group'] == tw_group
        subset = customers_df[mask]
        ax.scatter(subset['lon'], subset['lat'],
                   c=TW_COLORS[tw_group], s=70, edgecolors='white',
                   linewidths=0.6, zorder=4, label=TW_LABELS[tw_group],
                   alpha=0.9)

    ax.legend(loc='upper right', fontsize=7, framealpha=0.85,
              title='Time Window', title_fontsize=8)


def draw_depot(ax, depot_row):
    ax.scatter(depot_row['lon'], depot_row['lat'],
               c=DEPOT_COLOR, s=300, marker='s',
               edgecolors='#333333', linewidths=1.5, zorder=5, label='Depot')


def draw_density_contours(ax, kernels, nodes_lon, nodes_lat):
    x_grid = np.linspace(nodes_lon.min(), nodes_lon.max(), 120)
    y_grid = np.linspace(nodes_lat.min(), nodes_lat.max(), 120)
    X, Y = np.meshgrid(x_grid, y_grid)
    Z = np.zeros_like(X)
    for k in kernels:
        dx = (X - k['center'][0]) / k['sigma'][0]
        dy = (Y - k['center'][1]) / k['sigma'][1]
        Z += k['weight'] * np.exp(-0.5 * (dx**2 + dy**2))

    levels = [np.percentile(Z[Z > Z.max()*0.01], p) for p in [30, 55, 80]]
    cs = ax.contour(X, Y, Z, levels=levels, colors='#333333',
                     linewidths=0.6, alpha=0.35, zorder=2, linestyles='dashed')
    return cs


def draw_statistics_panel(ax, stats):
    ax.axis('off')
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    y = 0.97
    for label, value in stats:
        is_header = isinstance(value, str) and value == ''
        if is_header or (isinstance(label, str) and label.isupper()):
            ax.text(0.06, y, label, fontsize=10, fontweight='bold',
                    fontfamily='monospace', color='#222222', va='top')
            y -= 0.04
        else:
            ax.text(0.06, y, f'{label:30s} {value}', fontsize=9,
                    fontfamily='monospace', color='#444444', va='top')
            y -= 0.028

        if y < 0.02:
            break


def set_map_bounds(ax, G):
    bbox = G.graph.get('bbox')
    if bbox:
        margin = 0.002
        ax.set_xlim(bbox[1] - margin, bbox[3] + margin)
        ax.set_ylim(bbox[0] - margin, bbox[2] + margin)


def finalize_map(ax, title, G):
    ax.set_title(title, fontsize=12, fontweight='bold', pad=10)
    ax.set_xlabel('Longitude', fontsize=9)
    ax.set_ylabel('Latitude', fontsize=9)
    ax.set_aspect('equal')
    ax.set_facecolor(BACKGROUND_COLOR)
    for spine in ax.spines.values():
        spine.set_color(FRAME_COLOR)
        spine.set_linewidth(0.5)


def draw_sample_labels(ax, customers_df, max_labels=12):
    step = max(1, len(customers_df) // max_labels)
    for idx in range(1, len(customers_df), step):
        row = customers_df.iloc[idx]
        ax.annotate(str(int(row['id'])),
                    (row['lon'], row['lat']),
                    textcoords="offset points", xytext=(6, 4),
                    fontsize=6, color='#444444', alpha=0.7, zorder=6)
