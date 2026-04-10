import numpy as np

class Web3FinancialTensor:
    def __init__(self, h_bar_mkt=0.01):
        self.h_bar_mkt = h_bar_mkt
        self._prev_q = None

    def process_manifold(self, C: np.ndarray, H: np.ndarray, L: np.ndarray):
        if C.ndim == 1: C = C.reshape(1, -1)
        N, T = C.shape
        means = np.mean(C, axis=1, keepdims=True)
        stds = np.maximum(np.std(C, axis=1, keepdims=True), 1e-8)
        current_spots = C[:, -1]
        
        Z_scores = (C - means) / stds
        returns = np.diff(C, axis=1) / np.maximum(C[:, :-1], 1e-8)
        base_vols = np.std(returns, axis=1)
        recent_deltas = np.std(returns[:, -10:], axis=1) if T > 10 else base_vols
        
        q_marks = 1.0 - np.exp(-np.abs(Z_scores[:, -1]) * (recent_deltas / np.maximum(base_vols, self.h_bar_mkt)))
        turtle_alignment = (current_spots - L[:, -1]) / (H[:, -1] - L[:, -1] + 1e-8)
        
        return {
            "spot": current_spots, "z_score": Z_scores[:, -1],
            "q_mark": q_marks, "turtle_alignment": turtle_alignment
        }

    def compute_delta_q(self, current_q: np.ndarray) -> np.ndarray:
        if self._prev_q is None:
            self._prev_q = current_q
            return np.zeros_like(current_q)
        delta = current_q - self._prev_q
        self._prev_q = current_q
        return delta
