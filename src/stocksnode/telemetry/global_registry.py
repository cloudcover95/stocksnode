import time, os, pandas as pd
from pathlib import Path

class GlobalRegistry:
    def __init__(self):
        self.vault = Path("vault/global_telemetry")
        self.vault.mkdir(parents=True, exist_ok=True)
        self.buffers = {"WEB3_FINANCE": [], "HUNTER_SIGNALS": [], "LLM_REPORTS": []}

    def ingest(self, node_id: str, data: dict):
        data["timestamp"] = time.time()
        self.buffers[node_id].append(data)

    def get_df(self, node_id: str, limit: int = 100):
        buffer = self.buffers.get(node_id, [])
        return pd.DataFrame(buffer[-limit:])

    def flush(self, node_id: str):
        self.buffers[node_id].clear() # Simplified for memory reset in pipeline

jcllc_registry = GlobalRegistry()
