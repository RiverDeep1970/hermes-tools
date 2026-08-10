#!/usr/bin/env python3
"""Rapport hebdo/mensuel médicaments — envoyé par email."""
import json, urllib.request, os, re, sqlite3
from datetime import datetime, timedelta, date

DB = os.path.expanduser("~/.hermes/med-tracker.db")
EMAIL_TO = "river.deep@ik.me"
MEAL_LABELS = {"morning":"🌅 Matin","midday":"🌞 Midi","evening":"🌙 Soir"}

def get_agentmail_key():
    with open(os.path.expanduser("~/.hermes/config.yaml")) as f:
        m = re.search(r'AGENTMAIL_API_KEY:\s*([^\s]+)', f.read())
        return m.group(1).strip('"') if m else None

def main():
    days = 30 if date.today().day == 1 else 7
    label = "Mensuel" if days == 30 else "Hebdomadaire"
    since = (date.today() - timedelta(days=days)).isoformat()

    conn = sqlite3.connect(DB)
    c = conn.cursor()

    meds = c.execute("SELECT id, name, dosage FROM meds WHERE active=1").fetchall()
    html_rows = ""
    total_taken = 0
    total_expected = 0

    for m in meds:
        expected = c.execute("SELECT morning+midday+evening FROM meds WHERE id=?", (m[0],)).fetchone()[0] * days
        taken = c.execute("SELECT COUNT(*) FROM intakes WHERE med_id=? AND taken_date>=?", (m[0], since)).fetchone()[0]
        pct = round(taken/expected*100) if expected else 0
        total_taken += taken
        total_expected += expected
        html_rows += f"<tr><td><b>{m[1]}</b> {m[2] or ''}</td><td>{taken}/{expected}</td><td>{pct}%</td></tr>"

    overall = round(total_taken/total_expected*100) if total_expected else 0

    html = f"""<html><body style="font-family:sans-serif;padding:20px;max-width:650px">
<h2>💊 Bilan médicaments {label}</h2>
<p>Période : dernier(s) {days} jour(s)</p>
<p><b>Prise globale : {overall}%</b> ({total_taken}/{total_expected})</p>
<hr>
<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%">
<tr style="background:#f0f0f0"><th>Médicament</th><th>Pris</th><th>Observance</th></tr>
{html_rows}
</table>
<hr><p><i>Rapport automatique — Alexis Bot 🤖</i></p></body></html>"""

    text = f"Bilan médicaments {label}: {overall}% observance"

    k = get_agentmail_key()
    if not k: return
    data = json.dumps({"to":[EMAIL_TO],"subject":f"💊 Bilan médicaments {label}","text":text,"html":html}).encode()
    req = urllib.request.Request("https://api.agentmail.to/v0/inboxes/alexis-bot@agentmail.to/messages/send", data=data, headers={"Authorization":f"Bearer {k}","Content-Type":"application/json"}, method="POST")
    try:
        urllib.request.urlopen(req)
        print(f"✅ Rapport {label} envoyé")
    except Exception as e:
        print(f"Erreur: {e}")

if __name__ == "__main__":
    main()