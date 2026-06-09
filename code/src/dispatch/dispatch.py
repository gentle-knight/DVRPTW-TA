"""
Dispatch decision module (Sect 3.3.3, Eqs.38–41).

Evaluates all candidate actions, computes adjusted score:
  score = rollout_cost + stability_penalty + recovery_penalty + tabu_penalty
Selects argmin score. Returns best action and dispatch result.
"""

import time
import numpy as np
from .rollout import evaluate_candidate


def dispatch_action(event, candidates, original_solution, traffic, demands,
                    service_times, windows_open, windows_close,
                    lambda_1, lambda_2, horizon_minutes=60,
                    move_tabu=None, sol_tabu=None, current_iter=0):
    t_start = time.time()

    best_score = float('inf')
    best_idx = -1
    best_details = None

    for idx, candidate in enumerate(candidates):
        blocked_arc = event.get('arc') if event['type'].name == 'E1_TRAFFIC' else None

        tabu_penalty = 0.0
        if sol_tabu and sol_tabu.is_tabu(candidate['solution'], current_iter):
            tabu_penalty += 50.0

        score, rc, sp, rp = evaluate_candidate(
            candidate, original_solution, traffic, demands, service_times,
            windows_open, windows_close, lambda_1, lambda_2,
            horizon_minutes=horizon_minutes,
            blocked_arc=blocked_arc,
            tabu_penalty=tabu_penalty,
        )

        if score < best_score:
            best_score = score
            best_idx = idx
            best_details = {'rollout_cost': rc, 'stability_penalty': sp, 'recovery_penalty': rp,
                           'total_score': score}

    response_time_ms = (time.time() - t_start) * 1000

    if best_idx == -1:
        return None, {'success': False, 'response_time_ms': response_time_ms, 'reason': 'no valid candidates'}

    chosen = candidates[best_idx]
    best_details['success'] = True
    best_details['response_time_ms'] = response_time_ms
    best_details['chosen_action'] = chosen['name']

    return chosen, best_details
