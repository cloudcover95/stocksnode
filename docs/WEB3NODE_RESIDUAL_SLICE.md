# Residual tick lives on JuniorHome

Do not vendor a second V305 core here.

Source of truth: `cloudcover95/JuniorHome` branch `slice/web3node-ternary-20260913`

- `web3node/svd_residual_tick.py` — SVD retained, residual into ternary mesh
- `web3node/trit_cache.py` — packed trits + zlib; zstd when present
- `deployment/Dockerfile.web3node-harness` — thin numpy bench toward this node

This repo keeps Parquet / quant rails. FrameForge knockback is not scaled here.
