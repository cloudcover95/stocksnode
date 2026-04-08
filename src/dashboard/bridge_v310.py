# path: src/dashboard/bridge_v310.py
import pandas as pd
import glob, os
from flask import Flask, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

VAULT = "/Users/nico/Documents/JuniorCloud/stocksnode/vault/global_telemetry"

@app.route('/api/state')
def get_latest_state():
    # Pull the most recent .parquet file from the Data Lake
    files = glob.glob(f"{VAULT}/*.parquet")
    if not files: return jsonify({"status": "DATA_VOID"})
    
    latest_file = max(files, key=os.path.getctime)
    df = pd.read_parquet(latest_file)
    
    # We take the last state for each unique ticker
    state = df.sort_values('timestamp').groupby('ticker').tail(1)
    return state.to_json(orient='records')

if __name__ == "__main__":
    app.run(port=8080)