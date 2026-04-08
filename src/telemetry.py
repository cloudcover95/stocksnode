import os
import time
import logging
from pathlib import Path
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="[*] %(message)s")

class GlobalTelemetryRegistry:
    """
    V305 Registry & Data Lake: Manages node mapping and .parquet archival.
    Optimized for Apple Silicon / M4 Unified Memory.
    """
    def __init__(self, workspace_root: str):
        self.root = Path(workspace_root)
        self.vault_dir = self.root / "vault" / "global_telemetry"
        self.vault_dir.mkdir(parents=True, exist_ok=True)
        
        # Registry Mapping
        self.buffers = {
            "WEB3_FINANCE": [], 
            "JC_DRIVE": [],     
            "LLM_SANDBOX": []   
        }
        self.FLUSH_THRESHOLD = 1000  # Row-count trigger for Parquet etch

    def ingest_node_state(self, node_id: str, state_vector: dict):
        """Sequential ledger ingestion."""
        if node_id not in self.buffers:
            self.buffers[node_id] = []
            
        state_vector["timestamp"] = time.time()
        self.buffers[node_id].append(state_vector)
        
        if len(self.buffers[node_id]) >= self.FLUSH_THRESHOLD:
            self.flush_to_lake(node_id)

    def flush_to_lake(self, node_id: str):
        """Etches buffer into the 5D Quartz-Simulated Data Lake."""
        if not self.buffers[node_id]: return
            
        ts = int(time.time())
        file_path = self.vault_dir / f"{node_id}_LAKE_{ts}.parquet"
        
        # Columnar conversion via PyArrow
        table = pa.Table.from_pydict({
            k: [r.get(k, 0.0) for r in self.buffers[node_id]] 
            for k in self.buffers[node_id][0].keys()
        })
        
        pq.write_table(table, file_path, compression='ZSTD')
        logging.info(f"DATA_LAKE_ETCH: {file_path.name} | Matrix: {table.shape}")
        self.buffers[node_id].clear()

# Global Singleton
jcllc_registry = GlobalTelemetryRegistry(workspace_root=os.getcwd())