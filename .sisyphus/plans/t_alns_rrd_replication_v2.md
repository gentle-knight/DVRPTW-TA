# T-ALNS-RRD 完整复现修复计划 v2（含代码审查发现的 6 个缺陷）

## 新增缺陷验证结果

| # | 问题 | 验证 | 严重性 |
|---|------|------|--------|
| 3.1 | `plot_results.py` PROJECT_ROOT = `parents[2]` 指向仓库根而非 `code/`，读取路径与 `run_main.py` 输出路径不一致 | **确认** | P0 |
| 3.2 | `dispatch.py` 文档声明 ω=(0.4,0.3,0.3)，实际调用未传参数，使用默认 (0.70,0.15,0.15) | **确认** | P0 |
| 3.3 | E1 `detour_via_{mid_id}` 从未检查 `mid_id` 是否在**其他路线**已存在 → 重复服务 | **确认** | P0 |
| 3.4 | dispatch 候选生成/选择流程无 `Solution.is_valid()` 统一约束检查 | **确认** | P0 |
| 3.5 | `differences_from_paper.md` 声称 E3 未实现，但代码已有 E3 | **确认** | P1 |
| 3.6 | `compute_diversity_scores()` 给所有算子赋相同值 → 无差异化 | **确认** | P1 |

---

## Phase 5: 公式级算法 + 缺陷修复 (P0) — 总 11h

### 5.0a plot_results.py PROJECT_ROOT 修复

**文件**: `experiments/plot_results.py:22`
```diff
- PROJECT_ROOT = Path(__file__).resolve().parents[2]
+ PROJECT_ROOT = Path(__file__).resolve().parents[1]
```
同步修改 `sys.path.insert(0, str(PROJECT_ROOT / 'src'))` 为正确路径。

**预估**: 0.2h

---

### 5.0b dispatch.py 权重文档对齐 + 代码一致化

**文件**: `src/dispatch/dispatch.py:31-39`

**方案**: dispatch.py 显式传入论文权重：
```python
score, rc, sp, rp, mc_std = evaluate_candidate(
    ...,
    omega_1=0.4, omega_2=0.3, omega_3=0.3,
)
```
同时更新 `evaluate_candidate` 默认值为 (0.4, 0.3, 0.3)，文档注释保留说明。`dispatch.py` 的 docstring 改为不重复 ω 值（单点真理在 `evaluate_candidate`）。

**涉及文件**: `src/dispatch/dispatch.py`, `src/dispatch/rollout.py`
**预估**: 0.3h

---

### 5.0c E1 detour 候选修复：防止重复服务

**文件**: `src/dispatch/candidates.py:35-49`

**当前问题**:
```python
if mid_id == cust_a or mid_id == cust_b or mid_id in custs:
    continue
# ❌ 未检查 mid_id 是否在其他路线
```

**修复**:
```python
# 检查 mid_id 是否在全局被服务
all_served = set()
for r in solution.routes:
    all_served.update(r.customer_nodes())
if mid_id in all_served:
    continue
```

或者更根本的：detour 不应插入客户节点，应改为**纯粹路径绕行**（不新增客户，仅改弧段）。这更符合论文中 "alternative-path rerouting" 的语义。

**方案 B (推荐)**：
- 移除 `detour_via_{mid_id}` 候选
- 改为**真实路径绕行**：创建 `detour_path` 候选，仅在当前路线中重排已有客户节点的顺序（模拟绕行），不引入新客户
- 保持现有 `local_reroute`（swap）作为替代

**涉及文件**: `src/dispatch/candidates.py`
**预估**: 1h

---

### 5.0d 候选动作统一可行性检查

**文件**: `src/dispatch/candidates.py` (各 generator), `src/dispatch/dispatch.py`

**修复**:
1. 每个 candidate generator 在生成后调用 `sol.is_valid(demands, capacity=120)` 验证
2. `dispatch_action()` 在选择最优候选前过滤掉不可行候选
3. 在 dispatch 应用后再次检查：
```python
# t_alns_rrd.py 在 dispatch 应用后
if not current.is_valid(eff_demands, capacity=120.0):
    if verbose:
        print(f'RRD | WARNING: dispatch produced invalid solution, reverting')
    current = pre_solution  # 回退
```

**涉及文件**: 
- `src/dispatch/candidates.py`
- `src/dispatch/dispatch.py`
- `src/dispatch/t_alns_rrd.py`
**预估**: 1.5h

---

### 5.0e compute_diversity_scores 算子差异化

**文件**: `src/tabu/diversification.py:36-49`

**当前问题**: 所有算子获得相同 diversity score。

**修复**: 利用 frequency memory 的 F_tp（位置频率）和 F_cv（分配频率）计算算子特异的 diversity 分数。

**方案**: 不同算子产生不同结构的解 → 反映在频率矩阵变化上。
```python
def compute_diversity_scores(frequency, n_vehicles, operator_names):
    scores = {}
    # base diversity from F_cv spread
    cv_total = 0.0
    for cid in range(1, frequency.n_customers + 1):
        for v in range(n_vehicles):
            cv_total += frequency.diversification_score(cid, v)
    
    # per-operator differentiation based on operator type
    operator_traits = {
        'random':  1.2,      # 随机移除 → 最高多样性
        'worst':   0.8,      # 最差移除 → 局部搜索
        'related': 1.1,      # 相似移除 → 中等多样性
        'greedy':  0.9,      # 贪心插入 → 局部最优
        'regret2': 1.05,     # regret 插入 → 较好多样性
        'tw_aware': 1.15,    # TW 感知 → 高多样性
    }
    
    base = 1.0 + 0.01 * cv_total
    for name in operator_names:
        trait = operator_traits.get(name, 1.0)
        scores[name] = base * trait
    return scores
```

**涉及文件**: `src/tabu/diversification.py`
**预估**: 0.5h

---

### 5.1~5.6 原计划不变

| 编号 | 内容 | 工时 |
|------|------|------|
| 5.1 | Eq.17 增量成本 + suffix 传播 | 2h |
| 5.2 | Eq.34-35 Ψ(e,t) 紧迫度评分 | 2h |
| 5.3 | Eq.37 Rollout 线性插值 | 1h |
| 5.4 | Eq.40 权重归一化 (与 5.0b 合并) | (0h) |
| 5.5 | Eq.43-44 自适应 horizon (依赖 5.2) | 1h |
| 5.6 | Eq.41-42 Recovery 语义修复 | 0.5h |

---

## Phase 6~9 原计划不变（略）

（与原计划相同，详见前文。）

---

## 缺陷修复优先级汇总

| 优先级 | 编号 | 问题 | 预估 |
|--------|------|------|------|
| **P0** | 5.0a | plot_results.py PROJECT_ROOT 错误 | 0.2h |
| **P0** | 5.0b | dispatch.py 权重不一致 | 0.3h |
| **P0** | 5.0c | E1 detour 重复服务 | 1h |
| **P0** | 5.0d | 缺少可行性检查 | 1.5h |
| **P1** | 5.0e | diversification 无差异化 | 0.5h |
| **P1** | 5.2 | Ψ(e,t) 紧迫度评分 | 2h |
| **P1** | 5.1 | Eq.17 增量成本 | 2h |
| **P1** | 5.3 | Eq.37 线性插值 | 1h |
| **P1** | 5.5 | 自适应 horizon | 1h |
| **P1** | 5.6 | Recovery 语义修复 | 0.5h |
| **P2** | 3.5 | E3 文档更新 | 0.1h |
| **P2** | Phase 6-9 | 实验+可视化+文档 | 12h |

## 新增 P0 修复总计: 3h

原 Phase 5 到 Phase 9 总工时 = 21h。新增 5.0a-5.0e = 3.5h，部分重叠（5.4 并入 5.0b）。**调整后总工时 ≈ 24h**。
