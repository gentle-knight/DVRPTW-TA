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

        valid_mask = (self.free_flow < 9999) & (self.free_flow > 0)
        self._fallback_tt = float(self.free_flow[valid_mask].mean()) if valid_mask.any() else 5.0
        self._fallback_gamma = float(self.tensor[:, :, :, 1][:, :, :][valid_mask].mean()) if valid_mask.any() else 0.3
        self._fallback_eta = float(self.tensor[:, :, :, 2][:, :, :][valid_mask].mean()) if valid_mask.any() else 1.0

    def _safe_index(self, i, j):
        if i >= self.n_nodes or j >= self.n_nodes or i < 0 or j < 0:
            return False, -1, -1
        return True, i, j

    def interval_of(self, minutes):
        h = int(minutes // 60)
        return max(0, min(h, self.n_intervals - 1))

    def travel_time(self, i, j, departure_minutes):
        ok, i, j = self._safe_index(i, j)
        if not ok:
            return self._fallback_tt
        h = self.interval_of(departure_minutes)
        t = float(self.tensor[i, j, h, 0])
        return t if t < 9999 else self._fallback_tt

    def congestion_density(self, i, j, departure_minutes):
        ok, i, j = self._safe_index(i, j)
        if not ok:
            return self._fallback_gamma
        h = self.interval_of(departure_minutes)
        return float(self.tensor[i, j, h, 1])

    def congestion_cost(self, i, j, departure_minutes):
        return self.theta * self.congestion_density(i, j, departure_minutes)

    def reliability_margin(self, i, j, departure_minutes):
        ok, i, j = self._safe_index(i, j)
        if not ok:
            return self._fallback_eta
        h = self.interval_of(departure_minutes)
        return float(self.tensor[i, j, h, 2])

    def adjusted_time(self, i, j, departure_minutes):
        return self.travel_time(i, j, departure_minutes) + self.beta * self.reliability_margin(i, j, departure_minutes)

    def free_flow_time(self, i, j):
        ok, i, j = self._safe_index(i, j)
        if not ok:
            return self._fallback_tt
        return float(self.free_flow[i, j])

    def interpolated_travel_time(self, i, j, departure_minutes):
        """Eq.37: piecewise-linear interpolated travel time for rollout.

        t_ij^rollout(T_i + s) = t_ij^(r) + s/Δt * (t_ij^(r+1) - t_ij^(r))
        If the next interval is unavailable, hold-last-value.
        """
        interval_size = 60
        h = int(departure_minutes // interval_size)
        frac = (departure_minutes % interval_size) / interval_size

        ok, i, j = self._safe_index(i, j)
        if not ok:
            return self._fallback_tt

        h = max(0, min(h, self.n_intervals - 1))
        t_now = float(self.tensor[i, j, h, 0])
        if t_now >= 9999:
            t_now = self._fallback_tt

        if h + 1 < self.n_intervals:
            t_next = float(self.tensor[i, j, h + 1, 0])
            if t_next >= 9999:
                t_next = t_now
        else:
            t_next = t_now

        return t_now + frac * (t_next - t_now)
