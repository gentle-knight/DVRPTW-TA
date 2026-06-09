# 公式 → 代码映射

| 论文 | 代码位置 | 函数/类 |
|------|---------|---------|
| **第 3.1 节：DVRPTW-TA 问题建模** | | |
| Eq.1 目标函数 $\min \sum [t_{ij}+\lambda_2\rho_{ij}] + \lambda_1\sum\delta_j$ | `src/core/solution.py:180` | `Solution.compute_cost()` |
| Eq.2 迟到定义 $\delta_j = \max\{0, S_j-l_j\}$ | `src/core/solution.py:103` | `Route.forward_propagate()` |
| Eq.3 每个客户仅服务一次 | `src/core/solution.py:191` | `Solution.is_valid()` |
| Eq.4 车辆容量约束 | `src/core/solution.py:71` | `Route.total_demand()` |
| Eq.5 时间可行性 $S_j \geq \max\{A_j, e_j\}$ | `src/core/solution.py:102` | `Route.forward_propagate()` |
| Eq.6 软时间窗 | `src/core/solution.py:103` | `Route.forward_propagate()` |
| Eq.7 子回路消除 (MTZ) | 隐式实现 | 路线列表表示 |
| **第 3.2 节：交通流数据集成** | | |
| Eq.8 分段常数旅行时间 $t_{ij}(T_i)$ | `src/traffic/traffic_manager.py:50` | `TrafficManager.travel_time()` |
| Eq.9 拥堵成本 $\rho_{ij} = \theta\gamma_{ij}$ | `src/traffic/traffic_manager.py:63` | `TrafficManager.congestion_cost()` |
| Eq.10 可靠性调整时间 $t'_{ij} = t_{ij} + \beta\eta_{ij}$ | `src/traffic/traffic_manager.py:72` | `TrafficManager.adjusted_time()` |
| Eq.11 FIFO 一致性 | 解析保证 | 分段常数天然满足 FIFO |
| **第 3.3.1 节：ALNS** | | |
| Eq.12 路线表示 | `src/core/solution.py:61` | `Route` 类 |
| Eq.13 容量约束 | `src/core/solution.py:71` | `Route.total_demand()` |
| Eq.14 破坏-修复循环 | `src/core/alns.py:101-119` | `run_alns()` |
| Eq.15 破坏比例 $\alpha\in[0.1,0.4]$ | `src/core/alns.py:100` | `alpha = iter_rng.uniform(0.10, 0.40)` |
| Eq.16 局部插入成本 | `src/core/solution.py:101-103` | 全量前向传播 |
| Eq.17 完全边际成本 | `src/core/solution.py:86-106` | 全量前向传播 |
| Eq.18 算子选择概率 | `src/core/alns.py:91-92` | 轮盘赌 |
| Eq.19 权重更新 $\omega \leftarrow (1-\xi)\omega + \xi\theta_r$ | `src/core/alns.py:131-137` | 每 segment 的 EMA 更新 |
| Eq.20 SA 接受准则 | `src/core/alns.py:105-126` | 使用 current_cost 作为基准 |
| Eq.21 温度冷却 | `src/core/alns.py:139` | `T *= cooling_rate` |
| 算法 1 | `src/core/alns.py:49-162` | `run_alns()` |
| **第 3.3.2 节：Tabu 增强** | | |
| Eq.22 移动 Tabu（重叠检查） | `src/tabu/move_tabu.py:22` | `MoveTabuList.is_tabu()` |
| Eq.23 解哈希 $H(S)$ | `src/tabu/solution_tabu.py:13` | `hash_solution()` |
| Eq.24 $F_{ik}^{cv}$ 更新 | `src/tabu/frequency.py:31` | `FrequencyMemory.update()` |
| Eq.25 $F_{ij}^{tp}$ 更新 | `src/tabu/frequency.py:33` | `FrequencyMemory.update()` |
| Eq.26 多样化强度 $\delta(t)$ | `src/tabu/diversification.py:14` | `compute_intensity()` |
| Eq.27 概率调整 | `src/tabu/diversification.py:20` | `adjust_probabilities()` |
| Eq.28 全局最优渴望 | `src/tabu/aspiration.py:18` | `check_aspiration()` |
| Eq.29 最少频率渴望 | `src/tabu/aspiration.py:21` | `check_aspiration()` |
| Eq.30 交通适应渴望 | `src/tabu/aspiration.py:23` | `check_aspiration()` |
| Eq.31 自适应 tenure | `src/tabu/move_tabu.py:35-44` | `report_improvement()` / `report_stagnation()` |
| Eq.32 频率归一化 | `src/tabu/frequency.py:38` | `_normalize()` |
| Eq.33 拥堵加权频率 | `src/tabu/frequency.py:31` | `update(congestion_weights=...)` |
| 算法 2 | `src/tabu/t_alns.py:38` | `run_t_alns_full()` |
| **第 3.3.3 节：Rollout 调度** | | |
| E1-E4 事件类型 | `src/dispatch/events.py:16` | `EventType` 枚举 |
| Eq.34 紧迫度评分 $\Psi(e,t)$ | 隐式实现 | 同步版使用预设迭代触发 |
| Eq.35 rollout 价值 $V^{rollout}$ | `src/dispatch/rollout.py:16` | `rollout_cost()` |
| Eq.36 可行性检查 | `src/dispatch/candidates.py` | 隐式在候选动作生成中 |
| Eq.37 轻量插值 | `src/dispatch/rollout.py:16` | 简化为分段常数 |
| Eq.38 Tabu 调整价值 | `src/dispatch/dispatch.py:28` | 评分中的 tabu_penalty |
| Eq.39 复合评分 $\Sigma$ | `src/dispatch/dispatch.py:34` | `score = rc + sp + rp + tp` |
| Eq.40 稳定性 | `src/dispatch/rollout.py:47` | `stability_penalty()` |
| Eq.41 恢复性 | `src/dispatch/rollout.py:56` | `recovery_penalty()` |
| Eq.42 自适应时域 | `src/dispatch/dispatch.py:17` | 固定 `horizon_minutes=60` |
| Eq.43 自适应模拟次数 | 不适用 | 同步版：单次 rollout |
| 算法 3 | `src/dispatch/t_alns_rrd.py:41` | `run_t_alns_rrd()` |
| **第 4.4 节：评价指标** | | |
| Eq.44 总成本 | `src/utils/evaluation.py:16` | `compute_metrics()` |
| Eq.45 OTDR | `src/utils/evaluation.py:33` | `compute_metrics()` |
| Eq.46 平均路线时长 | `src/utils/evaluation.py:56` | 隐式实现 |
| Eq.47 CES | `src/utils/evaluation.py:34` | `compute_metrics()` |
