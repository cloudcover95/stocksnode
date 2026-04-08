# path: src/web3node/ticker_hunter.py
import yfinance as yf
import numpy as np
import pandas as pd
from typing import List
from src.telemetry import jcllc_monitor

class Web3TickerHunter:
    """
    V338 Sovereign Hunter: Python 3.9 Compatible.
    Unifies wide-net scanning and historical Data Lake priming.
    """
    def __init__(self, tickers: List[str], engine):
        self.tickers = tickers
        self.engine = engine

    def hunt_and_backfill(self, period: str = "60d", interval: str = "1h") -> List[str]:
        """
        Ingests 60-day history, ledgers the manifold, and returns 
        candidates with High-Q superposition.
        """
        print(f"[*] INITIATING SOVEREIGN SCAN: {len(self.tickers)} Assets...")
        high_q_candidates = []
        
        try:
            # Batch download to maximize API efficiency
            data = yf.download(self.tickers, period=period, interval=interval, group_by='ticker', progress=False)
            
            for ticker in self.tickers:
                # Handle yfinance single-ticker vs multi-ticker dataframe disparity
                if len(self.tickers) > 1:
                    t_df = data[ticker].dropna()
                else:
                    t_df = data.dropna()
                
                if len(t_df) < 20: continue 
                
                # Format Tensors
                C = t_df['Close'].values.reshape(1, -1)
                H = t_df['High'].values.reshape(1, -1)
                L = t_df['Low'].values.reshape(1, -1)
                
                # Inference
                metrics = self.engine.process_financial_manifold(H, L, C)
                
                # Data Lake Priming
                for t_idx in range(len(t_df)):
                    jcllc_monitor.ingest_node_state("WEB3_FINANCE", {
                        "ticker": ticker,
                        "spot": float(C[0, t_idx]),
                        "z_score": float(metrics["full_z_history"][0, t_idx]),
                        "q_mark": float(metrics["q_mark"][0]),
                        "historical": 1
                    })
                
                # Hunter Logic
                current_q = metrics["q_mark"][-1]
                if current_q > 0.70:
                    high_q_candidates.append(ticker)
                    print(f"[!] HUNTER_HIT: {ticker} | Q: {current_q:.4f}")

            print(f"[+] Backfill Complete. Candidates Found: {len(high_q_candidates)}")
            return high_q_candidates

        except Exception as e:
            print(f"[ERR] Sovereign Hunt Failed: {e}")
            return []