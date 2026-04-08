import yfinance as yf
import numpy as np
import pandas as pd
import time
from src.web3node.financial_tensor import Web3FinancialTensor
from src.telemetry import jcllc_monitor

class Web3TickerHunter:
    """
    V325 Ticker Hunter: Scans a wide manifold to identify High-Q candidates.
    Maximizes yfinance efficiency via batch downloads.
    """
    def __init__(self, watch_list):
        self.watch_list = watch_list
        self.engine = Web3FinancialTensor()

    def hunt_and_backfill(self, period="60d", interval="1h"):
        print(f"[*] INITIATING WIDE-NET SCAN: {len(self.watch_list)} Assets...")
        
        try:
            # Single batch request to minimize IP overhead
            data = yf.download(self.watch_list, period=period, interval=interval, group_by='ticker', progress=False)
            
            high_q_candidates = []
            
            for ticker in self.watch_list:
                ticker_data = data[ticker].dropna()
                if len(ticker_data) < 30: continue
                
                # Format Tensors
                C = ticker_data['Close'].values.reshape(1, -1)
                H = ticker_data['High'].values.reshape(1, -1)
                L = ticker_data['Low'].values.reshape(1, -1)
                
                # Inference
                metrics = self.engine.process_financial_manifold(H, L, C)
                
                q = metrics["q_mark"][-1]
                z = metrics["z_score"][-1]
                
                # 60-Day Historical Etching (Ledgering the entire history)
                for t_idx in range(len(ticker_data)):
                    jcllc_monitor.ingest_node_state("WEB3_FINANCE", {
                        "ticker": ticker,
                        "spot": float(C[0, t_idx]),
                        "z_score": float(metrics["z_score"][t_idx]),
                        "q_mark": float(metrics["q_mark"][t_idx]),
                        "historical": 1
                    })
                
                # Hunter Logic: Find structural anomalies
                if q > 0.70:
                    high_q_candidates.append(ticker)
                    print(f"[!] HUNTER_HIT: {ticker} | Q: {q:.4f} | Z: {z:.2f}")

            return high_q_candidates

        except Exception as e:
            print(f"[ERR] Hunter Scan Failed: {e}")
            return []