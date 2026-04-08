import numpy as np

class FreedmanDistanceLadder:
    """Topological Drift Auditor via Standard Candle Anchoring."""
    def map_distance_ladder(self, Vt_reduced, S_reduced, standard_idx=0):
        V_standard = Vt_reduced[:, standard_idx]
        diff = Vt_reduced - V_standard[:, np.newaxis]
        weighted_diff_sq = (diff ** 2) * (S_reduced[:, np.newaxis] ** 2)
        return np.sqrt(np.sum(weighted_diff_sq, axis=0))
