#!/usr/bin/env python3
"""Generate medium-difficulty instance. Usage: python generate_medium_instance.py"""

import argparse
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EASY_PATH = PROJECT_ROOT / 'datasets' / 'customers' / 'customers_47.csv'
MEDIUM_PATH = PROJECT_ROOT / 'datasets' / 'customers' / 'customers_47_medium.csv'

TW_CONFIG = [('09:00','10:30','morning'), ('12:30','14:00','midday'), ('16:00','17:30','evening')]
TW_COUNTS = [16, 16, 15]

def _to_min(hhmm):
    h, m = map(int, hhmm.split(':'))
    return (h - 6) * 60 + m

def generate(target_total=435, seed=42):
    np.random.seed(seed)
    df = pd.read_csv(EASY_PATH)

    tw_cust = []
    for i, count in enumerate(TW_COUNTS):
        tw_cust.extend([TW_CONFIG[i]] * count)
    tw_cust = tw_cust[:47]
    rng = np.random.RandomState(seed)
    rng.shuffle(tw_cust)

    for attempt in range(50):
        rng2 = np.random.RandomState(seed + attempt * 1000)
        d_raw = rng2.uniform(6, 13, 47)
        d = np.clip(d_raw * target_total / d_raw.sum(), 5, 14).round(1)
        total = d.sum()
        if 420 <= total <= 450:
            break

    rows = []
    for i in range(48):
        row = df.iloc[i]
        if i == 0:
            rows.append([0, row['node_id'], row['lon'], row['lat'], 0.0, 0, '', '', 'depot'])
        else:
            start, end, group = tw_cust[i-1]
            rows.append([i, row['node_id'], row['lon'], row['lat'],
                        float(d[i-1]), 4, start, end, group])

    result = pd.DataFrame(rows, columns=['id','node_id','lon','lat','demand_kg',
                                          'service_min','window_start','window_end','tw_group'])
    result.to_csv(MEDIUM_PATH, index=False)

    print(f"Medium instance: {MEDIUM_PATH}")
    print(f"  Demand: {total:.1f} kg / 480 ({100*total/480:.1f}%)")
    print(f"  Range: [{d.min():.1f}, {d.max():.1f}] kg")
    g = {'morning':0,'midday':0,'evening':0}
    for _,_,grp in tw_cust: g[grp] += 1
    print(f"  TW: morning={g['morning']} midday={g['midday']} evening={g['evening']}")
    for _, r in result.iterrows():
        if r['id'] == 0: continue
        if _to_min(r['window_start']) < 0 or _to_min(r['window_end']) > 720:
            print(f"  WARN: customer {r['id']} TW out of range"); break
    else:
        print("  All TW in [06:00-18:00]: OK")
    return result

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--target-total', type=float, default=435)
    p.add_argument('--seed', type=int, default=42)
    a = p.parse_args()
    generate(a.target_total, a.seed)
