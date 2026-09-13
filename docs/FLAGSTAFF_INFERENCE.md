# Flagstaff inference

`src/stocksnode/core/financial_tensor.py` (`Web3FinancialTensor`) is the live manifold.
JuniorHome `fieldcore_bridge.py` importlib-loads it when PYTHONPATH includes this repo.
Otherwise it uses the same numpy shape locally.
