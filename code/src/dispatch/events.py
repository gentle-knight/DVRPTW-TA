"""
Event types and injection for synchronous RRD (Sect 3.3.3, Eq.34).

Defines E1/E2/E4 event types. In the synchronous version, events are
injected at predetermined iterations rather than detected in real-time.

E1_TRAFFIC: road blockage on a random arc → travel time ×3
E2_URGENT: new customer with tight time window must be inserted
E4_TIME_RISK: existing customer at risk of missing its time window
"""

from enum import Enum
import numpy as np
from core.solution import N_DEPOT


class EventType(Enum):
    E1_TRAFFIC = 1
    E2_URGENT = 2
    E4_TIME_RISK = 4


def inject_traffic_incident(solution, traffic, demands, service_times,
                            windows_open, windows_close, lambda_1, lambda_2, rng):
    routes_with_customers = [
        (v, route) for v, route in enumerate(solution.routes)
        if len(route.customer_nodes()) >= 2
    ]
    if not routes_with_customers:
        return None

    v, route = routes_with_customers[rng.randint(0, len(routes_with_customers))]
    customers = route.customer_nodes()
    pos = rng.randint(0, len(customers) - 1)
    cust_a = customers[pos]
    cust_b = customers[pos + 1]

    orig_time = traffic.travel_time(cust_a, cust_b, 0)
    blocked_time = orig_time * 3.0

    return {
        'type': EventType.E1_TRAFFIC,
        'description': f'traffic blockage on arc ({cust_a}→{cust_b})',
        'vehicle': v,
        'arc': (cust_a, cust_b),
        'original_travel_time': orig_time,
        'blocked_travel_time': blocked_time,
        'affected_customer': cust_b,
    }


def inject_urgent_order(traffic, demands, service_times,
                        windows_open, windows_close, rng):
    max_id = len(demands) - 1
    new_id = max_id + 1

    urgency = rng.uniform(0.15, 0.35)
    arrival_limit = 360.0

    tw_open = arrival_limit * urgency
    tw_close = arrival_limit * (urgency + rng.uniform(0.3, 0.6))
    tw_close = min(tw_close, 720.0)
    demand = rng.uniform(3, 8)

    return {
        'type': EventType.E2_URGENT,
        'description': f'urgent order: customer {new_id} with TW [{tw_open:.0f},{tw_close:.0f}]',
        'new_id': new_id,
        'demand': demand,
        'service_time': 4.0,
        'tw_open': tw_open,
        'tw_close': tw_close,
    }


def inject_time_window_risk(solution, traffic, demands, service_times,
                            windows_open, windows_close, lambda_1, lambda_2, rng):
    risk_threshold = 15.0

    at_risk = []
    for v, route in enumerate(solution.routes):
        custs = route.customer_nodes()
        nodes_full = route.nodes
        T = route.departure_time
        prev = nodes_full[0]

        cust_idx = 0
        for nid in nodes_full[1:]:
            if nid == N_DEPOT:
                break
            tt = traffic.travel_time(prev, nid, T)
            A = T + tt
            S = max(A, windows_open[nid])
            slack = windows_close[nid] - S
            if 0 < slack < risk_threshold:
                at_risk.append({
                    'vehicle': v,
                    'customer': nid,
                    'slack_minutes': slack,
                    'arrival': A,
                    'tw_close': windows_close[nid],
                    'position': cust_idx,
                })
            T = S + service_times[nid]
            prev = nid
            cust_idx += 1

    if not at_risk:
        return None

    ranked = sorted(at_risk, key=lambda x: x['slack_minutes'])
    event = ranked[0]

    return {
        'type': EventType.E4_TIME_RISK,
        'description': f'time-window risk: customer {event["customer"]} slack={event["slack_minutes"]:.1f}min',
        'vehicle': event['vehicle'],
        'customer': event['customer'],
        'slack_minutes': event['slack_minutes'],
    }
