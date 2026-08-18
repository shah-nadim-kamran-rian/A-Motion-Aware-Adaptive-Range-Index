#!/usr/bin/env bash
# Reproduce MARI's results and rebuild the manuscript. Usage: bash reproduce.sh
set -e
echo "== 1. dependencies =="
pip install -r requirements.txt --break-system-packages

echo "== 2. datasets (Sections 9.9, 9.13, 9.16) =="
mkdir -p data
[ -f data/all_stocks_5yr.csv ] || curl -sS -o data/all_stocks_5yr.csv \
  https://raw.githubusercontent.com/plotly/datasets/master/all_stocks_5yr.csv
[ -f data/nbaallelo.csv ] || curl -sS -o data/nbaallelo.csv \
  https://raw.githubusercontent.com/fivethirtyeight/data/master/nba-elo/nbaallelo.csv
python - <<'PY'
import urllib.request, pandas as pd, io, os
cities=["nyc","atlanta","boston","chicago","denver","elpaso","honolulu","houston",
        "losangeles","miami","minneapolis","phoenix","portland","saltlake","sanfrancisco","seattle"]
for c in cities:
    p=f"data/wx_{c}.csv"
    if os.path.exists(p): continue
    raw=urllib.request.urlopen(f"https://raw.githubusercontent.com/zonination/weather-us/master/{c}.csv").read()
    df=pd.read_csv(io.BytesIO(raw),usecols=["Date","Mean.TemperatureF"]); df["city"]=c
    df.to_csv(p,index=False)
print("datasets ready")
PY

echo "== 3. experiments (each writes a *_results.json) =="
python mari_v2.py            # exactness + relocation (Table R1)
python thm_check.py          # Theorem 3 validation
python baseline_bench.py     # MARI vs ART/PGM/Bx, 5 seeds + scale (Table R20, Fig 8)
python tuning_bench.py       # guard = drift quantile (Table R18, Fig 7)
python real_data_bench.py    # S&P (Section 9.9)
python real_multi_bench.py   # NBA Elo + temps (Section 9.9)
python query_bench.py        # query latency / verification (Tables R15-16, Fig 6)
python recovery_demo.py      # crash recovery (Table R17)
python memory_bench.py       # memory overhead (Table R19)
python hotspot_demo.py       # hotspot mitigation (Table R22)
python hetero_demo.py        # heteroscedastic per-region guards (Table R21)
# native durable-write comparison (needs lmdb + rocksdict):
python native_bench.py lmdb || true
python native_bench.py rocksdb || true
python native_bench.py mari || true

echo "== 4. figures =="
python gen_figures.py || true
python fig_query.py; python fig_tuning.py; python fig_baseline.py

echo "== 5. manuscript =="
sed -i 's/]), { justify: true });/], { justify: true }));/g' build_mari.js   # recurring-bug guard
node build_mari.js
echo "Done -> MARI_manuscript_draft.docx"
