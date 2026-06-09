"""
Regenerate customer demands to sum exactly 480 kg (full fleet capacity).
Keeps all other attributes (node positions, time windows) unchanged.
"""
import pandas as pd
import numpy as np

np.random.seed(42)

df = pd.read_csv(
    '/Users/huangfuqixun/workspace/课程汇报/企业资源管理/code/datasets/customers/customers_47.csv'
)

customers = df[df['tw_group'] != 'depot'].copy()

target_total = 480.0
n = len(customers)

# Generate demands biased high: uniform(7, 12) then scale to exact total
raw = np.random.uniform(7.0, 12.0, n)
raw = raw / raw.sum() * target_total
demands = np.round(raw, 1)

# Fix any out-of-range values by redistributing excess
for _ in range(20):
    overflow = 0.0
    for i in range(n):
        if demands[i] > 12.0:
            overflow += demands[i] - 12.0
            demands[i] = 12.0
        elif demands[i] < 3.0:
            deficit = 3.0 - demands[i]
            demands[i] = 3.0
            overflow -= deficit
    if abs(overflow) < 0.1:
        break
    # Redistribute overflow to non-boundary values
    free_idx = [i for i in range(n) if 3.0 < demands[i] < 12.0]
    if free_idx:
        per = overflow / len(free_idx)
        for i in free_idx:
            demands[i] += per
        demands = np.round(demands, 1)

# Fix rounding error in final sum
diff = target_total - demands.sum()
if abs(diff) > 0.01:
    i = 0
    step = 0.1 if diff > 0 else -0.1
    while abs(demands.sum() - target_total) > 0.05:
        if 3.0 <= demands[i] + step <= 12.0:
            demands[i] = round(demands[i] + step, 1)
        i = (i + 1) % n

df.loc[customers.index, 'demand_kg'] = demands

df.to_csv(
    '/Users/huangfuqixun/workspace/课程汇报/企业资源管理/code/datasets/customers/customers_47.csv',
    index=False
)

total = df[df['tw_group'] != 'depot']['demand_kg'].sum()
print(f"Updated demands: total = {total:.1f} kg ({100*total/480:.1f}% of fleet capacity)")
print(f"  Range: [{demands.min():.1f}, {demands.max():.1f}] kg")
print(f"  Mean: {demands.mean():.1f}, Std: {demands.std():.1f}")

for g in ['morning', 'afternoon', 'evening']:
    sub = customers[customers['tw_group'] == g]
    print(f"  {g}: {len(sub)} customers, {sub['demand_kg'].sum():.1f} kg")
