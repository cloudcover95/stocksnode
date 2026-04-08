# /JuniorCloud/stocksnode/run_node.py
import time
import numpy as np
from src.web3node import Web3FinancialTensor
from src.telemetry import jcllc_monitor

TICKERS = ["BTC-USD", "ETH-USD", "SOL-USD", "SPY", "QQQI"]

class MarketSimulator:
    def __init__(self, count):
        self.prices = np.random.uniform(100, 50000, count)

    def generate_candle_batch(self):
        """Simulates 60 periods of OHLC candle action."""
        # Random walk for the Close price
        volatility = 0.002 
        drift = np.random.normal(1.0, volatility, (len(self.prices), 60))
        C = self.prices[:, np.newaxis] * np.cumprod(drift, axis=1)
        
        # Update baseline for next pulse
        self.prices = C[:, -1]
        
        H = C * (1 + np.random.uniform(0, 0.005, C.shape))
        L = C * (1 - np.random.uniform(0, 0.005, C.shape))
        return H, L, C

def ignite():
    print("[*] IGNITION: V306 Sovereign Simulation Active")
    math_core = Web3FinancialTensor()
    sim = MarketSimulator(len(TICKERS))
    
    try:
        while True:
            # 1. Generate Variable Candle Action
            H, L, C = sim.generate_candle_batch()
            
            # 2. Execute Manifold Inference
            metrics = math_core.process_financial_manifold(H, L, C)
            
            # 3. Ingest State Vectors to Data Lake
            for i, t in enumerate(TICKERS):
                state = {
                    "ticker": t,
                    "spot": float(metrics["spot"][i]),
                    "z_score": float(np.round(metrics["z_score"][i], 2)),
                    "q_mark": float(metrics["q_mark"][i]),
                    "liq_align": float(metrics["turtle_alignment"][i])
                }
                jcllc_monitor.ingest_node_state("WEB3_FINANCE", state)
                
            print(f"[+] {time.strftime('%H:%M:%S')} | Candle Etched | Delta: {np.mean(np.diff(C[:, -1])):.4f}")
            time.sleep(60) # 1-Minute Pulse
            
    except KeyboardInterrupt:
        jcllc_monitor.flush_to_lake("WEB3_FINANCE")

if __name__ == "__main__":
    ignite()