class DeFiYieldFarmEngine:
    def estimate_yield(self, ticker: str, q_mark: float, spot: float, liq_align: float) -> dict:
        base_yield = 4.0 if "USD" in ticker else 1.5
        boost = q_mark * liq_align * 10.0
        return {"protocol": "Aave_V3_Sim", "estimated_apy": base_yield + boost}
