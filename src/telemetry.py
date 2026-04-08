# path: src/telemetry.py
import os, time, logging
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq

class GlobalTelemetryRegistry:
    def __init__(self, root_path):
        self.root = Path(root_path)
        self.vault = self.root / "vault" / "global_telemetry"
        self.vault.mkdir(parents=True, exist_ok=True)
        self.RESTRICTED = {"01_Legal", "02_Assets"}
        self.buffers = {"WEB3_FINANCE": []}

    def _secure_gate(self, path):
        return not any(zone in Path(path).parts for zone in self.RESTRICTED)

    def ingest_node_state(self, node_id, vector, source="local"):
        if not self._secure_gate(source): return
        vector["timestamp"] = time.time()
        self.buffers[node_id].append(vector)
        if len(self.buffers[node_id]) >= 100: self.flush(node_id)

    def flush(self, node_id):
        if not self.buffers[node_id]: return
        f_path = self.vault / f"{node_id}_{int(time.time())}.parquet"
        table = pa.Table.from_pydict({k: [r[k] for r in self.buffers[node_id]] for k in self.buffers[node_id][0].keys()})
        pq.write_table(table, f_path, compression='ZSTD')
        self.buffers[node_id].clear()

jcllc_monitor = GlobalTelemetryRegistry(os.getcwd())