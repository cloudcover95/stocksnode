import time
from src.stocksnode.engines.defi_yield_farm import DeFiYieldFarmEngine

class ProfitabilityIdentityMatrix:
    def __init__(self):
        self.defi_engine = DeFiYieldFarmEngine()
        self.trade_fee_roundtrip = 0.004      
        self.short_term_tax = 0.32        
        self.long_term_tax = 0.15        
        self.tax_loss_offset = 0.40        
        self.risk_penalty = 0.25    

    def evaluate_singularity(self, ticker: str, q_mark: float, spot: float, liq_align: float, hold_days: int = 90) -> dict:
        farm_vector = self.defi_engine.estimate_yield(ticker, q_mark, spot, liq_align)
        gross_apy = farm_vector["estimated_apy"]
        days_frac = hold_days / 365.0
        gross_return = spot * (gross_apy / 100.0) * days_frac
        costs = spot * self.trade_fee_roundtrip * 2
        taxable_manifold = max(gross_return - costs, 0.0)
        tax_rate = self.long_term_tax if hold_days > 365 else self.short_term_tax
        tax_drag = taxable_manifold * tax_rate * (1.0 - self.tax_loss_offset)
        net_return = gross_return - costs - tax_drag
        net_apy = (net_return / spot) * (365.0 / hold_days) * 100.0 if spot > 0.0 else 0.0
        risk_score = net_apy * (1.0 - self.risk_penalty) + (q_mark * 8.0)
        
        recommendation = "EXECUTE_YIELD_FARM" if (net_apy > 3.5 and risk_score > 9.0) else "ISOLATE_AND_MONITOR"
        return {
            "ticker": ticker, "q_mark_trigger": round(q_mark, 4), "gross_apy": round(gross_apy, 2),
            "net_apy": round(net_apy, 2), "recommendation": recommendation, "protocol": farm_vector["protocol"],
            "timestamp": time.time(), "identity_status": "PROFITABLE_SINGULARITY" if net_apy > 5.0 else "MARGINAL"
        }
