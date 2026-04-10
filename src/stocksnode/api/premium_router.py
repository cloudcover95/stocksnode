from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from src.stocksnode.config.node_config import settings
from src.stocksnode.telemetry.global_registry import jcllc_registry

router = APIRouter(prefix="/v4/premium", tags=["Enterprise"])
api_key_header = APIKeyHeader(name="X-JCLLC-Omni-Key", auto_error=True)

def verify_premium_access(api_key: str = Security(api_key_header)):
    if api_key not in settings.PREMIUM_API_KEYS:
        raise HTTPException(status_code=403, detail="CME Protocol: Unauthorized API Access")
    return api_key

@router.get("/tensor/raw")
async def extract_raw_tensor(ticker: str, key: str = Depends(verify_premium_access)):
    df = jcllc_registry.get_df("WEB3_FINANCE", 500)
    if df.empty or ticker not in df['ticker'].values:
        return {"status": "VOID", "data": []}
    return {"manifold_integrity": "OK", "tensor": df[df['ticker'] == ticker].to_dict(orient="records")}
