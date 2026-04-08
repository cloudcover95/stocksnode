# path: /Users/nico/Documents/JuniorCloud/stocksnode/run_node.py
import time, threading, numpy as np, pandas as pd
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.web3node.ticker_hunter import Web3TickerHunter
from src.web3node.financial_tensor import Web3FinancialTensor
from src.telemetry import jcllc_monitor

# --- INFRASTRUCTURE CONFIG ---
# The Hunter scans the Wide Net; the Node pulses the Active List.
WIDE_NET = ["BTC-USD", "ETH-USD", "SOL-USD", "SPY", "QQQ", "AAPL", "NVDA", "TSLA", "LINK-USD", "DOT-USD"]
active_list = [] # Dynamically populated by the Hunter

app = FastAPI(title="JuniorCloud LLC // stocksnode V335")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Initialize Math Engine early to pass into the Hunter
engine = Web3FinancialTensor()

@app.get("/api/state")
async def get_state():
    """Dashboard Ingress: Returns the latest state for the active watch-list."""
    buffer = jcllc_monitor.buffers.get("WEB3_FINANCE", [])
    if not buffer: return {"status": "DATA_VOID"}
    
    # Dynamically slice based on the current size of the active list
    slice_size = len(active_list) if active_list else 5
    return buffer[-slice_size:]

def sovereign_pulse_loop():
    global active_list
    print("[⚡] JuniorCloud stocksnode V335: Sovereign Ignition")
    
    # 1. Wide-Net Scan & Historical Backfill (Priming the Quartz Lake)
    hunter = Web3TickerHunter(WIDE_NET, engine)
    active_list = hunter.hunt_and_backfill()
    
    # Fallback if no High-Q candidates are found
    if not active_list:
        print("[!] No High-Q candidates found. Defaulting to Core Anchors.")
        active_list = ["BTC-USD", "ETH-USD", "SPY"]
    
    print(f"[*] Transitioning to Live Pulse on: {active_list}")

    while True:
        try:
            import yfinance as yf
            # Batch download active candidates
            live_data = yf.download(active_list, period="1d", interval="1m", group_by='ticker', progress=False)
            
            for ticker in active_list:
                # Handle yfinance dataframe structure for single vs multiple tickers
                t_df = live_data[ticker].dropna() if len(active_list) > 1 else live_data.dropna()
                if t_df.empty: continue
                
                # Format Tensors (N=1 for individual ticker pulse)
                C, H, L = t_df['Close'].values.reshape(1, -1), t_df['High'].values.reshape(1, -1), t_df['Low'].values.reshape(1, -1)
                metrics = engine.process_financial_manifold(H, L, C)
                
                # Ingest Current State to Ledger
                jcllc_monitor.ingest_node_state("WEB3_FINANCE", {
                    "ticker": ticker,
                    "spot": float(metrics["spot"][-1]),
                    "z_score": float(metrics["z_score"][-1]),
                    "q_mark": float(metrics["q_mark"][-1]),
                    "liq_align": float(metrics["turtle_alignment"][-1]),
                    "historical": 0
                })
            
            print(f"[+] {time.strftime('%H:%M:%S')} | Pulse Recorded | Lake Active")
            time.sleep(60)
            
        except Exception as e:
            print(f"[!] Sovereign Pulse Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    # Start the Logic Loop in a background thread
    threading.Thread(target=sovereign_pulse_loop, daemon=True).start()
    
    # Launch the FastAPI Server (Host 0.0.0.0 allows iPad access on local network)
    uvicorn.run(app, host="0.0.0.0", port=8080)