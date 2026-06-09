"""
Frequency memory for search diversification (Sect 3.3.2, Eqs.24–25, 32–33).

F_cv[i,k]: how often customer i assigned to vehicle k. Biases toward
           underrepresented assignments.
F_tp[i,j]: how often customer i appears at position j in any route.

Congestion-weighted: updates multiplied by (1 + sum of ρ on incoming arcs).
"""

import numpy as np


class FrequencyMemory:

    def __init__(self, n_customers, n_vehicles,
                 normalization_factor=2.0, normalization_interval=50):
        self.n_customers = n_customers
        self.n_vehicles = n_vehicles
        self.F_cv = np.zeros((n_customers + 1, n_vehicles), dtype=np.float32)
        self.F_tp = np.zeros((n_customers + 1, n_customers + 1), dtype=np.float32)

        self.norm_factor = normalization_factor
        self.norm_interval = normalization_interval
        self.iter_since_norm = 0

    def update(self, solution, congestion_weights=None):
        for v, route in enumerate(solution.routes):
            customers = route.customer_nodes()
            for pos, cid in enumerate(customers):
                weight = 1.0
                if congestion_weights is not None and v < len(congestion_weights):
                    weight += congestion_weights[v]

                self.F_cv[cid, v] += weight
                self.F_tp[cid, pos] += 1.0

        self.iter_since_norm += 1
        if self.iter_since_norm >= self.norm_interval:
            self._normalize()

    def _normalize(self):
        self.F_cv = np.floor(self.F_cv / self.norm_factor)
        self.F_tp = np.floor(self.F_tp / self.norm_factor)
        self.iter_since_norm = 0

    def customer_vehicle_std(self):
        return float(np.std(self.F_cv))

    def least_frequent_assignment(self, customer_id):
        return float(np.min(self.F_cv[customer_id]))

    def mean_frequency(self):
        return float(np.mean(self.F_cv))

    def diversification_score(self, customer_id, vehicle_id):
        total = self.F_cv[customer_id].sum()
        if total < 1e-6:
            return 0.0
        return float(1.0 / (1.0 + self.F_cv[customer_id, vehicle_id]))

    def resize(self, n_customers):
        if n_customers <= self.n_customers:
            return
        old_cv = self.F_cv
        old_tp = self.F_tp
        old_n = self.n_customers
        self.F_cv = np.zeros((n_customers + 1, self.n_vehicles), dtype=np.float32)
        self.F_tp = np.zeros((n_customers + 1, n_customers + 1), dtype=np.float32)
        self.F_cv[:old_n + 1, :] = old_cv
        self.F_tp[:old_n + 1, :old_n + 1] = old_tp
        self.n_customers = n_customers
