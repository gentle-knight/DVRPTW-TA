"""
Solution representation and cost evaluation (Sect 3.3.1, Eqs. 1–6, 12–13).

Route: ordered list of nodes [0, c₁, ..., cₖ, 0] with forward time propagation.
Solution: collection of Routes, composite objective f(S) = travel + λ₂·ρ + λ₁·δ.
"""

from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]

N_DEPOT = 0
DEPOT_OPEN = 0
DEPOT_CLOSE = 720


def _to_minutes(hhmm_str):
    h, m = map(int, hhmm_str.split(':'))
    return (h - 6) * 60 + m


def load_customer_data(csv_path=None):
    if csv_path is None:
        csv_path = PROJECT_ROOT / 'datasets' / 'customers' / 'customers_47.csv'
    df = pd.read_csv(csv_path)

    n = len(df) - 1
    demands = np.zeros(n + 1, dtype=np.float32)
    service_times = np.zeros(n + 1, dtype=np.float32)
    windows_open = np.zeros(n + 1, dtype=np.float32)
    windows_close = np.zeros(n + 1, dtype=np.float32)

    windows_open[N_DEPOT] = DEPOT_OPEN
    windows_close[N_DEPOT] = DEPOT_CLOSE

    for _, row in df.iterrows():
        cid = int(row['id'])
        if cid == N_DEPOT:
            continue
        demands[cid] = float(row['demand_kg'])
        service_times[cid] = float(row['service_min'])
        windows_open[cid] = _to_minutes(str(row['window_start']))
        windows_close[cid] = _to_minutes(str(row['window_end']))

    return demands, service_times, windows_open, windows_close


class Route:

    def __init__(self, nodes=None):
        self.nodes = list(nodes) if nodes else [N_DEPOT, N_DEPOT]
        self.departure_time = DEPOT_OPEN

    def copy(self):
        r = Route()
        r.nodes = list(self.nodes)
        r.departure_time = self.departure_time
        return r

    def total_demand(self, demands):
        return sum(demands[n] for n in self.nodes if n != N_DEPOT)

    def is_feasible(self, demands, capacity, windows_open, windows_close):
        if self.total_demand(demands) > capacity:
            return False
        for n in self.nodes:
            if n == N_DEPOT:
                continue
            if windows_open[n] > DEPOT_CLOSE or windows_close[n] < DEPOT_OPEN:
                return False
        return True

    def forward_propagate(self, traffic, demands, service_times, windows_open, windows_close,
                          use_reliability_margin=True):
        arrivals = []
        starts = []
        departures = []
        latenesses = []
        travel_costs = []
        congestion_costs = []

        T = self.departure_time
        prev = self.nodes[0]

        for idx in range(1, len(self.nodes)):
            cur = self.nodes[idx]
            if use_reliability_margin:
                tt = traffic.adjusted_time(prev, cur, T)
            else:
                tt = traffic.travel_time(prev, cur, T)
            cc = traffic.congestion_cost(prev, cur, T)

            if idx == len(self.nodes) - 1 and cur == N_DEPOT:
                T = T + tt
                arrivals.append(T)
                starts.append(T)
                departures.append(T)
                latenesses.append(0.0)
                travel_costs.append(tt)
                congestion_costs.append(cc)
                break

            A = T + tt
            S = max(A, windows_open[cur])
            delta = max(0.0, S - windows_close[cur])
            T_next = S + service_times[cur]

            arrivals.append(A)
            starts.append(S)
            departures.append(T_next)
            latenesses.append(delta)
            travel_costs.append(tt)
            congestion_costs.append(cc)

            T = T_next
            prev = cur

        return {
            'arrivals': arrivals,
            'starts': starts,
            'departures': departures,
            'latenesses': latenesses,
            'travel_cost': sum(travel_costs),
            'congestion_cost': sum(congestion_costs),
            'lateness_penalty': sum(latenesses),
        }

    def compute_cost(self, traffic, demands, service_times, windows_open, windows_close,
                     lambda_1=1.0, lambda_2=0.5, use_reliability_margin=True):
        result = self.forward_propagate(
            traffic, demands, service_times, windows_open, windows_close,
            use_reliability_margin=use_reliability_margin
        )
        return (result['travel_cost']
                + lambda_2 * result['congestion_cost']
                + lambda_1 * result['lateness_penalty']), result

    def customer_nodes(self):
        return [n for n in self.nodes if n != N_DEPOT]

    def __repr__(self):
        return f"Route({'→'.join(map(str, self.nodes))})"


class Solution:

    def __init__(self, routes=None, n_vehicles=4):
        self.routes = routes if routes else [Route() for _ in range(n_vehicles)]

    def copy(self):
        return Solution([r.copy() for r in self.routes])

    def all_customers(self):
        custs = []
        for r in self.routes:
            custs.extend(r.customer_nodes())
        return custs

    def served_customer_set(self):
        return set(self.all_customers())

    def compute_cost(self, traffic, demands, service_times, windows_open, windows_close,
                     lambda_1=1.0, lambda_2=0.5, use_reliability_margin=True):
        travel = 0.0
        congestion = 0.0
        lateness = 0.0
        details = []
        for r in self.routes:
            cost, result = r.compute_cost(
                traffic, demands, service_times, windows_open, windows_close,
                lambda_1, lambda_2,
                use_reliability_margin=use_reliability_margin)
            travel += result['travel_cost']
            congestion += result['congestion_cost']
            lateness += result['lateness_penalty']
            details.append(result)

        total = travel + lambda_2 * congestion + lambda_1 * lateness
        return total, {
            'travel_cost': travel,
            'congestion_cost': congestion,
            'lateness_penalty': lateness,
            'total': total,
            'route_details': details,
        }

    def is_valid(self, demands, capacity, n_customers=None):
        all_seen = set()
        for r in self.routes:
            for n in r.customer_nodes():
                if n in all_seen:
                    return False
                all_seen.add(n)
            if r.total_demand(demands) > capacity:
                return False
        if n_customers is not None:
            expected = set(range(1, n_customers + 1))
            if all_seen != expected:
                return False
        return True

    def __repr__(self):
        parts = []
        for i, r in enumerate(self.routes):
            parts.append(f"  V{i+1}: {r.customer_nodes()}")
        return "Solution:\n" + "\n".join(parts)
