"""
Unified evaluation metrics for all T-ALNS-RRD algorithms (Sect 4.4, Eqs.44-47).

Provides standardized metric computation used by ALNS, T-ALNS, T-ALNS-RRD,
and all baseline solvers. Metrics include:
  total_cost, travel_cost, lateness_penalty, congestion_cost (CES),
  OTDR, average_delay, max_delay, late_customers, time_window_violation_rate.
"""

import numpy as np
from core.solution import N_DEPOT


def compute_metrics(solution, traffic, demands, service_times,
                     windows_open, windows_close, lambda_1=1.0, lambda_2=0.5,
                     use_reliability_margin=True):
    n_customers = len(demands) - 1
    cost, details = solution.compute_cost(
        traffic, demands, service_times, windows_open, windows_close,
        lambda_1=lambda_1, lambda_2=lambda_2,
        use_reliability_margin=use_reliability_margin)

    ontime = 0
    delays = []
    late_count = 0

    for rd, route in zip(details['route_details'], solution.routes):
        customers = route.customer_nodes()
        for i in range(len(customers)):
            lat = rd['latenesses'][i]
            if lat == 0:
                ontime += 1
            else:
                late_count += 1
                delays.append(lat)

    avg_delay = np.mean(delays) if delays else 0.0
    max_delay = np.max(delays) if delays else 0.0

    return {
        'total': cost,
        'travel': details['travel_cost'],
        'lateness': details['lateness_penalty'],
        'congestion': details['congestion_cost'],
        'ces': details['congestion_cost'],
        'otdr': ontime / n_customers * 100,
        'average_delay': avg_delay,
        'max_delay': max_delay,
        'late_customers': late_count,
        'tw_violation_rate': late_count / n_customers * 100,
    }


def metrics_header():
    return [
        'total', 'travel', 'lateness', 'congestion', 'ces',
        'otdr', 'average_delay', 'max_delay', 'late_customers', 'tw_violation_rate',
    ]


def metrics_to_row(metrics):
    return {k: metrics[k] for k in metrics_header()}
