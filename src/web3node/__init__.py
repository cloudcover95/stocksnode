from .financial_tensor import Web3FinancialTensor
from .llm_bridge import LocalLLMBridge

class SovereignAgentInterface:
    """
    The 'Lever' for AI Agents. 
    Exposes simplified logic gates for autonomous decision making.
    """
    def __init__(self):
        self.math = Web3FinancialTensor()
        self.bridge = LocalLLMBridge()

    def get_alpha_signal(self, H, L, C):
        """Collapses the 5D manifold into a single actionable string for an LLM."""
        state = self.math.process_financial_manifold(H, L, C)
        # Returns a 'Human-Readable' state for LLM injection
        return f"Z:{state['z_score'][-1]:.2f} | Q:{state['q_mark'][-1]:.2f} | Liq:{state['turtle_alignment'][-1]:.2f}"

__all__ = ["Web3FinancialTensor", "LocalLLMBridge", "SovereignAgentInterface"]