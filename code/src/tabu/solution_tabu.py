"""
Solution-based Tabu memory (Sect 3.3.2, Eqs.23-24).

Uses polynomial hashing over consecutive customer pairs to fingerprint
solutions. Circular buffer rejects revisits within tenure τ_sol.

H(S) = Σ_{routes} hash(pairs) mod P
"""

import math


def hash_solution(solution):
    BASE = 47
    P1 = 1000003
    P2 = 1000033
    MOD = 10**9 + 7

    h = 0
    for route in solution.routes:
        nodes = route.nodes
        for i in range(len(nodes) - 1):
            a, b = nodes[i], nodes[i + 1]
            pair_hash = (a * P1 + b * P2) % MOD
            if i == 0:
                route_h = pair_hash
            else:
                route_h = (route_h * BASE + pair_hash) % MOD
        h = (h + route_h) % MOD
    return h


class SolutionTabuMemory:

    def __init__(self, tenure=15, n_customers=47):
        self.tenure = tenure
        max_log = 2 ** math.ceil(math.log2(max(1, n_customers)))
        self.max_size = min(1000, max_log)
        self.buffer = []
        self.iter_counter = 0

    def is_tabu(self, solution, current_iter):
        h = hash_solution(solution)
        for stored_hash, t_iter in self.buffer:
            if h == stored_hash and current_iter - t_iter <= self.tenure:
                return True
        return False

    def add(self, solution, current_iter):
        h = hash_solution(solution)
        self.buffer.append((h, current_iter))
        while len(self.buffer) > self.max_size:
            self.buffer.pop(0)

    @property
    def size(self):
        return len(self.buffer)
