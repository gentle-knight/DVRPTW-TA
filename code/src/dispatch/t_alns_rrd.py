"""
T-ALNS-RRD engine — synchronous version (Sect 3.3.3, Algorithm 3).

Wraps T-ALNS with event injection at predetermined iterations:
  - iter=250: E1_TRAFFIC (road blockage)
  - iter=500: E2_URGENT (new order insertion)
  - iter=750: E4_TIME_RISK (time-window at risk)

At each event: pause optimization → generate candidates → dispatch action →
apply to current solution → update Tabu structures → resume optimization.

Tracks dispatch metrics: success rate, response time, delay/congestion reduction,
route change ratio.
"""

import time
import numpy as np
from .events import (
    EventType, inject_traffic_incident, inject_urgent_order, inject_time_window_risk
)
from .candidates import (
    generate_candidates_traffic, generate_candidates_urgent, generate_candidates_time_risk
)
from .dispatch import dispatch_action
from core.solution import Solution, Route, N_DEPOT
from utils.evaluation import compute_metrics
from tabu.frequency import FrequencyMemory


class IncidentTraffic:
    def __init__(self, base_tm, blocked_arc, multiplier=3.0):
        self._tm = base_tm
        self._blocked = blocked_arc
        self._mult = multiplier

    def _is_blocked(self, i, j):
        return self._blocked is not None and (i, j) == self._blocked

    def travel_time(self, i, j, T):
        t = self._tm.travel_time(i, j, T)
        return t * self._mult if self._is_blocked(i, j) else t

    def congestion_cost(self, i, j, T):
        return self._tm.congestion_cost(i, j, T)

    def adjusted_time(self, i, j, T):
        t = self._tm.adjusted_time(i, j, T)
        base = self._tm.travel_time(i, j, T)
        return t + base * (self._mult - 1) if self._is_blocked(i, j) else t

    def free_flow_time(self, i, j):
        return self._tm.free_flow_time(i, j)


def run_t_alns_rrd(traffic, demands, service_times, windows_open, windows_close,
                   max_iter=1000, event_iterations=(250, 500, 750),
                   lambda_1=1.0, lambda_2=0.5,
                   cooling_rate=0.99975, reaction_factor=0.1, segment_size=100,
                   max_attempts=10, seed=42, verbose=True,
                   dispatch_mode='rollout'):
    rng = np.random.RandomState(seed)

    t0 = time.time()
    dispatch_log = []

    current = None
    best = None
    best_cost = float('inf')
    move_tabu = None
    sol_tabu = None
    freq_memory = None
    d_weights = None
    r_weights = None
    T_sa = 0.05 * 300

    destroy_names = ['random', 'worst', 'related']
    repair_names = ['greedy', 'regret2', 'tw_aware']

    iter_events = set(event_iterations)
    event_idx = 0
    it = 0

    while it < max_iter:
        if it in iter_events:
            etype = [EventType.E1_TRAFFIC, EventType.E2_URGENT, EventType.E4_TIME_RISK][event_idx]

            if verbose:
                m_pre = compute_metrics(current, traffic, demands, service_times,
                                        windows_open, windows_close, lambda_1, lambda_2)
                print(f'\nRRD | iter={it:4d} | EVENT {etype.name}: travel={m_pre["travel"]:.1f} '
                      f'late={m_pre["lateness"]:.1f} total={m_pre["total"]:.1f} OTDR={m_pre["otdr"]:.1f}%')

            pre_solution = current.copy()
            eval_tm = traffic
            pre_cost, pre_detail = pre_solution.compute_cost(
                eval_tm, demands, service_times, windows_open, windows_close, lambda_1, lambda_2)

            if etype == EventType.E1_TRAFFIC:
                event = inject_traffic_incident(
                    current, traffic, demands, service_times,
                    windows_open, windows_close, lambda_1, lambda_2, rng)
                if event:
                    candidates = generate_candidates_traffic(
                        event, current, traffic, demands, service_times,
                        windows_open, windows_close, lambda_1, lambda_2, rng)
                    eval_tm = IncidentTraffic(traffic, event['arc'])
                else:
                    eval_tm = traffic
            elif etype == EventType.E2_URGENT:
                event = inject_urgent_order(
                    traffic, demands, service_times, windows_open, windows_close, rng)
                candidates = generate_candidates_urgent(
                    event, current, traffic, demands, service_times,
                    windows_open, windows_close, lambda_1, lambda_2, rng)
                eval_tm = traffic
            else:
                event = inject_time_window_risk(
                    current, traffic, demands, service_times,
                    windows_open, windows_close, lambda_1, lambda_2, rng)
                if event:
                    candidates = generate_candidates_time_risk(
                        event, current, traffic, demands, service_times,
                        windows_open, windows_close, lambda_1, lambda_2, rng)
                else:
                    candidates = []
                eval_tm = traffic

            if event and candidates:
                if dispatch_mode == 'none':
                    dispatch_log.append({
                        'iter': it, 'event_type': etype.name, 'action': 'none',
                        'success': True, 'response_time_ms': 0,
                        'pre_cost': pre_cost, 'post_cost': pre_cost,
                        'delay_reduction': 0, 'congestion_reduction': 0,
                        'route_change_ratio': 0, 'candidates_count': 0,
                    })
                    if verbose:
                        print(f'RRD | ACTION: none (no-dispatch) | cost {pre_cost:.1f}')
                elif dispatch_mode == 'greedy':
                    best_immediate = float('inf')
                    best_greedy_candidate = None
                    for cand in candidates:
                        eff_d = demands
                        eff_st = service_times
                        eff_wo = windows_open
                        eff_wc = windows_close
                        if 'extended_data' in cand:
                            eff_d, eff_st, eff_wo, eff_wc = cand['extended_data']
                        ic, _ = cand['solution'].compute_cost(
                            eval_tm, eff_d, eff_st, eff_wo, eff_wc, lambda_1, lambda_2)
                        if ic < best_immediate:
                            best_immediate = ic
                            best_greedy_candidate = cand
                    if best_greedy_candidate:
                        chosen = best_greedy_candidate
                        current = chosen['solution']
                        result = {'success': True, 'response_time_ms': 0, 'rollout_cost': best_immediate,
                                  'stability_penalty': 0, 'chosen_action': chosen['name']}
                    else:
                        chosen = None
                else:
                    chosen, result = dispatch_action(
                        event, candidates, current, traffic, demands, service_times,
                        windows_open, windows_close, lambda_1, lambda_2,
                        horizon_minutes=60,
                        move_tabu=move_tabu, sol_tabu=sol_tabu, current_iter=it)

                if dispatch_mode != 'none' and chosen and result.get('success'):
                    current = chosen['solution']

                    eff_demands = demands
                    eff_service_times = service_times
                    eff_windows_open = windows_open
                    eff_windows_close = windows_close

                    if 'extended_data' in chosen:
                        eff_demands, eff_service_times, eff_windows_open, eff_windows_close = chosen['extended_data']
                        demands = eff_demands
                        service_times = eff_service_times
                        windows_open = eff_windows_open
                        windows_close = eff_windows_close
                        freq_memory = FrequencyMemory(n_customers=len(demands)-1, n_vehicles=4)

                    post_cost, post_detail = current.compute_cost(
                        eval_tm, eff_demands, eff_service_times, eff_windows_open, eff_windows_close, lambda_1, lambda_2)

                    delay_reduction = pre_detail['lateness_penalty'] - post_detail['lateness_penalty']
                    cong_reduction = pre_detail['congestion_cost'] - post_detail['congestion_cost']

                    route_change = 0.0
                    for r_idx in range(4):
                        pre_set = set(pre_solution.routes[r_idx].customer_nodes())
                        post_set = set(current.routes[r_idx].customer_nodes())
                        union = len(pre_set | post_set)
                        if union > 0:
                            route_change += 1.0 - len(pre_set & post_set) / union
                    route_change /= 4

                    log_entry = {
                        'iter': it,
                        'event_type': etype.name,
                        'action': chosen['name'],
                        'success': True,
                        'response_time_ms': result.get('response_time_ms', 0),
                        'pre_cost': pre_cost,
                        'post_cost': post_cost,
                        'delay_reduction': delay_reduction,
                        'congestion_reduction': cong_reduction,
                        'route_change_ratio': route_change,
                        'candidates_count': len(candidates),
                        'dispatch_mode': dispatch_mode,
                    }
                    dispatch_log.append(log_entry)

                    if verbose:
                        print(f'RRD | ACTION: {chosen["name"]} | mode={dispatch_mode} | '
                              f'cost {pre_cost:.1f}→{post_cost:.1f} | '
                              f'delay_red={delay_reduction:.1f} cong_red={cong_reduction:.2f} '
                              f'route_chg={route_change:.3f} | {len(candidates)} candidates')

                    if move_tabu and chosen:
                        for r in chosen['solution'].routes:
                            cids = r.customer_nodes()
                            if cids:
                                move_tabu.add(cids, 'dispatch', 'dispatch', it)
                    if sol_tabu and chosen:
                        sol_tabu.add(chosen['solution'], it)
                    if freq_memory and chosen:
                        cong_w = []
                        for r in chosen['solution'].routes:
                            c, rd = r.compute_cost(traffic, eff_demands, eff_service_times, eff_windows_open, eff_windows_close, lambda_1, lambda_2)
                            cong_w.append(rd['congestion_cost'])
                        freq_memory.update(chosen['solution'], congestion_weights=cong_w)

                elif dispatch_mode != 'none':
                    dispatch_log.append({
                        'iter': it, 'event_type': etype.name, 'success': False,
                        'response_time_ms': result.get('response_time_ms', 0) if result else 0,
                        'dispatch_mode': dispatch_mode,
                    })

            event_idx += 1
            it += 1
            continue

        else:
            if current is None:
                from core.initialization import build_greedy_init
                current = build_greedy_init(
                    traffic, demands, service_times, windows_open, windows_close,
                    n_vehicles=4, capacity=120.0, lambda_1=lambda_1, lambda_2=lambda_2,
                    seed=rng.randint(0, 99999))
                best = current.copy()
                best_cost, _ = best.compute_cost(
                    traffic, demands, service_times, windows_open, windows_close,
                    lambda_1=lambda_1, lambda_2=lambda_2)
                current_cost = best_cost

                from tabu.move_tabu import MoveTabuList
                from tabu.solution_tabu import SolutionTabuMemory
                move_tabu = MoveTabuList(tenure=7)
                sol_tabu = SolutionTabuMemory(tenure=15, n_customers=len(demands)-1)
                freq_memory = FrequencyMemory(n_customers=len(demands)-1, n_vehicles=4)
                freq_memory.update(current)

                d_weights = {n: 1.0 for n in destroy_names}
                r_weights = {n: 1.0 for n in repair_names}
                d_seg_rewards = {n: 0.0 for n in destroy_names}
                r_seg_rewards = {n: 0.0 for n in repair_names}
                T_sa = 0.05 * best_cost

                m0 = compute_metrics(best, traffic, demands, service_times,
                                     windows_open, windows_close, lambda_1, lambda_2)
                if verbose:
                    print(f'T-ALNS-RRD | iter={0:4d} | travel={m0["travel"]:7.1f} '
                          f'late={m0["lateness"]:6.1f} cong={m0["congestion"]:5.2f} '
                          f'total={m0["total"]:7.1f} OTDR={m0["otdr"]:5.1f}% | init')

            from core.destroy import random_removal, worst_removal, relatedness_removal
            from core.repair import greedy_insertion, regret2_insertion, tw_aware_insertion

            DESTROY_OPS = {'random': random_removal, 'worst': worst_removal, 'related': relatedness_removal}
            REPAIR_OPS = {'greedy': greedy_insertion, 'regret2': regret2_insertion, 'tw_aware': tw_aware_insertion}

            REWARD_SIGMA1 = 10.0
            REWARD_SIGMA2 = 5.0
            REWARD_SIGMA3 = 2.0
            REWARD_SIGMA4 = 0.5

            iter_rng = np.random.RandomState(rng.randint(0, 2**31 - 1))

            d_sum = sum(d_weights.values())
            r_sum = sum(r_weights.values())
            d_p = np.array([d_weights[n]/d_sum for n in destroy_names])
            r_p = np.array([r_weights[n]/r_sum for n in repair_names])

            found_valid = False
            working = None
            removed = None
            used_d = None
            used_r = None

            for attempt in range(max_attempts):
                d_name = iter_rng.choice(destroy_names, p=d_p)
                r_name = iter_rng.choice(repair_names, p=r_p)

                candidate = current.copy()
                alpha = iter_rng.uniform(0.10, 0.40)

                if d_name == 'random':
                    cand_removed = random_removal(candidate, alpha=alpha, rng=iter_rng)
                elif d_name == 'worst':
                    cand_removed = worst_removal(
                        candidate, alpha=alpha, traffic=traffic, demands=demands,
                        service_times=service_times, windows_open=windows_open,
                        windows_close=windows_close, lambda_1=lambda_1, lambda_2=lambda_2,
                        rng=iter_rng)
                else:
                    cand_removed = relatedness_removal(
                        candidate, alpha=alpha, traffic=traffic, demands=demands,
                        windows_open=windows_open, windows_close=windows_close, rng=iter_rng)

                REPAIR_OPS[r_name](
                    candidate, cand_removed, traffic, demands, service_times,
                    windows_open, windows_close, lambda_1=lambda_1, lambda_2=lambda_2,
                    capacity=120.0, rng=iter_rng)

                if sol_tabu.is_tabu(candidate, it):
                    continue
                if move_tabu.is_tabu(cand_removed, it):
                    continue

                found_valid = True
                working = candidate
                removed = cand_removed
                used_d = d_name
                used_r = r_name
                break

            if not found_valid:
                d_name = iter_rng.choice(destroy_names, p=d_p)
                r_name = iter_rng.choice(repair_names, p=r_p)
                working = current.copy()
                alpha = iter_rng.uniform(0.10, 0.40)

                if d_name == 'random':
                    removed = random_removal(working, alpha=alpha, rng=iter_rng)
                elif d_name == 'worst':
                    removed = worst_removal(
                        working, alpha=alpha, traffic=traffic, demands=demands,
                        service_times=service_times, windows_open=windows_open,
                        windows_close=windows_close, lambda_1=lambda_1, lambda_2=lambda_2,
                        rng=iter_rng)
                else:
                    removed = relatedness_removal(
                        working, alpha=alpha, traffic=traffic, demands=demands,
                        windows_open=windows_open, windows_close=windows_close, rng=iter_rng)

                REPAIR_OPS[r_name](
                    working, removed, traffic, demands, service_times,
                    windows_open, windows_close, lambda_1=lambda_1, lambda_2=lambda_2,
                    capacity=120.0, rng=iter_rng)

                used_d = d_name
                used_r = r_name

            new_cost, _ = working.compute_cost(
                traffic, demands, service_times, windows_open, windows_close,
                lambda_1=lambda_1, lambda_2=lambda_2)
            delta = new_cost - current_cost

            reward = REWARD_SIGMA4
            accepted = False
            is_new_best = new_cost < best_cost
            if is_new_best:
                accepted = True
                best = working.copy()
                best_cost = new_cost
                current = working.copy()
                current_cost = new_cost
                reward = REWARD_SIGMA1
                move_tabu.report_improvement()
            elif delta < 0:
                accepted = True
                current = working.copy()
                current_cost = new_cost
                reward = REWARD_SIGMA2
            else:
                prob = np.exp(-delta / max(T_sa, 1e-8))
                if iter_rng.random() < prob:
                    accepted = True
                    current = working.copy()
                    current_cost = new_cost
                    reward = REWARD_SIGMA3
                    move_tabu.report_stagnation()
                else:
                    move_tabu.report_stagnation()

            if accepted:
                move_tabu.add(removed, used_d, used_r, it)
                sol_tabu.add(working, it)
                cong_w = []
                for r in working.routes:
                    _, rd = r.compute_cost(traffic, demands, service_times, windows_open, windows_close, lambda_1, lambda_2)
                    cong_w.append(rd['congestion_cost'])
                freq_memory.update(working, congestion_weights=cong_w)

            d_seg_rewards[used_d] += reward
            r_seg_rewards[used_r] += reward

            if it % segment_size == 0:
                for n in destroy_names:
                    d_weights[n] = (1.0 - reaction_factor) * d_weights[n] + reaction_factor * d_seg_rewards[n]
                    d_seg_rewards[n] = 0.0
                for n in repair_names:
                    r_weights[n] = (1.0 - reaction_factor) * r_weights[n] + reaction_factor * r_seg_rewards[n]
                    r_seg_rewards[n] = 0.0

            T_sa *= cooling_rate

            if verbose and it % 200 == 0:
                m = compute_metrics(best, traffic, demands, service_times,
                                    windows_open, windows_close, lambda_1, lambda_2)
                print(f'T-ALNS-RRD | iter={it:4d} | travel={m["travel"]:7.1f} '
                      f'late={m["lateness"]:6.1f} cong={m["congestion"]:5.2f} '
                      f'total={m["total"]:7.1f} OTDR={m["otdr"]:5.1f}% | T={T_sa:.1f}')

        it += 1

    elapsed = time.time() - t0
    final = compute_metrics(best, traffic, demands, service_times,
                            windows_open, windows_close, lambda_1, lambda_2)

    if verbose:
        print(f'\nT-ALNS-RRD done | {max_iter} iters {elapsed:.1f}s')
        print(f'  travel={final["travel"]:.1f} late={final["lateness"]:.1f} cong={final["congestion"]:.2f} total={final["total"]:.1f} OTDR={final["otdr"]:.1f}%')
        print(f'\nDispatch stats:')
        for log in dispatch_log:
            print(f'  iter={log["iter"]} {log["event_type"]}: {log["action"]} '
                  f'rt={log.get("response_time_ms",0):.0f}ms '
                  f'success={log.get("success","?")} '
                  f'pre_cost={log.get("pre_cost","?"):.1f}→post_cost={log.get("post_cost","?"):.1f} '
                  f'delay_red={log.get("delay_reduction","?"):.1f} cong_red={log.get("congestion_reduction","?"):.2f}')

    return best, final, dispatch_log
