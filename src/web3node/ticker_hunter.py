# src/web3node/ticker_hunter.py
import time
import numpy as np
from pathlib import Path
import pandas as pd
from src.telemetry import jcllc_monitor

class TickerHunter:
    """
    Sovereign Web3Node Ticker Hunter
    Scans for high Q-Mark signals and moves assets into Yield Farming Range registry.
    Writes dedicated ledgers on signal events.
    """

    def __init__(self, q_threshold: float = 0.85, yield_farm_window: int = 20):
        self.q_threshold = q_threshold
        self.yield_farm_window = yield_farm_window
        self.yield_farm_registry = []   # Active yield farming candidates
        self.hunter_ledgers_path = Path("vault/hunter_ledgers")
        self.hunter_ledgers_path.mkdir(parents=True, exist_ok=True)

    def hunt(self, metrics: dict, tickers: list) -> dict:
        """Run hunt on latest manifold metrics."""
        signals = []
        for i, ticker in enumerate(tickers):
            q = float(metrics["q_mark"][i])
            if q > self.q_threshold:
                signal = {
                    "ticker": ticker,
                    "timestamp": time.time(),
                    "q_mark": q,
                    "z_score": float(metrics["z_score"][i]),
                    "spot": float(metrics["spot"][i]),
                    "liq_align": float(metrics["turtle_alignment"][i]),
                    "status": "YIELD_FARM_CANDIDATE"
                }
                signals.append(signal)
                
                # Move to Yield Farming Registry
                self.yield_farm_registry.append(signal)
                if len(self.yield_farm_registry) > self.yield_farm_window:
                    self.yield_farm_registry.pop(0)

                # Write dedicated hunter ledger
                self._write_hunter_ledger(signal)

        # Ingest summary to main telemetry
        if signals:
            jcllc_monitor.ingest_node_state("HUNTER_SIGNALS", {
                "signal_count": len(signals),
                "tickers": [s["ticker"] for s in signals],
                "avg_q": np.mean([s["q_mark"] for s in signals])
            })

        return {
            "signals": signals,
            "yield_farm_count": len(self.yield_farm_registry),
            "yield_farm_tickers": [s["ticker"] for s in self.yield_farm_registry]
        }

    def _write_hunter_ledger(self, signal: dict):
        """Write high-signal event to dedicated ledger (CSV + Parquet)."""
        ts = int(time.time())
        df = pd.DataFrame([signal])
        
        # CSV ledger
        csv_path = self.hunter_ledgers_path / f"hunter_signal_{ts}.csv"
        df.to_csv(csv_path, index=False)
        
        # Also flush to main telemetry lake
        jcllc_monitor.flush_to_lake("HUNTER_SIGNALS")

    def get_yield_farm_registry(self):
        return self.yield_farm_registry