import numpy as np

class SystemicAuditor:
    """Evaluates manifold health via Singular Value Decomposition."""
    @staticmethod
    def calculate_coherence(matrix):
        """
        Calculates the ratio of the primary singular value to the sum.
        C = sigma_1 / sum(sigma_i)
        """
        if matrix.size == 0: return 0.0
        # Center the matrix
        matrix_centered = matrix - np.mean(matrix, axis=0)
        _, S, _ = np.linalg.svd(matrix_centered, full_matrices=False)
        
        coherence = S[0] / (np.sum(S) + 1e-9)
        return round(float(coherence), 4)

    @staticmethod
    def get_status(coherence):
        if coherence > 0.80: return "OPTIMAL"
        if coherence > 0.50: return "NOMINAL"
        return "CRITICAL_DRIFT"