import os, time, logging
from pathlib import Path
import pyarrow as pa
import pyarrow.parquet as pq

logging.basicConfig(level=logging.INFO, format="[*] %(message)s")

class GlobalTelemetryRegistry:
    def __init__(self, root_path=os.getcwd()):
        self.root = Path(root_path)
        self.vault = self.root / "vault" / "global_telemetry"
        self.vault.mkdir(parents=True, exist_ok=True)
        self.RESTRICTED = {"01_Legal", "02_Assets"}
        self.buffers = {"WEB3_FINANCE": [], "LLM_INFERENCE": [], "AUDIT": []}

    def _secure_gate(self, source_path):
        return not any(zone in Path(source_path).parts for zone in self.RESTRICTED)

    def ingest_node_state(self, node_id, state_vector, source="local"):
        if not self._secure_gate(source): return
        state_vector["timestamp"] = time.time()
        self.buffers[node_id].append(state_vector)
        if len(self.buffers[node_id]) >= 500: self.flush(node_id)

    def flush(self, node_id):
        if not self.buffers[node_id]: return
        f_path = self.vault / f"{node_id}_LAKE_{int(time.time())}.parquet"
        try:
            table = pa.Table.from_pydict({k: [r.get(k) for r in self.buffers[node_id]] for k in self.buffers[node_id][0].keys()})
            pq.write_table(table, f_path, compression='ZSTD')
            logging.info(f"ETCH_COMPLETE: {f_path.name}")
            self.buffers[node_id].clear()
        except Exception as e: logging.error(f"ETCH_FAILURE: {e}")

jcllc_monitor = GlobalTelemetryRegistry()
