import os
from pydantic_settings import BaseSettings
from typing import List

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"

class SDKSettings(BaseSettings):
    TICKER_NET: List[str] = ["BTC-USD", "ETH-USD", "SOL-USD", "SPY", "QQQ", "TSLA", "NVDA", "MSTR"]
    Q_THRESHOLD: float = 0.82
    POLLING_FREQ_SEC: int = 25
    VAULT_DIR: str = "vault"
    PREMIUM_API_KEYS: List[str] = ["jc_omni_v4_admin", "jc_quant_tier_1"]

    class Config:
        env_prefix = "JCLLC_"

settings = SDKSettings()
