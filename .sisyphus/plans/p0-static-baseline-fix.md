# P0: Static Baseline 修复 + easy 实例验证

## TL;DR
> **目标**: 修复 Static baseline 与其他算法的成本空间不同的问题。
> **核心修改**: `static_vrptw.py` 已使用时段平均旅行时间(无需改)，只需改 `run_main.py` 中 Static 的评估逻辑。
> **验证**: 重跑 easy 30 seeds，确认成本排序恢复。

---

## 背景

当前 Static baseline 的 `StaticTrafficManager` 已经正确使用 `np.mean(tensor[:,:,:,0], axis=2)` 做时段平均规划（之前已修改）。但 `run_main.py` 中 Static 的 `compute_metrics` 仍用 `static_tm` 评估，导致 cost 空间与其他算法不同。

## 修改清单

### Task 1: static_vrptw.py 返回 static_tm

**文件**: `code/src/baselines/static_vrptw.py`

**修改**: `run_static_vrptw()` 返回值从 `return sol` 改为 `return sol, static_tm`。调用处同步适配。

### Task 2: run_main.py 中 Static 双成本评估

**文件**: `code/experiments/run_main.py`

**修改** `run_one()` 中 `Static-VRPTW` 分支:

```python
if alg_name == 'Static-VRPTW':
    sol, static_tm = run_static_vrptw(tm, demands, service_times, windows_open, windows_close, seed=seed)
    # 规划成本（用于说明规划-执行差异）
    m_plan, _ = sol.compute_cost(static_tm, demands, service_times, windows_open, windows_close, LAMBDA_1, LAMBDA_2)
    # 评估成本（用动态TM，与其他算法同一空间）
    m = compute_metrics(sol, tm, demands, service_times, windows_open, windows_close, LAMBDA_1, LAMBDA_2)
    m['planning_total'] = m_plan  # 新增字段
```

**预期效果**: Static 的 `total` 字段应高于 `planning_total`（因为动态评估暴露了高峰期拥堵成本）。

### Task 3: 验证

```bash
cd code
python experiments/run_main.py --seeds 30 --iters 800
```

**P0 通过标准**:
- [ ] Static 评估使用动态 TrafficManager ✅
- [ ] Static 的 `total` 与其他算法在同一成本空间 ✅
- [ ] 若 easy 仍 OTDR=100%，记录为 ceiling effect，不视为失败 ✅

**趋势检查** (不写死具体值):
- Static `total` ≥ TA-Greedy `total`（正向排序）
- Static `lateness` ≥ TA-Greedy `lateness`（平均规划暴露延迟）
- ALNS/T-ALNS 逐步改善 total

## Must NOT do
- 不修改 TrafficManager 或 generate_traffic.py
- 不修改 easy 实例的 CSV
- 不修改其他算法的评估逻辑
