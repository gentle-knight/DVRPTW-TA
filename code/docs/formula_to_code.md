# Formula → Code Mapping

| Paper | Code Location | Function / Class |
|-------|--------------|-----------------|
| **Section 3.1: DVRPTW-TA Formulation** | | |
| Eq.1 objective $\min \sum [t_{ij}+\lambda_2\rho_{ij}] + \lambda_1\sum\delta_j$ | `src/core/solution.py:180` | `Solution.compute_cost()` |
| Eq.2 lateness $\delta_j = \max\{0, S_j-l_j\}$ | `src/core/solution.py:103` | `Route.forward_propagate()` |
| Eq.3 each customer served once | `src/core/solution.py:191` | `Solution.is_valid()` |
| Eq.4 vehicle capacity | `src/core/solution.py:71` | `Route.total_demand()` |
| Eq.5 temporal feasibility $S_j \geq \max\{A_j, e_j\}$ | `src/core/solution.py:102` | `Route.forward_propagate()` |
| Eq.6 soft time window | `src/core/solution.py:103` | `Route.forward_propagate()` |
| Eq.7 subtour elimination (MTZ) | implicit | route list representation |
| **Section 3.2: Traffic Flow Integration** | | |
| Eq.8 piecewise-constant travel time $t_{ij}(T_i)$ | `src/traffic/traffic_manager.py:50` | `TrafficManager.travel_time()` |
| Eq.9 congestion cost $\rho_{ij} = \theta\gamma_{ij}$ | `src/traffic/traffic_manager.py:63` | `TrafficManager.congestion_cost()` |
| Eq.10 reliability-adjusted time $t'_{ij} = t_{ij} + \beta\eta_{ij}$ | `src/traffic/traffic_manager.py:72` | `TrafficManager.adjusted_time()` |
| Eq.11 FIFO consistency | analytic guarantee | piecewise-constant ensures FIFO |
| **Section 3.3.1: ALNS** | | |
| Eq.12 route representation | `src/core/solution.py:61` | `Route` class |
| Eq.13 capacity constraint | `src/core/solution.py:71` | `Route.total_demand()` |
| Eq.14 destroy-repair cycle | `src/core/alns.py:101-119` | `run_alns()` |
| Eq.15 destroy fraction $\alpha\in[0.1,0.4]$ | `src/core/alns.py:100` | `alpha = iter_rng.uniform(0.10, 0.40)` |
| Eq.16 local insertion cost | `src/core/solution.py:101-103` | full forward propagation |
| Eq.17 full marginal cost | `src/core/solution.py:86-106` | full forward propagation |
| Eq.18 operator selection probability | `src/core/alns.py:91-92` | roulette wheel |
| Eq.19 weight update $\omega \leftarrow (1-\xi)\omega + \xi\theta_r$ | `src/core/alns.py:150-157` | EMA update per segment |
| Eq.20 SA acceptance | `src/core/alns.py:124-146` | current_cost reference |
| Eq.21 temperature cooling | `src/core/alns.py:159` | `T *= cooling_rate` |
| Algorithm 1 | `src/core/alns.py:49-182` | `run_alns()` |
| **Section 3.3.2: Tabu Enhancement** | | |
| Eq.22 move tabu (overlap check) | `src/tabu/move_tabu.py:22` | `MoveTabuList.is_tabu()` |
| Eq.23 solution hash $H(S)$ | `src/tabu/solution_tabu.py:13` | `hash_solution()` |
| Eq.24 $F_{ik}^{cv}$ update | `src/tabu/frequency.py:31` | `FrequencyMemory.update()` |
| Eq.25 $F_{ij}^{tp}$ update | `src/tabu/frequency.py:33` | `FrequencyMemory.update()` |
| Eq.26 diversification intensity $\delta(t)$ | `src/tabu/diversification.py:14` | `compute_intensity()` |
| Eq.27 probability adjustment | `src/tabu/diversification.py:20` | `adjust_probabilities()` |
| Eq.28 global best aspiration | `src/tabu/aspiration.py:18` | `check_aspiration()` |
| Eq.29 least frequency aspiration | `src/tabu/aspiration.py:21` | `check_aspiration()` |
| Eq.30 traffic adaptation aspiration | `src/tabu/aspiration.py:23` | `check_aspiration()` |
| Eq.31 adaptive tenure | `src/tabu/move_tabu.py:35-44` | `report_improvement()` / `report_stagnation()` |
| Eq.32 frequency normalization | `src/tabu/frequency.py:38` | `_normalize()` |
| Eq.33 congestion-weighted frequency | `src/tabu/frequency.py:31` | `update(congestion_weights=...)` |
| Algorithm 2 | `src/tabu/t_alns.py:38` | `run_t_alns_full()` |
| **Section 3.3.3: Rollout Dispatch** | | |
| E1-E4 event types | `src/dispatch/events.py:16` | `EventType` enum |
| Eq.34 urgency score $\Psi(e,t)$ | `src/dispatch/events.py:26-93` | implicit in injection functions |
| Eq.35 rollout value $V^{rollout}$ | `src/dispatch/rollout.py:16` | `rollout_cost()` |
| Eq.36 feasibility check | `src/dispatch/candidates.py` | implicit in candidate generation |
| Eq.37 lightweight interpolation | `src/dispatch/rollout.py:16` | simplified to piecewise-constant |
| Eq.38 tabu-adjusted value | `src/dispatch/dispatch.py:28` | tabu_penalty in score |
| Eq.39 composite score $\Sigma$ | `src/dispatch/dispatch.py:34` | `score = rc + sp + rp + tp` |
| Eq.40 stability | `src/dispatch/rollout.py:47` | `stability_penalty()` |
| Eq.41 recovery | `src/dispatch/rollout.py:56` | `recovery_penalty()` |
| Eq.42 adaptive horizon | `src/dispatch/dispatch.py:17` | fixed `horizon_minutes=60` |
| Eq.43 adaptive simulation count | N/A | synchronous: single rollout |
| Algorithm 3 | `src/dispatch/t_alns_rrd.py:41` | `run_t_alns_rrd()` |
| **Section 4.4: Evaluation Metrics** | | |
| Eq.44 total cost | `src/utils/evaluation.py:16` | `compute_metrics()` |
| Eq.45 OTDR | `src/utils/evaluation.py:33` | `compute_metrics()` |
| Eq.46 avg route duration | `src/utils/evaluation.py:56` | implicit |
| Eq.47 CES | `src/utils/evaluation.py:34` | `compute_metrics()` |
