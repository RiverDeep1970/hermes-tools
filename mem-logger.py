#!/usr/bin/env python3
"""Log RAM + swap usage every 4h pour le dashboard."""
import json, os, psutil
from datetime import datetime

FP = os.path.expanduser("~/.hermes/mem-log.json")

mem = psutil.virtual_memory()
swap = psutil.swap_memory()

entry = {
    "t": datetime.now().strftime("%m-%d %H:%M"),
    "r": round(mem.percent, 1),
    "s": round(swap.percent, 1)
}

data = []
if os.path.exists(FP):
    with open(FP) as f:
        try: data = json.load(f)
        except: pass

data.append(entry)
# Keep max 48 entries (8 jours à 4h)
if len(data) > 48:
    data = data[-48:]

with open(FP, "w") as f:
    json.dump(data, f)

print(f"✅ Mem log: RAM={entry['r']}% Swap={entry['s']}% ({len(data)} entries)")