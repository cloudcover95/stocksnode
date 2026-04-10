import time, threading, numpy as np, pandas as pd, yfinance as yf, logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.stocksnode.config.node_config import settings
from src.stocksnode.core.financial_tensor import Web3FinancialTensor
from src.stocksnode.engines.ticker_hunter import TickerHunter
from src.stocksnode.telemetry.global_registry import jcllc_registry
from src.stocksnode.api.premium_router import router as premium_router

logging.basicConfig(level=logging.INFO, format="[*] %(message)s")

app = FastAPI(title="JCLLC Stocksnode V4.0 Enterprise")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(premium_router)

math_kernel = Web3FinancialTensor()
hunter_module = TickerHunter(q_threshold=settings.Q_THRESHOLD)

@app.get("/api/state")
async def get_state():
    df = jcllc_registry.get_df("WEB3_FINANCE", len(settings.TICKER_NET))
    return df.to_dict(orient="records") if not df.empty else {"status": "DATA_VOID"}

@app.get("/api/profit_matrix")
async def get_profit_matrix():
    df = jcllc_registry.get_df("HUNTER_SIGNALS", 10)
    return df.to_dict(orient="records") if not df.empty else []

def pipeline_loop():
    logging.info("V4.0 Sovereign Pipeline Engaged. Connecting to spatial manifold...")
    pulse_idx = 0
    while True:
        try:
            raw_data = yf.download(settings.TICKER_NET, period="5d", interval="5m", group_by="ticker", progress=False)
            C_list, H_list, L_list, active = [], [], [], []
            
            for t in settings.TICKER_NET:
                try:
                    c, h, l = raw_data[t]['Close'].dropna(), raw_data[t]['High'].dropna(), raw_data[t]['Low'].dropna()
                    if len(c) >= 60:
                        C_list.append(c.values[-60:])
                        H_list.append(h.values[-60:])
                        L_list.append(l.values[-60:])
                        active.append(t)
                except KeyError: continue
            
            if not C_list:
                time.sleep(settings.POLLING_FREQ_SEC)
                continue
                
            C, H, L = np.array(C_list), np.array(H_list), np.array(L_list)
            metrics = math_kernel.process_manifold(C, H, L)
            delta_q_array = math_kernel.compute_delta_q(metrics["q_mark"])
            hunt_results = hunter_module.hunt(metrics, active, delta_q_array)
            
            for i, t in enumerate(active):
                jcllc_registry.ingest("WEB3_FINANCE", {
                    "ticker": t, "spot": float(metrics["spot"][i]), "z_score": float(metrics["z_score"][i]),
                    "q_mark": float(metrics["q_mark"][i]), "delta_q": float(delta_q_array[i])
                })
                
            pulse_idx += 1
            logging.info(f"[Pulse {pulse_idx:04d}] Avg Q: {np.mean(metrics['q_mark']):.4f} | Singularity Targets: {hunt_results['signals_found']}")
            time.sleep(settings.POLLING_FREQ_SEC)
            
        except Exception as e:
            logging.error(f"Root Node Failure: {e}")
            time.sleep(40)

if __name__ == "__main__":
    threading.Thread(target=pipeline_loop, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=8080)
