# T-ALNS-RRD 论文对齐修复计划

## 背景

对照论文《Optimizing urban last mile delivery efficiency through dynamic vehicle routing heuristics and traffic flow analysis》中的实验设置与算法伪代码（Algorithm 1-3），已对 `code/` 目录下完整代码实现进行了逐项 GAP 分析。本计划列出所有需要修复的差异项，按优先级和依赖关系组织。

## 修复总览

```
Phase 1 (P0): 核心算法逻辑修复 ─ Aspiration + Diversification + SA Init ─ 3h
Phase 2 (P1): Dispatch 架构修复 ─ MC Rollout + 评分权重 + Bonus ─ 5h
Phase 3 (P2): 细节机制对齐 ─ Tabu tenure + Freq Bug + E1/E3 ─ 4.5h
Phase 4 (P3): 实验设置归一化 ─ T_max + 迭代数 ─ 1.5h
Total: ~14h
```

## Phase 1 ─ P0: 核心算法逻辑修复

### 1.1 T-ALNS-RRD 补全 Aspiration Criteria

- **文件**: `code/src/dispatch/t_alns_rrd.py` (lines 328-331)
- **问题**: Tabu move 直接 `continue` 跳过，不检查 `check_aspiration()`
- **修复**: 仿照 `t_alns.py` lines 150-182，在 Tabu 检测后添加 aspiration check (global_best / least_freq / traffic_adapt)
- **验证**: 运行 1 seed，确认 aspiration_count > 0
- **预估**: 1h

### 1.2 T-ALNS-RRD 补全 Diversification Intensity

- **文件**: `code/src/dispatch/t_alns_rrd.py` (lines 290-295)
- **问题**: 标准轮盘赌选择算子，无 `compute_intensity()` 和 `adjust_probabilities()`
- **修复**: 添加 δ(t) 计算、δ > δ_max 时切换到 diversity-biased 概率，追踪 `last_best_iter`
- **验证**: 运行 1 seed，确认 "DIV" 标签在输出中出现
- **预估**: 1.5h

### 1.3 SA 温度初始化 Bug

- **文件**: `code/src/dispatch/t_alns_rrd.py` (line 74)
- **问题**: `T_sa = 0.05 * 300` 硬编码，而非 `0.05 * best_cost`
- **修复**: 延迟初始化到 best_cost 已知后
- **预估**: 0.5h

---

## Phase 2 ─ P1: Dispatch 架构修复

### 2.1 Dispatch 评分权重对齐论文 Eq.40

- **文件**: `code/src/dispatch/dispatch.py` (line 100), `code/src/dispatch/rollout.py`
- **问题**: `score = rc + sp + rp + tp` (所有权重=1.0)，论文要求 ω₁=0.4, ω₂=0.3, ω₃=0.3
- **修复**: 归一化 stability/recovery 分量后按 0.4/0.3/0.3 加权
- **验证**: P3 dispatch 对比实验，rollout 应优于 greedy
- **预估**: 2h

### 2.2 Rollout 引入 MC 模拟 (Eq.10, Eq.43)

- **文件**: `code/src/dispatch/rollout.py`
- **问题**: 单次确定性 rollout，论文要求 50 次 MC 模拟含交通扰动
- **修复**: 添加 `n_samples` 参数，对 travel time 施加 η 引导的噪声
- **验证**: 同一 snapshot 多次 rollout 标准差非零
- **预估**: 2h

### 2.3 Dispatch 添加 Diversification Bonus (Eq.39)

- **文件**: `code/src/dispatch/dispatch.py`
- **问题**: 仅有 Tabu penalty，无 diversification reward
- **修复**: 使用 `freq_memory.diversification_score()` 计算 bonus
- **预估**: 1h

---

## Phase 3 ─ P2: 细节机制对齐

### 3.1 Adaptive Move Tabu Tenure (Eq.32)

- **文件**: `code/src/tabu/move_tabu.py`
- **问题**: tenure 固定为 7，论文要求自适应 (stagnation → +1, improve → -1)
- **修复**: 添加 `report_improvement()` / `report_stagnation()` 调整 tenure
- **预估**: 1h

### 3.2 Frequency Memory E2 重置 Bug

- **文件**: `code/src/dispatch/t_alns_rrd.py` (lines 182-183), `code/src/tabu/frequency.py`
- **问题**: E2_URGENT 事件后重建 FrequencyMemory，丢弃所有累积数据
- **修复**: 添加 `resize()` 方法保留已有数据
- **预估**: 0.5h

### 3.3 E1 Traffic Dispatch Candidates 增强

- **文件**: `code/src/dispatch/candidates.py` (lines 17-73)
- **问题**: `local_reroute` 仅 swap 邻居，非论文的 k-shortest detours (K_s=5)
- **修复**: 添加基于最短路径的 detour 候选生成
- **预估**: 1.5h

### 3.4 E3 Capacity Violations 事件

- **文件**: `code/src/dispatch/events.py`, `code/src/dispatch/candidates.py`, `code/src/dispatch/t_alns_rrd.py`
- **问题**: 论文 4 类事件，代码仅实现 E1/E2/E4
- **修复**: 添加 E3 事件检测 + 负载重分配候选生成
- **预估**: 1.5h

---

## Phase 4 ─ P3: 实验设置归一化

### 4.1 添加 T_max 时间限制

- **文件**: `code/src/core/alns.py`, `code/src/tabu/t_alns.py`, `code/src/dispatch/t_alns_rrd.py`
- **问题**: 无 600s 时间限制，论文使用 T_max=600s
- **修复**: 主循环中添加 `elapsed < T_max` 检查
- **预估**: 1h

### 4.2 实验参数对齐

- **文件**: `code/experiments/run_main.py`
- **问题**: 默认 `--iters 800`，论文 1000
- **修复**: `--iters 1000`, 新增 `--tmax 600`
- **预估**: 0.5h

---

## 依赖关系

```
Phase 1 (P0) ───── 先做 ─────────┐
  ├─ 1.1 Aspiration               │
  ├─ 1.2 Diversification          │
  └─ 1.3 SA Init Bug              │
                                  │
Phase 2 (P1) ───── 依赖 P0 ──────┤
  ├─ 2.1 Scoring Weights          │
  ├─ 2.2 MC Rollout               │
  └─ 2.3 Diversification Bonus    │
                                  │
Phase 3 (P2) ──── 独立可并行 ────┤
  ├─ 3.1 Adaptive Tabu Tenure     │
  ├─ 3.2 Frequency Reset Bug      │
  ├─ 3.3 E1 Candidates            │
  └─ 3.4 E3 Event                 │
                                  │
Phase 4 (P3) ──── 最后做 ────────┘
  ├─ 4.1 T_max
  └─ 4.2 Params
```

## 验证 Checkpoint

每 Phase 完成后运行：

```bash
# Phase 1
python experiments/run_main.py --algo T-ALNS-RRD --seeds 3 --iters 400 --instance easy
# 检查: aspiration_count > 0, DIV 标签, best_cost 改善

# Phase 2
python experiments/run_rrd_dispatch.py --seeds 3 --iters 400
# 检查: rollout cost_reduction > greedy, MC std > 0

# Phase 3
python experiments/run_main.py --algo T-ALNS-RRD --seeds 3 --iters 400 --instance medium
# 检查: E3 日志, E1 detours > 3 candidates

# Phase 4
python experiments/run_main.py --seeds 5 --iters 1000 --instance medium
# 检查: 无 T_max 超时, 参数正确
```

## 非修复范围（已知但接受）

以下 GAP 属于简化实现，在当前 proof-of-concept 阶段接受：

1. **交通数据源**: 论文使用高德+SUMO 实时数据，代码使用 OSM 合成静态 tensor。重做数据层超出本修复范围。
2. **双线程架构**: 论文描述 Thread 1 (T-ALNS) + Thread 2 (Event Monitor)，代码使用同步单线程+预设迭代点。全异步架构超出当前范围。
3. **Eq.17 early abandonment**: 代码的 repair 使用完整 route cost 计算而非增量 suffix propagation。正确性无影响。
4. **实时事件检测 vs 预设事件**: 论文描述 `monitor_events()` 实时监控，代码使用硬编码迭代点。添加真实事件流超出当前范围。
5. **Eq.42/43 自适应 horizon/sim**: 代码使用固定 horizon_minutes=60。自适应调整超出当前范围。
