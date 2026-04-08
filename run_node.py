import time, threading, numpy as np, pandas as pd
import yfinance as yf
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from src.web3node.financial_tensor import Web3FinancialTensor
from src.telemetry import jcllc_monitor

# --- INFRASTRUCTURE ---
TICKERS = ["BTC-USD", "ETH-USD", "SOL-USD", "SPY", "QQQ"]
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
engine = Web3FinancialTensor()

class SovereignIngress:
    def __init__(self, tickers):
        self.tickers = tickers
        self.prices = np.random.uniform(100, 65000, len(tickers))

    def fetch_tensor(self):
        try:
            # Attempt real-world ingress
            df = yf.download(self.tickers, period="1d", interval="1m", progress=False)['Close']
            if df.empty: raise ValueError("YF_VOID")
            return df.tail(60).values.T # Shape (N, T)
        except:
            # Simulator Fallback (OHLC Walk)
            drift = np.random.normal(1.0, 0.002, (len(self.prices), 60))
            C = self.prices[:, np.newaxis] * np.cumprod(drift, axis=1)
            self.prices = C[:, -1]
            return C

ingress = SovereignIngress(TICKERS)

@app.get("/api/state")
async def get_state():
    buffer = jcllc_monitor.buffers.get("WEB3_FINANCE", [])
    if not buffer: return {"status": "DATA_VOID"}
    return buffer[-len(TICKERS):] # Return latest pulse for all tickers

def logic_loop():
    print("[⚡] JuniorCloud stocksnode V321: Ignition")
    while True:
        C = ingress.fetch_tensor()
        H, L = C * 1.002, C * 0.998
        metrics = engine.process_financial_manifold(H, L, C)
        
        for i, t in enumerate(TICKERS):
            jcllc_monitor.ingest_node_state("WEB3_FINANCE", {
                "ticker": t, "spot": float(metrics["spot"][i]),
                "z_score": float(metrics["z_score"][i]),
                "q_mark": float(metrics["q_mark"][i]),
                "liq_align": float(metrics["turtle_alignment"][i])
            })
        print(f"[+] {time.strftime('%H:%M:%S')} | ETCH Pulse | Buffer: {len(jcllc_monitor.buffers['WEB3_FINANCE'])}")
        time.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=logic_loop, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8080)
