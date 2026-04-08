import numpy as np

class SovereignOmniKernel:
    """V321 Hard-Fork: Pure SVD Mathematical Core."""
    def __init__(self, variance_retention=0.95):
        self.variance_retention = variance_retention

    def compute_svd_mesh(self, X):
        """X shape: (N, T) - N nodes, T time steps."""
        mu = np.mean(X, axis=1, keepdims=True)
        X_centered = X - mu
        U, S, Vt = np.linalg.svd(X_centered, full_matrices=False)
        return U, S, Vt
