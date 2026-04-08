import yfinance as yf
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

class SovereignIngress:
    """Ingests live market data and formats into N x T tensor manifolds."""
    def __init__(self, tickers):
        self.tickers = tickers

    def fetch_latest_tensor(self, period="1d", interval="1m"):
        """Fetches OHLC data and returns as a dict of numpy matrices."""
        data = yf.download(self.tickers, period=period, interval=interval, group_by='ticker', progress=False)
        
        # Matrix dimensions: N (assets) x T (time steps)
        N = len(self.tickers)
        # Ensure we have a uniform T across all tickers
        T = len(data)
        
        H = np.zeros((N, T))
        L = np.zeros((N, T))
        C = np.zeros((N, T))

        for i, ticker in enumerate(self.tickers):
            # Handle yfinance multi-index/single-index variance
            t_data = data[ticker] if N > 1 else data
            H[i] = t_data['High'].values
            L[i] = t_data['Low'].values
            C[i] = t_data['Close'].values

        return {"H": H, "L": L, "C": C, "T_steps": T}