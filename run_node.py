# run_node.py
import time
import threading
import numpy as np
import pandas as pd
import yfinance as yf
from fastapi import FastAPI
from fastapi.responses import JSONResponse, FileResponse
import uvicorn
from pathlib import Path

from src.web3node.financial_tensor import Web3FinancialTensor
from src.web3node.ticker_hunter import TickerHunter
from src.telemetry import jcllc_monitor

app = FastAPI(title="JuniorCloud LLC // stocksnode V335 Sovereign Omni-Flex")

TICKERS = ["BTC-USD", "ETH-USD", "SOL-USD", "SPY", "QQQ"]
math_core = Web3FinancialTensor()
hunter = TickerHunter(q_threshold=0.82)   # Adjustable sensitivity

@app.get("/api/state")
async def get_state():
    buffer = jcllc_monitor.buffers.get("WEB3_FINANCE", [])
    return pd.DataFrame(buffer[-100:]).to_dict(orient="records") if buffer else {"status": "DATA_VOID"}

@app.get("/api/hunter")
async def get_hunter():
    return {
        "yield_farm_registry": hunter.get_yield_farm_registry(),
        "last_signals": jcllc_monitor.buffers.get("HUNTER_SIGNALS", [])[-10:]
    }

@app.get("/api/download/ledger/{ledger_type}")
async def download_ledger(ledger_type: str):
    buffer = jcllc_monitor.buffers.get("WEB3_FINANCE" if ledger_type == "main" else "HUNTER_SIGNALS", [])
    if not buffer:
        return {"status": "no_data"}
    df = pd.DataFrame(buffer)
    path = Path(f"vault/{ledger_type}_ledger_{int(time.time())}.csv")
    df.to_csv(path, index=False)
    return FileResponse(path, filename=f"stocksnode_{ledger_type}_ledger.csv")

def real_market_loop():
    print("[⚡ IGNITION] JuniorCloud LLC // stocksnode V335 Sovereign Omni-Flex + Ticker Hunter")
    print("[*] Dashboard: http://localhost:8080 + open src/dashboard/app.html")
    print("[*] Hunter actively scanning for Yield Farming Range signals...")

    pulse = 0
    while True:
        try:
            data = yf.download(TICKERS, period="5d", interval="5m", group_by="ticker", progress=False)
            
            closes = [data[t]['Close'].dropna().tail(60).values for t in TICKERS]
            highs  = [data[t]['High'].dropna().tail(60).values for t in TICKERS]
            lows   = [data[t]['Low'].dropna().tail(60).values for t in TICKERS]

            min_len = min((len(c) for c in closes), default=0)
            if min_len < 20:
                time.sleep(30)
                continue

            C = np.array([c[-min_len:] for c in closes])
            H = np.array([h[-min_len:] for h in highs])
            L = np.array([l[-min_len:] for l in lows])

            metrics = math_core.process_manifold(C, H, L)
            hunt_result = hunter.hunt(metrics, TICKERS)

            # Ingest main telemetry
            for i, t in enumerate(TICKERS):
                state = {
                    "ticker": t,
                    "spot": float(round(metrics["spot"][i], 2)),
                    "z_score": float(round(metrics["z_score"][i], 4)),
                    "q_mark": float(round(metrics["q_mark"][i], 4)),
                    "liq_align": float(round(metrics["turtle_alignment"][i], 4)),
                    "in_yield_farm": t in [s["ticker"] for s in hunt_result["yield_farm_registry"]]
                }
                jcllc_monitor.ingest_node_state("WEB3_FINANCE", state)

            pulse += 1
            print(f"[+] {time.strftime('%H:%M:%S')} | Pulse #{pulse} | Avg Q: {np.mean(metrics['q_mark']):.4f} | Hunter Signals: {len(hunt_result['signals'])} | Yield Farm: {hunt_result['yield_farm_count']}")

            if pulse % 10 == 0:
                jcllc_monitor.flush_to_lake("WEB3_FINANCE")

            time.sleep(25)

        except Exception as e:
            print(f"[!] Error in market loop: {e}")
            time.sleep(30)

if __name__ == "__main__":
    threading.Thread(target=real_market_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")