"""
Diversification intensity control (Sect 3.3.2, Eqs.26–27).

δ(t) = ω₁·(t−t_last_best)/T_max + ω₂·|T_move|/|T_move|_max + ω₃·σ(F_cv)

When δ(t) > δ_max, shifts operator selection toward diversification-biased
probabilities to escape local optima and explore underrepresented regions.
"""

import numpy as np


def compute_intensity(it, last_best_iter, max_iter, move_tabu_size, move_tabu_max,
                      frequency_std, omega_1=0.4, omega_2=0.3, omega_3=0.3):
    stagnation = (it - last_best_iter) / max(max_iter, 1)
    tabu_ratio = move_tabu_size / max(move_tabu_max, 1)
    freq_term = frequency_std
    return omega_1 * stagnation + omega_2 * tabu_ratio + omega_3 * freq_term


def adjust_probabilities(weights, diversity_scores, eta=0.6):
    n = len(weights)
    weight_sum = sum(weights.values())
    div_sum = sum(diversity_scores.values())
    if div_sum < 1e-8:
        div_probs = np.ones(n) / n
    else:
        div_probs = np.array([diversity_scores[n] / div_sum for n in weights.keys()])

    p = np.array([weights[n] / weight_sum for n in weights.keys()])
    adjusted = eta * p + (1.0 - eta) * div_probs
    adjusted /= adjusted.sum()
    return {name: float(adjusted[i]) for i, name in enumerate(weights.keys())}


def compute_diversity_scores(frequency, n_vehicles, operator_names):
    cv_total = 0.0
    for cid in range(1, frequency.n_customers + 1):
        for v in range(n_vehicles):
            cv_total += frequency.diversification_score(cid, v)

    base = 1.0 + 0.01 * cv_total

    operator_traits = {
        'random':  1.20,
        'worst':   0.85,
        'related': 1.10,
        'greedy':  0.90,
        'regret2': 1.05,
        'tw_aware': 1.15,
    }

    scores = {}
    for name in operator_names:
        trait = operator_traits.get(name, 1.0)
        scores[name] = base * trait
    return scores
