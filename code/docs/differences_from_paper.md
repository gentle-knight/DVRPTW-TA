# 与论文的已知差异

## 实现简化

| 项目 | 论文 | 本实现 | 原因 |
|------|------|--------|------|
| **RRD 线程模型** | 线程 1（优化）+ 线程 2（事件监控） | 单线程同步 | 设计选择；事件在预设迭代 (250/500/750/875) 触发 |
| **Eq.16-17 插入成本** | 增量边际成本公式 + suffix 传播 + early abandonment | 全量前向传播 | 更稳健；n=47 时计算开销可忽略 |

## 已对齐项（之前为差异，现已修复）

| 项目 | 论文要求 | 实现位置 | 状态 |
|------|---------|---------|------|
| **E3 容量违规事件** | 4 种事件类型 (E1-E4) | `events.py:E3_CAPACITY` + `inject_capacity_violation()` + `candidates.py:generate_candidates_capacity()` | ✅ 已实现 |
| **Eq.34 紧迫度评分** | Ψ(e,t) = α·time + β·impact + γ·cost | `events.py:urgency_score()` 含四种事件类型的差异化权重 | ✅ 已实现 |
| **Eq.37 线性插值** | rollout 使用分段线性插值 | `traffic_manager.py:interpolated_travel_time()` | ✅ 已实现 |
| **Eq.40 复合权重** | ω₁=0.4, ω₂=0.3, ω₃=0.3 | `rollout.py:evaluate_candidate()` 默认参数 | ✅ 已实现 |
| **Eq.42-43 自适应时域** | H_rollout = max(H_min, H_max - α·Ψ)，N_sim 自适应 | `t_alns_rrd.py` H=max(30, 120-40·Ψ), N=min(20, Ψ·30) | ✅ 已实现 |
| **Eq.10 可靠性调整** | t' = t + β·η | `traffic_manager.py:adjusted_time()`，所有 cost 评估使用 | ✅ 已实现 |
| **Eq.26 多样化强度** | δ(t) = ω₁·stagnation + ω₂·tabu_ratio + ω₃·freq_std | `diversification.py:compute_intensity()` | ✅ 已实现 |
| **Eq.27 概率调整** | p'_h = η·p_h + (1-η)·div_h | `diversification.py:adjust_probabilities()` + 算子差异化 `diversity_scores` | ✅ 已实现 |
| **Eq.28-30 渴望准则** | global_best / least_freq / traffic_adapt | `aspiration.py:check_aspiration()`，在 T-ALNS 和 T-ALNS-RRD 中均调用 | ✅ 已实现 |
| **Eq.22 Move Tabu** | 基于 Jaccard 重叠的自适应 tenure | `move_tabu.py:MoveTabuList` 含 `report_improvement/stagnation` | ✅ 已实现 |
| **Eq.38-39 Tabu 调整价值** | V_adjusted = V_rollout - τ·1[Tabu] + τ·Diversification | `dispatch.py:dispatch_action()` 含 tabu_penalty + `rollout.py:compute_diversion_bonus()` | ✅ 已实现 |
| **Eq.41-42 Stability/Recovery** | Stability (Jaccard) + Recovery (position vs S_best) | `rollout.py:stability_penalty()` + `recovery_penalty()`，dispatch 时传入 `best_solution` 作为恢复参考 | ✅ 已实现 |
| **候选动作可行性检查** | 论文 Eq.36 可行性约束 | `dispatch.py:is_valid()` 前置过滤 + `t_alns_rrd.py` 调度后 guardrail 回退 | ✅ 已实现 |
| **收敛历史追踪** | 论文 Table 9-10 所需的 epoch 收敛数据 | `t_alns_rrd.py:history` + `run_main.py` 保存 `_history.json` | ✅ 已实现 |

## 数据生成差异

| 项目 | 论文 | 本实现 | 原因 |
|------|------|--------|------|
| **交通数据来源** | 高德地图 API + SUMO v1.19 仿真 | 基于 OSM 的合成交通剖面 | 无公开 API 访问权限 |
| **旅行时间量级** | 论文旅行成本 ~1900-2250 (上海真实交通) | 代码旅行成本 ~230-270 (OSM 合成数据) | 数据源决定；相对性能排序不受影响 |
| **Eq.10 η 生成方式** | 基于历史轨迹数据的经验标准差 | 合成生成 | 无真实历史轨迹数据 |
| **晚间时间窗** | 17:00-20:00 | 交通数据仅覆盖至 18:00 | 论文自身限制；超过 18:00 使用最后区间值 |

## 实验差异

| 项目 | 论文 | 本实现 | 原因 |
|------|------|--------|------|
| **Oracle-Traffic-Perfect 基准** | 具有完美交通预知能力的基准 | 尚未实现 | 需单独生成具有先知知识的交通数据 |
| **SOTA 对比 (Table 17)** | 与 GA-ALNS, GA-VNS, Dynamic VRP-ACO, ML-Enhanced ALNS 对比 | 未实现 | 外部基准需独立实现；可直接引用论文数值 |
| **统计检验 (Table 18)** | paired t-test with Bonferroni correction | 未实现 | 可用 scipy.stats 实现 |
| **参数敏感性 (Table 3-4)** | 车队/客户/容量扫描 + 超参数扫描 | 未实现 | 实验 runner 待开发 |
| **鲁棒性/压力测试 (Table 14-16)** | σ=0.1-0.5 + 5 种压力场景 | 未实现 | 实验 runner 待开发 |

## 算法 3 (RRD) 同步版说明

同步版实现了算法 3 的全部核心逻辑：

1. **事件注入**：E1 (iter=250) → E2 (iter=500) → E4 (iter=750) → E3 (iter=875)
2. **紧迫度评分**：`urgency_score()` 计算 Ψ(e,t)，用于自适应调节 rollout horizon 和模拟次数
3. **候选动作生成**：全部 4 种事件类型均有专属候选生成器
4. **Rollout 评估**：支持确定性（`n_samples=1`）和 MC（`n_samples>1`）模式，使用线性插值旅行时间
5. **调度决策**：基于 Eq.40 复合评分 (0.4/0.3/0.3) + Tabu 调整 + 多样化奖励
6. **可行性保障**：候选过滤 + 调度后 guardrail 回退
7. **Tabu 更新**：调度后同步更新 Move/Solution/Frequency 记忆

与论文的唯一架构差异：事件在预设迭代触发而非实时检测。此差异不影响算法机制验证。
