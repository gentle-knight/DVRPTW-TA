# T-ALNS-RRD: Dynamic Urban Last-Mile Delivery Optimization

Reproduction of *"Optimizing urban last mile delivery efficiency through dynamic vehicle routing heuristics and traffic flow analysis"* (Liu & Wang).

## Architecture

```
DVRPTW-TA (Eq.1-7)    ←→ solution.py
  ├─ Traffic tensor     ←→ traffic_manager.py + traffic_tensor.npz
  ├─ ALNS (Algorithm 1) ←→ core/alns.py
  ├─ T-ALNS (Algorithm 2) ←→ tabu/t_alns.py + move/ solution/ frequency/ aspiration/ diversification
  └─ T-ALNS-RRD (Algorithm 3) ←→ dispatch/t_alns_rrd.py + events/ candidates/ rollout/ dispatch
```

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Generate datasets (one-time)
python datasets/network/download_osm_network.py
python datasets/customers/select_nodes.py
python datasets/traffic/generate_traffic.py

# Run main experiment (5 algorithms × 30 seeds)
python experiments/run_main.py

# Generate figures
python experiments/plot_results.py
```

## Formula → Code Mapping

| Paper | Code |
|-------|------|
| Eq.1 objective | `src/core/solution.py: Solution.compute_cost()` |
| Eq.8–10 traffic | `src/traffic/traffic_manager.py` |
| Eq.18–21 ALNS | `src/core/alns.py: run_alns()` |
| Eq.22–33 Tabu | `src/tabu/` (move/ solution/ frequency/ aspiration/ diversification) |
| Algorithm 1 ALNS | `src/core/alns.py` |
| Algorithm 2 T-ALNS | `src/tabu/t_alns.py` |
| Algorithm 3 T-ALNS-RRD | `src/dispatch/t_alns_rrd.py` |

## Known Differences from Paper

See `docs/differences_from_paper.md`.

## License

MIT
