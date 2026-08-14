#!/usr/bin/env python3
"""Rappel médicaments — envoyé par Telegram aux heures de repas."""
import json, urllib.request, os, re, sqlite3
from datetime import date
import sys

MEAL = sys.argv[1] if len(sys.argv) > 1 else "morning"
MEAL_EMOJI = {"morning": "🌅 Matin", "midday": "🌞 Midi", "evening": "🌙 Soir"}
MEAL_URL = {"morning": "https://mood.riverdeep1970.xyz", "midday": "https://mood.riverdeep1970.xyz", "evening": "https://mood.riverdeep1970.xyz"}

DB = os.path.expanduser("~/.hermes/med-tracker.db")
CHAT_ID = "8126578200"

def get_token():
    t = os.environ.get("TELEGRAM_BOT_TOKEN")
    if t: return t
    try:
        with open(os.path.expanduser("~/.hermes/.env")) as f:
            for line in f:
                if "TELEGRAM_BOT_TOKEN" in line and "=" in line and not line.strip().startswith("#"):
                    v = line.split("=",1)[1].strip()
                    for q in ["'",'"']:
                        if v.startswith(q) and v.endswith(q): return v[1:-1]
                    return v
    except: pass
    return None

def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    today = date.today().isoformat()
    col = {"morning": "morning", "midday": "midday", "evening": "evening"}
    
    meds = c.execute(f"SELECT id, name, dosage FROM meds WHERE active=1 AND {col[MEAL]}=1").fetchall()
    taken = {r[0] for r in c.execute("SELECT med_id FROM intakes WHERE taken_date=? AND meal=?", (today, MEAL))}
    
    pending = [m for m in meds if m[0] not in taken]
    
    if not pending:
        return  # Silencieux si tout est pris
    
    msg = f"💊 *Rappel {MEAL_EMOJI[MEAL]}*\n\nMédicaments à prendre :\n"
    for m in pending:
        msg += f"• {m[1]}" + (f" ({m[2]})" if m[2] else "") + "\n"
    
    msg += f"\n[✅ Ouvrir le site]({MEAL_URL[MEAL]})"
    
    token = get_token()
    if not token: return
    d = json.dumps({"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=d, headers={"Content-Type":"application/json"}))
        print(f"✅ Rappel {MEAL} envoyé ({len(pending)} médicaments)")
    except Exception as e:
        print(f"Erreur: {e}")

if __name__ == "__main__":
    main()