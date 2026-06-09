"""
Aspiration criteria to override Tabu restrictions (Sect 3.3.2, Eqs.28–30).

Three conditions permit tabu moves when they show high potential:
  global_best:   f(S') < f(S*) — new global optimum
  least_freq:    min F_cv < β · mean F_cv — rarely-used assignment
  traffic_adapt: congestion reduction > γ · current — significant traffic gain
"""


def check_aspiration(new_cost, best_cost, solution=None, frequency=None,
                     customer_id=None, vehicle_id=None,
                     beta=0.3, gamma=0.7,
                     new_congestion=None, current_congestion=None):
    if new_cost < best_cost:
        return True, 'global_best'

    if frequency is not None and customer_id is not None and vehicle_id is not None:
        min_freq = frequency.least_frequent_assignment(customer_id)
        mean_freq = frequency.mean_frequency()
        if min_freq < beta * mean_freq:
            return True, 'least_frequency'

    if new_congestion is not None and current_congestion is not None and current_congestion > 0:
        if new_congestion < gamma * current_congestion:
            return True, 'traffic_adaptation'

    return False, None
