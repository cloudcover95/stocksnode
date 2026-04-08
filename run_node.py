# path: run_node.py
import time, threading, numpy as np, pandas as pd
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.web3node.ticker_hunter import Web3TickerHunter
from src.web3node.financial_tensor import Web3FinancialTensor
from src.telemetry import jcllc_monitor

WIDE_NET = ["BTC-USD", "ETH-USD", "SOL-USD", "SPY", "QQQ", "AAPL", "NVDA", "TSLA", "LINK-USD", "DOT-USD"]
active_list = []

app = FastAPI(title="JuniorCloud LLC // stocksnode V337")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

engine = Web3FinancialTensor()

@app.get("/api/state")
async def get_state():
    buffer = jcllc_monitor.buffers.get("WEB3_FINANCE", [])
    if not buffer: return {"status": "DATA_VOID"}
    slice_size = len(active_list) if active_list else 5
    return buffer[-slice_size:]

def sovereign_pulse_loop():
    global active_list
    print("[⚡] JuniorCloud stocksnode V337: Sovereign Ignition (Py3.9 Compat)")
    
    hunter = Web3TickerHunter(WIDE_NET, engine)
    active_list = hunter.hunt_and_backfill()
    
    if not active_list:
        active_list = ["BTC-USD", "ETH-USD", "SPY"]
    
    while True:
        try:
            import yfinance as yf
            live_data = yf.download(active_list, period="1d", interval="1m", group_by='ticker', progress=False)
            
            for ticker in active_list:
                try:
                    # MultiIndex handling for single vs many tickers
                    if isinstance(live_data.columns, pd.MultiIndex):
                        t_df = live_data[ticker].dropna()
                    else:
                        t_df = live_data.dropna()
                except KeyError:
                    t_df = live_data.dropna()

                if t_df.empty: continue
                
                C, H, L = t_df['Close'].values.reshape(1, -1), t_df['High'].values.reshape(1, -1), t_df['Low'].values.reshape(1, -1)
                metrics = engine.process_financial_manifold(H, L, C)
                
                jcllc_monitor.ingest_node_state("WEB3_FINANCE", {
                    "ticker": ticker,
                    "spot": float(metrics["spot"][-1]),
                    "z_score": float(metrics["z_score"][-1]),
                    "q_mark": float(metrics["q_mark"][-1]),
                    "liq_align": float(metrics["turtle_alignment"][-1]),
                    "historical": 0
                })
            print(f"[+] {time.strftime('%H:%M:%S')} | Pulse Recorded | {active_list}")
            time.sleep(60)
        except Exception as e:
            print(f"[!] Sovereign Pulse Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=sovereign_pulse_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8080)