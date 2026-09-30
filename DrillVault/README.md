# eRTMAC-NWIS V4 — Yellow/Orange + Corrected Similarity Engine

This version keeps the Yellow → Orange dashboard theme and fixes the similarity logic so a realistic depth difference does not automatically become 0%.

## Similarity weights
- Depth: 40%
- Formation: 25%
- Formation pressure: 20%
- Mud weight: 15%

Prototype tolerances:
- Depth: 500 m
- Pressure: 0.05
- Mud weight: 0.10

These are demonstration parameters, not validated field-engineering thresholds.

## Run
```powershell
pip install -r requirements.txt
python app.py
```
Then open http://127.0.0.1:5000

This remains a representative-data prototype for demonstration and engineering review, not a real drilling-control system.


V4 Fixed: Added the missing Formation selector used by the analysis endpoint and aligned the explainable-weight text with the backend.
