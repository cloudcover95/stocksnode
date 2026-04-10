from src.stocksnode.engines.profitability_matrix import ProfitabilityIdentityMatrix
from src.stocksnode.telemetry.global_registry import jcllc_registry

class TickerHunter:
    def __init__(self, q_threshold):
        self.q_threshold = q_threshold
        self.profit_matrix = ProfitabilityIdentityMatrix()

    def hunt(self, metrics: dict, active_tickers: list, delta_q_array: list):
        signals = 0
        for i, ticker in enumerate(active_tickers):
            q, spot, liq = metrics["q_mark"][i], metrics["spot"][i], metrics["turtle_alignment"][i]
            if q > self.q_threshold or abs(delta_q_array[i]) > 0.10:
                profit_id = self.profit_matrix.evaluate_singularity(ticker, q, spot, liq)
                jcllc_registry.ingest("HUNTER_SIGNALS", profit_id)
                signals += 1
        return {"signals_found": signals}
