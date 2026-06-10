"""
Move-based Tabu list (Sect 3.3.2, Eqs.22, 31).

Stores recent destroy-repair operations as (C_removed, d_op, r_op, iter).
A new move is tabu if it overlaps with a stored move beyond threshold μ
and the stored move is still within its tenure τ_move.

Tenure adapts: increases when search stagnates, decreases on improvement.
"""


class MoveTabuList:

    def __init__(self, tenure=7, tenure_min=3, tenure_max=15,
                 overlap_threshold=0.5, stall_limit=20):
        self.tenure = tenure
        self.tenure_min = tenure_min
        self.tenure_max = tenure_max
        self.overlap_threshold = overlap_threshold
        self.stall_limit = stall_limit

        self.entries = []
        self.stall_count = 0

    def is_tabu(self, removed_set, current_iter, d_op=None, r_op=None):
        r_set = set(removed_set)
        n = len(r_set)
        if n == 0:
            return False

        for c_set, old_d_op, old_r_op, t_iter in self.entries:
            if current_iter - t_iter > self.tenure:
                continue
            if d_op is not None and old_d_op != d_op:
                continue
            if r_op is not None and old_r_op != r_op:
                continue
            c_len = len(c_set)
            overlap = len(r_set & c_set)
            threshold = self.overlap_threshold * min(n, c_len)
            if overlap >= threshold:
                return True
        return False

    def add(self, removed_set, d_op, r_op, current_iter):
        self.entries.append((set(removed_set), d_op, r_op, current_iter))
        self._evict(current_iter)

    def report_improvement(self):
        self.stall_count = 0
        self.tenure = max(self.tenure_min, self.tenure - 1)

    def report_stagnation(self):
        self.stall_count += 1
        if self.stall_count >= self.stall_limit:
            self.tenure = min(self.tenure_max, self.tenure + 1)
            self.stall_count = 0

    def _evict(self, current_iter):
        self.entries = [
            e for e in self.entries
            if current_iter - e[3] <= self.tenure_max + 10
        ]

    @property
    def size(self):
        return len(self.entries)
