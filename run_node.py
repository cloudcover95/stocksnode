import time, numpy as np
from src.web3node.financial_tensor import Web3FinancialTensor
from src.telemetry import jcllc_monitor

TICKERS = ["BTC-USD", "ETH-USD", "SOL-USD", "SPY", "QQQ"]

class MarketSimulator:
    def __init__(self, count):
        self.prices = np.random.uniform(100, 65000, count)

    def generate_ohlc(self):
        drift = np.random.normal(1.0, 0.002, (len(self.prices), 60))
        C = self.prices[:, np.newaxis] * np.cumprod(drift, axis=1)
        self.prices = C[:, -1]
        H, L = C * 1.005, C * 0.995
        return H, L, C

def ignite():
    print("[⚡] JuniorCloud stocksnode V320: Ignition")
    engine = Web3FinancialTensor()
    sim = MarketSimulator(len(TICKERS))
    
    try:
        while True:
            H, L, C = sim.generate_ohlc()
            # Standardized method call to fix AttributeError
            metrics = engine.process_financial_manifold(H, L, C)
            
            for i, t in enumerate(TICKERS):
                jcllc_monitor.ingest_node_state("WEB3_FINANCE", {
                    "ticker": t, "spot": float(metrics["spot"][i]),
                    "z_score": float(metrics["z_score"][i]),
                    "q_mark": float(metrics["q_mark"][i]),
                    "liq_align": float(metrics["turtle_alignment"][i])
                })
            print(f"[+] {time.strftime('%H:%M:%S')} | ETCH Pulse | Avg Q: {np.mean(metrics['q_mark']):.4f}")
            time.sleep(10) # 10s intervals for HUD responsiveness
    except KeyboardInterrupt:
        jcllc_monitor.flush("WEB3_FINANCE")

if __name__ == "__main__":
    ignite()
