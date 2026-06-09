"""
Traffic flow data integration (Sect 3.2, Eqs. 8–10).

Loads precomputed traffic tensor [48, 48, 12, 3] and provides O(1) lookup:
  dim 0: travel time t_ij^(h) in minutes
  dim 1: congestion density γ_ij^(h) ∈ [0, 1]
  dim 2: reliability margin η_ij^(h) in minutes

Distinguishes γ (density) from ρ = θ·γ (cost entering objective).
"""

from pathlib import Path
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TENSOR_PATH = PROJECT_ROOT / 'datasets' / 'traffic' / 'traffic_tensor.npz'


class TrafficManager:

    def __init__(self, theta=1.0, beta=0.5):
        data = np.load(TENSOR_PATH)
        self.tensor = data['tensor'].astype(np.float32)
        self.free_flow = data['travel_time_free']
        self.lengths = data['total_length']

        self.n_nodes = self.tensor.shape[0]
        self.n_intervals = self.tensor.shape[2]
        self.theta = theta
        self.beta = beta

        self.HOUR_START = 6

    def interval_of(self, minutes):
        h = int(minutes // 60)
        return max(0, min(h, self.n_intervals - 1))

    def travel_time(self, i, j, departure_minutes):
        """t_ij(T_i) — Eq.8"""
        h = self.interval_of(departure_minutes)
        return float(self.tensor[i, j, h, 0])

    def congestion_density(self, i, j, departure_minutes):
        """γ_ij^(h) ∈ [0,1] — raw density from tensor, Eq.9"""
        h = self.interval_of(departure_minutes)
        return float(self.tensor[i, j, h, 1])

    def congestion_cost(self, i, j, departure_minutes):
        """ρ_ij(T_i) = θ · γ_ij^(h) — Eq.9, enters objective weighted by λ₂"""
        return self.theta * self.congestion_density(i, j, departure_minutes)

    def reliability_margin(self, i, j, departure_minutes):
        """η_ij^(h) — Eq.10"""
        h = self.interval_of(departure_minutes)
        return float(self.tensor[i, j, h, 2])

    def adjusted_time(self, i, j, departure_minutes):
        """t_ij + β·η_ij — Eq.10"""
        return self.travel_time(i, j, departure_minutes) + self.beta * self.reliability_margin(i, j, departure_minutes)

    def free_flow_time(self, i, j):
        return float(self.free_flow[i, j])
