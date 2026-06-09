# Known Differences from Paper

## Implemented as Simplifications

| Item | Paper | Our Implementation | Reason |
|------|-------|-------------------|--------|
| **RRD threading** | Thread 1 (optimization) + Thread 2 (event monitoring) | Single-thread synchronous | Phase 3D design choice; events injected at predetermined iterations (250/500/750) |
| **E3 capacity violation** | 4 event types (E1-E4) | 3 event types (E1/E2/E4) | E3 handled implicitly by capacity constraints in repair |
| **Eq.37 linear interpolation** | Piecewise-linear interpolation for rollout | Piecewise-constant lookup | 60-min horizon limits impact |
| **Eq.42-43 adaptive horizon** | $H_{rollout}$ and $N_{sim}$ adapt to urgency | Fixed horizon=60min, single simulation | Synchronous version limitation |
| **Eq.39 composite weights** | $\omega_1=0.4, \omega_2=0.3, \omega_3=0.3$ | All weights = 1.0 | Equivalent to equal weighting |
| **Eq.16-17 insertion cost** | Incremental cost delta formula | Full forward propagation | More robust; low computational overhead for n=47 |

## Data Generation Differences

| Item | Paper | Our Implementation | Reason |
|------|-------|-------------------|--------|
| **Traffic data source** | Gaode Maps API + SUMO v1.19 simulation | Synthetic OSM-based profiles | Public API access unavailable |
| **Eq.10 $\eta$ generation** | Empirical standard deviations from fleet data | Multiplicative: $\eta = t \times variability$ | Synthetic approximation (usage layer is correct additive form) |
| **Eq.8 travel time** | Pure piecewise-constant $t_{ij}^{(h)}$ | Road-type-weighted peak amplification added | Enhances realism for OSM-based synthesis |
| **Road classification** | 4 classes (paper: network-level) | 5 classes in path composition (adds tertiary) | Path-level granularity; paper 4-class scheme used in network-level stats |
| **Evening time windows** | 17:00-20:00 | Traffic data only to 18:00 | Paper limitation; last interval values used as fallback |
| **Study area traffic data** | Paper cites 2256 directed segments, 4 road types, 18/34/41/7% split | OSM road network: verified at network level with comparable distribution | Single-run OSM download; percentages vary based on exact OSM snapshot |

## Experimental Differences

| Item | Paper | Our Implementation | Reason |
|------|-------|-------------------|--------|
| **Oracle-Traffic-Perfect** | Baseline with perfect traffic foresight | Not yet implemented | Requires separate traffic generation with oracle knowledge |
| **SOTA comparison** | Pisinger & Ropke ALNS comparison (p<0.001) | Not implemented | External benchmark beyond scope of core reproduction |
| **30 runs** | All experiments ran 30 seeds | Runner supports N_SEEDS=30 | Default ready; user sets seed count |
