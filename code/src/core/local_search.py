"""
Lightweight final intensification for ALNS-family solutions.

The operators are deliberately conservative: relocate one customer or swap two
customers when the move strictly improves the same traffic-aware objective used
everywhere else.
"""

from .solution import N_DEPOT


def _solution_cost(solution, traffic, demands, service_times, windows_open,
                   windows_close, lambda_1, lambda_2):
    return solution.compute_cost(
        traffic, demands, service_times, windows_open, windows_close,
        lambda_1=lambda_1, lambda_2=lambda_2)


def _set_route_customers(route, customers):
    route.nodes = [N_DEPOT] + list(customers) + [N_DEPOT]


def _is_valid(solution, demands, capacity):
    return solution.is_valid(demands, capacity=capacity, n_customers=len(demands) - 1)


def polish_solution(solution, traffic, demands, service_times, windows_open,
                    windows_close, lambda_1=1.0, lambda_2=0.5,
                    capacity=120.0, max_passes=2, min_improvement=1e-6):
    """Apply relocate/swap improvements until a small pass limit is reached."""
    best = solution.copy()
    best_cost, best_detail = _solution_cost(
        best, traffic, demands, service_times, windows_open, windows_close,
        lambda_1, lambda_2)
    improvements = 0

    for _ in range(max_passes):
        improved = False
        candidate_best = None
        candidate_cost = best_cost
        candidate_detail = best_detail

        # Relocate one customer to another route/position.
        for src_idx, src_route in enumerate(best.routes):
            src_customers = src_route.customer_nodes()
            for src_pos, customer in enumerate(src_customers):
                for dst_idx, dst_route in enumerate(best.routes):
                    dst_customers = dst_route.customer_nodes()
                    for dst_pos in range(len(dst_customers) + 1):
                        if src_idx == dst_idx and (dst_pos == src_pos or dst_pos == src_pos + 1):
                            continue

                        trial = best.copy()
                        trial_src = trial.routes[src_idx].customer_nodes()
                        moved = trial_src.pop(src_pos)
                        _set_route_customers(trial.routes[src_idx], trial_src)

                        trial_dst = trial.routes[dst_idx].customer_nodes()
                        insert_pos = dst_pos
                        if src_idx == dst_idx and dst_pos > src_pos:
                            insert_pos -= 1
                        trial_dst.insert(insert_pos, moved)
                        _set_route_customers(trial.routes[dst_idx], trial_dst)

                        if not _is_valid(trial, demands, capacity):
                            continue
                        cost, detail = _solution_cost(
                            trial, traffic, demands, service_times,
                            windows_open, windows_close, lambda_1, lambda_2)
                        if cost + min_improvement < candidate_cost:
                            candidate_best = trial
                            candidate_cost = cost
                            candidate_detail = detail

        # Swap two customers.
        route_count = len(best.routes)
        for a_idx in range(route_count):
            a_customers = best.routes[a_idx].customer_nodes()
            for a_pos in range(len(a_customers)):
                for b_idx in range(a_idx, route_count):
                    b_customers = best.routes[b_idx].customer_nodes()
                    start_b = a_pos + 1 if a_idx == b_idx else 0
                    for b_pos in range(start_b, len(b_customers)):
                        trial = best.copy()
                        if a_idx == b_idx:
                            trial_customers = trial.routes[a_idx].customer_nodes()
                            trial_customers[a_pos], trial_customers[b_pos] = (
                                trial_customers[b_pos], trial_customers[a_pos])
                            _set_route_customers(trial.routes[a_idx], trial_customers)
                        else:
                            trial_a = trial.routes[a_idx].customer_nodes()
                            trial_b = trial.routes[b_idx].customer_nodes()
                            trial_a[a_pos], trial_b[b_pos] = trial_b[b_pos], trial_a[a_pos]
                            _set_route_customers(trial.routes[a_idx], trial_a)
                            _set_route_customers(trial.routes[b_idx], trial_b)

                        if not _is_valid(trial, demands, capacity):
                            continue
                        cost, detail = _solution_cost(
                            trial, traffic, demands, service_times,
                            windows_open, windows_close, lambda_1, lambda_2)
                        if cost + min_improvement < candidate_cost:
                            candidate_best = trial
                            candidate_cost = cost
                            candidate_detail = detail

        if candidate_best is None:
            break

        best = candidate_best
        best_cost = candidate_cost
        best_detail = candidate_detail
        improvements += 1
        improved = True
        if not improved:
            break

    return best, best_cost, best_detail, improvements
