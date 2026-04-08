import requests
import json
from src.telemetry import jcllc_monitor

class LocalLLMBridge:
    """
    JuniorCloud LLC Sandbox: Local LLM Injection Layer.
    Connects to Ollama/LM Studio for real-time sentiment/logic analysis.
    """
    def __init__(self, port=11434, model="llama3"):
        self.url = f"http://localhost:{port}/api/generate"
        self.model = model

    def query_sandbox(self, prompt, context_tensor):
        """Injects raw tensor data into the LLM for high-level inference."""
        payload = {
            "model": self.model,
            "prompt": f"Analyze this JuniorCloud Tensor: {context_tensor}. Prompt: {prompt}",
            "stream": False
        }
        try:
            response = requests.post(self.url, json=payload, timeout=10)
            result = response.json().get("response", "")
            
            # Log inference to telemetry for .parquet archival
            jcllc_monitor.ingest_node_state("LLM_INFERENCE", {
                "prompt": prompt[:50],
                "inference_length": len(result),
                "success": 1
            })
            return result
        except:
            return "LLM_OFFLINE"