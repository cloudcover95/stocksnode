import time, threading, numpy as np
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.web3node.ticker_hunter import Web3TickerHunter
from src.web3node.financial_tensor import Web3FinancialTensor
from src.telemetry import jcllc_monitor

# --- CONFIG ---
WIDE_NET = ["BTC-USD", "ETH-USD", "SOL-USD", "SPY", "QQQ", "AAPL", "NVDA", "TSLA", "LINK-USD", "DOT-USD"]
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"])

@app.get("/api/state")
async def get_state():
    buffer = jcllc_monitor.buffers.get("WEB3_FINANCE", [])
    if not buffer: return {"status": "DATA_VOID"}
    return buffer[-20:] # Return most recent 20 state vectors

def master_loop():
    print("[⚡] JuniorCloud stocksnode V325: Sovereign Ignition")
    
    # 1. 60-Day Historical Backfill & Active Candidate Identification
    hunter = Web3TickerHunter(WIDE_NET)
    active_list = hunter.hunt_and_backfill()
    
    if not active_list: active_list = ["BTC-USD", "SPY"] # Default anchors
    
    engine = Web3FinancialTensor()
    print(f"[*] Transitioning to Live Pulse on: {active_list}")

    while True:
        try:
            # 2. Live Pulse (Active List Only to minimize pings)
            import yfinance as yf
            live_data = yf.download(active_list, period="1d", interval="1m", group_by='ticker', progress=False)
            
            for ticker in active_list:
                t_df = live_data[ticker].dropna()
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
            
            print(f"[+] {time.strftime('%H:%M:%S')} | Live Pulse Recorded | Lake Active")
            time.sleep(60)
            
        except Exception as e:
            print(f"[!] Pulse Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    threading.Thread(target=master_loop, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8080)
