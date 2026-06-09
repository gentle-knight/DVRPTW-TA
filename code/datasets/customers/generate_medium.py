#!/usr/bin/env python3
"""
Generate medium-difficulty instance using same OSM nodes as easy instance.

Reuses node_id, lon, lat from customers_47.csv.
Reassigns: tighter 1.5h time windows, higher demand (420-450 kg total).

Output: datasets/customers/customers_47_medium.csv
"""

import os, sys
from pathlib import Path
import numpy as np
import pandas as pd

np.random.seed(2025)

DATA_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = DATA_DIR

easy_path = OUTPUT_DIR / 'customers_47.csv'
df = pd.read_csv(easy_path)

n_customers = len(df) - 1

demands = np.random.uniform(8, 14, n_customers).round(1)
total = demands.sum()
scale = 435.0 / total
demands = (demands * scale).round(1)
total = demands.sum()

service_times = np.full(n_customers, 4.0)

tw_order = np.random.permutation(n_customers)
n_per_group = n_customers // 3
leftover = n_customers - 3 * n_per_group

tw_groups = []
for i in range(n_customers):
    g = i % 3
    if g == 0:
        tw_groups.append(('09:00', '10:30', 'morning'))
    elif g == 1:
        tw_groups.append(('13:00', '14:30', 'afternoon'))
    else:
        tw_groups.append(('17:00', '18:30', 'evening'))

df_medium = df.copy()
for i, row in df.iterrows():
    cid = int(row['id'])
    if cid == 0:
        continue
    idx = tw_order[cid - 1] if cid <= len(tw_order) else cid - 1
    tw = tw_groups[cid - 1]
    df_medium.at[i, 'demand_kg'] = demands[cid - 1]
    df_medium.at[i, 'window_start'] = tw[0]
    df_medium.at[i, 'window_end'] = tw[1]
    df_medium.at[i, 'tw_group'] = tw[2]

output_path = OUTPUT_DIR / 'customers_47_medium.csv'
df_medium.to_csv(output_path, index=False)

print(f'Medium instance generated:')
print(f'  OSM nodes: same as easy (48 nodes)')
print(f'  Total demand: {total:.1f} kg / 480 kg ({100*total/480:.1f}%)')
print(f'  Demand range: [{demands.min():.1f}, {demands.max():.1f}] kg')
print(f'  Time windows: 09:00-10:30, 13:00-14:30, 17:00-18:30 (1.5h each)')
print(f'  TW distribution:')
for g in ['morning', 'afternoon', 'evening']:
    count = sum(1 for tw in tw_groups if tw[2] == g)
    sub_demand = sum(demands[i] for i in range(n_customers) if tw_groups[i][2] == g)
    print(f'    {g}: {count} customers, {sub_demand:.1f} kg')
print(f'Saved: {output_path}')
