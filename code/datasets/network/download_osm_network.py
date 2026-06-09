#!/usr/bin/env python3
"""
Download Shanghai Jing'an-Huangpu OSM road network for T-ALNS-RRD reproduction.

Paper description:
  - Study area: 8×10 km² centered on Jing'an and Huangpu districts
  - Road network extracted from OpenStreetMap
  - Nodes: 48 (47 customers + 1 depot), Arcs: 2,256 directed
  - Road types: arterial (18%), collector (34%), residential (41%), service (7%)

Jing'an district center: 31.228, 121.455
Huangpu district center: 31.230, 121.475
Midpoint: 31.229, 121.465

Bounding box for ~8×10 km² (roughly 0.072° lat × 0.09° lon at Shanghai latitude):
  North: 31.265, South: 31.193, East: 121.510, West: 121.420
"""
import os
import sys
import pickle
import warnings

import osmnx as ox
import networkx as nx

warnings.filterwarnings('ignore')
ox.settings.log_console = False
ox.settings.use_cache = True

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(OUTPUT_DIR)

# Shanghai Jing'an-Huangpu bounding box (~8×10 km²)
NORTH, SOUTH = 31.265, 31.193
EAST, WEST = 121.510, 121.420

def main():
    print("Downloading OSM road network for Shanghai Jing'an-Huangpu area...")
    print(f"Bounding box: N={NORTH}, S={SOUTH}, E={EAST}, W={WEST}")

    G = ox.graph_from_bbox(
        bbox=(WEST, SOUTH, EAST, NORTH),
        network_type='drive',
        simplify=True,
        retain_all=False,
    )

    print(f"\nDownloaded graph: {G}")
    print(f"Nodes: {len(G.nodes)}, Edges: {len(G.edges)}")

    G_proj = ox.project_graph(G)
    stats = ox.stats.basic_stats(G_proj)
    print(f"\nProjected graph stats:")
    print(f"  Total road length: {stats.get('street_length_total', 'N/A') / 1000:.1f} km")
    print(f"  Average edge length: {stats.get('street_length_avg', 'N/A'):.1f} m")

    road_types = {}
    total_edges = len(G.edges)
    for u, v, k, data in G.edges(keys=True, data=True):
        hwy = data.get('highway', 'unclassified')
        if isinstance(hwy, list):
            hwy = hwy[0]
        road_types[hwy] = road_types.get(hwy, 0) + 1

    arterial = sum(road_types.get(t, 0) for t in
                   ('motorway', 'motorway_link', 'trunk', 'trunk_link', 'primary', 'primary_link'))
    collector = sum(road_types.get(t, 0) for t in
                    ('secondary', 'secondary_link', 'tertiary', 'tertiary_link'))
    residential = sum(road_types.get(t, 0) for t in
                      ('residential', 'living_street'))
    service = sum(road_types.get(t, 0) for t in
                  ('unclassified', 'service'))

    print(f"\n  Road classification (paper: arterial 18%, collector 34%, residential 41%, service 7%):")
    print(f"    arterial:    {arterial} edges ({100*arterial/total_edges:.1f}%)")
    print(f"    collector:   {collector} edges ({100*collector/total_edges:.1f}%)")
    print(f"    residential: {residential} edges ({100*residential/total_edges:.1f}%)")
    print(f"    service:     {service} edges ({100*service/total_edges:.1f}%)")

    for hwy, count in sorted(road_types.items(), key=lambda x: -x[1]):
        print(f"    [raw] {hwy}: {count} edges ({100*count/total_edges:.1f}%)")

    graph_path = os.path.join(DATA_DIR, 'shanghai_road_graph.pkl')
    with open(graph_path, 'wb') as f:
        pickle.dump(G, f)
    print(f"\nSaved graph to: {graph_path}")
    print(f"File size: {os.path.getsize(graph_path) / 1024:.1f} KB")

    gdf_nodes, gdf_edges = ox.graph_to_gdfs(G)
    nodes_csv = os.path.join(DATA_DIR, 'shanghai_nodes.csv')
    edges_csv = os.path.join(DATA_DIR, 'shanghai_edges.csv')
    gdf_nodes[['y', 'x', 'highway']].to_csv(nodes_csv)
    gdf_edges.reset_index()[['u', 'v', 'length', 'highway', 'name', 'maxspeed']].to_csv(edges_csv)
    print(f"Exported nodes to: {nodes_csv}")
    print(f"Exported edges to: {edges_csv}")

    return G

if __name__ == '__main__':
    G = main()
