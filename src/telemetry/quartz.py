import pandas as pd
import glob
from pathlib import Path

class QuartzSearch:
    """High-speed query layer for the Parquet Data Lake."""
    def __init__(self, vault_path):
        self.vault = Path(vault_path)

    def holographic_query(self, min_q=0.85, ticker=None):
        """Finds high-intensity 'Standard Candle' moments across the lake."""
        files = glob.glob(str(self.vault / "*.parquet"))
        if not files: return pd.DataFrame()

        results = []
        for f in files:
            df = pd.read_parquet(f)
            # Filter by Q-Mark intensity
            match = df[df['q_mark'] >= min_q]
            if ticker:
                match = match[match['ticker'] == ticker]
            results.append(match)

        return pd.concat(results).sort_values('timestamp', ascending=False) if results else pd.DataFrame()