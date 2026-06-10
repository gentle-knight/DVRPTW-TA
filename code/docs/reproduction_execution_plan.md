# 期末复现实验执行计划

目标：在不引入高德/SUMO 全套工程的前提下，尽可能复现论文的核心算法趋势，证明
`Static-VRPTW < TA-Greedy < ALNS < T-ALNS < T-ALNS-RRD` 的机制收益。

## 阶段 1：修正可运行性与一致性

- 修复主实验 runner：静态/贪心基线也写入 history，避免 `history` 未定义。
- 修复 RRD dispatch runner：适配 `run_t_alns_rrd()` 的 4 个返回值。
- 修复 E2 动态订单：新增订单只在选择插入/延迟插入时进入 active customer set；subcontract 作为外部处理，不污染路线指标分母。
- 修复调度后状态：dispatch 后同步 `current_cost`；若 active customer set 改变，则重置 `best`，避免返回不服务新增客户的旧最优解。
- 验收：小规模命令能跑通，不要求趋势稳定。

## 阶段 2：机制级趋势验证

- 主实验使用当前 OSM 合成交通数据，先跑 `easy` 与 `medium` 各 3-5 seeds，确认执行稳定。
- 主算法趋势对比默认使用不改变客户集合的事件序列 `E1/E4/E3/E1`，保证 ALNS、T-ALNS、T-ALNS-RRD 的成本在同一 47 客户实例上可比。
- E2 urgent order 作为 RRD 专项实验单独展示，因为它会改变 active customer set，直接放进主算法总成本对比会让 T-ALNS-RRD 承担额外客户，污染趋势判断。
- 如果趋势不稳定，优先调整合成实例难度，而不是直接接高德/SUMO：
  - 增强峰值拥堵倍数和事故影响；
  - 收紧部分时间窗；
  - 提高 static/greedy 对拥堵和延误的暴露；
  - 保持所有算法使用同一数据与随机种子。
- 验收：至少在 `medium` 实例上，ALNS 优于贪心，T-ALNS 不劣于 ALNS，RRD 在动态事件指标上优于 no-dispatch/greedy-dispatch。
- 当前前哨测试建议先看 5 seeds / 120 iterations：该规模能快速暴露趋势，完整排序稳定后再扩大到 10 或 30 seeds。

## 阶段 3：全量实验

推荐在 Intel i5-12600KF 上使用 4-6 个 worker，避免 16 线程全占满导致调度抖动：

```bash
cd code
python experiments/run_main.py --instance medium --seeds 30 --iters 1000 --tmax 600 --parallel 6
python experiments/run_ablation.py --instance medium --seeds 30 --iters 600
python experiments/run_rrd_dispatch.py --instance medium --seeds 30 --iters 600 --tmax 600 --event-types E1_TRAFFIC,E2_URGENT,E4_TIME_RISK,E3_CAPACITY
python experiments/plot_results.py
```

若时间有限，期末汇报可用快速版：

```bash
cd code
python experiments/run_main.py --instance medium --seeds 10 --iters 600 --tmax 300 --parallel 4
python experiments/run_rrd_dispatch.py --instance medium --seeds 10 --iters 500 --tmax 300 --event-iters 100,200,300 --event-types E1_TRAFFIC,E2_URGENT,E4_TIME_RISK
```

已验证的前哨命令：

```bash
cd code
python experiments/run_main.py --instance medium --seeds 5 --iters 120 --tmax 120 --parallel 5
python experiments/run_rrd_dispatch.py --instance medium --seeds 2 --iters 120 --tmax 120 --event-iters 40,80 --event-types E1_TRAFFIC,E2_URGENT
```

## 阶段 4：论文对标与汇报口径

- 不承诺复现论文绝对数值，因为论文使用 Amap + SUMO + TraCI，当前项目使用 OSM 合成交通。
- 汇报重点放在相对趋势、消融贡献、动态事件响应，而不是表格数值完全一致。
- 若趋势仍不一致，作为复现发现汇报：论文结论对交通扰动强度、事件生成机制和实例难度敏感。
- 最终产物：
  - `outputs/processed/main_comparison.csv`
  - `outputs/processed/rrd_dispatch_comparison.csv`
  - `outputs/processed/ablation_table.csv`
  - 图表 `outputs/figures/*.png`
  - 一页“论文结果 vs 本复现结果 vs 差异原因”说明。
