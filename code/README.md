# T-ALNS-RRD：城市末端配送动态路径优化

论文复现：*"Optimizing urban last mile delivery efficiency through dynamic vehicle routing heuristics and traffic flow analysis"* (Liu & Wang).

## 项目结构

```
DVRPTW-TA (Eq.1-7)    ←→ solution.py
  ├─ 交通张量            ←→ traffic_manager.py + traffic_tensor.npz
  ├─ ALNS (算法 1)       ←→ core/alns.py
  ├─ T-ALNS (算法 2)     ←→ tabu/t_alns.py + move/solution/frequency/aspiration/diversification
  └─ T-ALNS-RRD (算法 3) ←→ dispatch/t_alns_rrd.py + events/candidates/rollout/dispatch
```

## 快速开始

```bash
# 安装依赖
pip install -r requirements.txt

# 生成数据集（一次性）
python datasets/network/download_osm_network.py
python datasets/customers/select_nodes.py
python datasets/traffic/generate_traffic.py

# 运行主实验（5 个算法 × 30 个随机种子）
python experiments/run_main.py

# 运行消融实验
python experiments/run_ablation.py

# 生成图表
python experiments/plot_results.py
```

## 公式 → 代码映射

详见 `docs/formula_to_code.md`（共 47 个公式全覆盖）。

| 论文 | 代码 |
|------|------|
| Eq.1 目标函数 | `src/core/solution.py` → `Solution.compute_cost()` |
| Eq.8–10 交通流 | `src/traffic/traffic_manager.py` |
| Eq.18–21 ALNS | `src/core/alns.py` → `run_alns()` |
| Eq.22–33 Tabu | `src/tabu/`（move/solution/frequency/aspiration/diversification） |
| 算法 1 ALNS | `src/core/alns.py` |
| 算法 2 T-ALNS | `src/tabu/t_alns.py` |
| 算法 3 T-ALNS-RRD | `src/dispatch/t_alns_rrd.py` |

## 与论文的已知差异

详见 `docs/differences_from_paper.md`。主要差异：基于 OSM 合成交通数据、RRD 采用同步版实现、E3 事件未覆盖。

## 许可

MIT
