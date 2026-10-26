#!/usr/bin/env python3
"""Résumé hebdomadaire du Mood Tracker (email HTML + résumé texte pour le cron).

Usage :
    mood-weekly-report.py            # les 7 derniers jours (dimanche soir)
    mood-weekly-report.py --dry      # n'envoie pas, affiche le texte
"""
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from zoneinfo import ZoneInfo

ENTRIES = os.path.expanduser(os.environ.get("MOOD_ENTRIES_DIR", "~/.hermes/life-tracker/entries"))
INBOX = "alexis-bot@agentmail.to"
TO_EMAIL = "river.deep@ik.me"
PARIS = ZoneInfo("Europe/Paris")

HUMEUR_EMOJI = {1: "😞", 2: "🙁", 3: "😐", 4: "🙂", 5: "😄"}
HUMEUR_LABEL = {1: "Très mal", 2: "Mal", 3: "Neutre", 4: "Bien", 5: "Très bien"}
JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
LEGACY = {"1": 1, "2": 2, "3": 3, "4": 5, "5": 3, "6": 3, "7": 3, "8": 3}
ETAT_LABEL = {"fatigue": "Fatigué", "malade": "Malade", "stresse": "Stressé", "anxieux": "Anxieux",
              "motif": "Motivé", "serein": "Serein", "enerve": "Énervé", "triste": "Triste"}


def get_key():
    k = os.environ.get("AGENTMAIL_API_KEY")
    if k:
        return k
    try:
        with open(os.path.expanduser("~/.hermes/config.yaml")) as f:
            m = re.search(r"AGENTMAIL_API_KEY:\s*([^\s]+)", f.read())
        return m.group(1).strip('"') if m else None
    except OSError:
        return None


def load_day(day):
    path = os.path.join(ENTRIES, day.isoformat() + ".json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            e = json.load(f)
    except (ValueError, OSError):
        return None
    raw = e.get("humeur") if "humeur" in e else LEGACY.get(str(e.get("mood", "")))
    try:
        humeur = int(raw) if raw not in (None, "") else None
    except (TypeError, ValueError):
        humeur = None
    if humeur is not None and not (1 <= humeur <= 5):
        humeur = None
    etats = e.get("etats") or ([] if "humeur" in e else
                               [k for k, v in {"fatigue": "5", "malade": "6", "stresse": "7", "motif": "8"}.items()
                                if str(e.get("mood", "")) == v])
    return {"date": day, "humeur": humeur, "etats": etats,
            "activites": e.get("activites") or [], "notes": e.get("notes", e.get("note", ""))}


def main():
    dry = "--dry" in sys.argv
    today = dt.datetime.now(PARIS).date()
    days = [today - dt.timedelta(days=i) for i in range(7)]
    prev = [today - dt.timedelta(days=i) for i in range(7, 14)]
    cur = {d: load_day(d) for d in days}
    old = {d: load_day(d) for d in prev}

    vals = [v["humeur"] for v in cur.values() if v and v["humeur"]]
    vals_prev = [v["humeur"] for v in old.values() if v and v["humeur"]]
    avg = sum(vals) / len(vals) if vals else None
    avg_prev = sum(vals_prev) / len(vals_prev) if vals_prev else None
    delta = (avg - avg_prev) if (avg is not None and avg_prev is not None) else None

    etats = {}
    for v in cur.values():
        if v:
            for s in v["etats"]:
                etats[s] = etats.get(s, 0) + 1
    top_etat = max(etats, key=etats.get) if etats else None

    best_day = None
    for d in sorted(cur, reverse=True):
        if cur[d] and cur[d]["humeur"]:
            if best_day is None or cur[d]["humeur"] > cur[best_day]["humeur"]:
                best_day = d

    filled = len(vals)
    period = f"{days[-1].strftime('%d/%m')} → {today.strftime('%d/%m')}"

    # ----- texte -----
    t = [f"📓 Mood — semaine du {period}"]
    t.append(f"Entrées : {filled}/7 jours" + (" — bel assiduité 💪" if filled >= 6 else ""))
    if avg is not None:
        t.append(f"Humeur moyenne : {avg:.1f}/5 {HUMEUR_EMOJI.get(round(avg), '')}")
    if delta is not None:
        t.append(f"Évolution vs semaine précédente : {'▲ +' if delta >= 0 else '▼ '}{delta:.1f}")
    if top_etat:
        t.append(f"État le plus fréquent : {ETAT_LABEL.get(top_etat, top_etat)} ({etats[top_etat]} j)")
    if best_day:
        t.append(f"Meilleure journée : {JOURS[best_day.weekday()]} {best_day.strftime('%d/%m')} "
                 f"{HUMEUR_EMOJI.get(cur[best_day]['humeur'], '')}")
    if not vals:
        t.append("Aucune humeur enregistrée cette semaine.")
    text = "\n".join(t)

    # ----- HTML -----
    rows = ""
    for d in sorted(cur):
        v = cur[d]
        if v and v["humeur"]:
            rows += (f'<tr><td>{JOURS[d.weekday()]} {d.strftime("%d/%m")}</td>'
                     f'<td align="center" style="font-size:18px">{HUMEUR_EMOJI.get(v["humeur"], "")}</td>'
                     f'<td>{HUMEUR_LABEL.get(v["humeur"], "")}</td>'
                     f'<td><small>{", ".join(ETAT_LABEL.get(s, s) for s in v["etats"])}</small></td></tr>')
        else:
            rows += (f'<tr><td>{JOURS[d.weekday()]} {d.strftime("%d/%m")}</td>'
                     f'<td align="center" style="color:#bbb">—</td><td colspan="2"><small style="color:#bbb">non renseigné</small></td></tr>')

    html = f"""<html><body style="font-family:Arial,sans-serif;max-width:640px;margin:auto;padding:16px;color:#222;line-height:1.5">
<h2>📓 Ton récap de la semaine</h2>
<p><small>{period}</small></p>
<div style="background:#eef3fb;border-left:4px solid #2b6cb0;padding:10px 12px;margin:12px 0;border-radius:4px">
  <b>Humeur moyenne :</b> {f'{avg:.1f}/5 {HUMEUR_EMOJI.get(round(avg), "")}' if avg is not None else "—"}<br>
  {'<b>Évolution :</b> ' + ("▲ +" if delta >= 0 else "▼ ") + f"{delta:.1f} vs semaine précédente<br>" if delta is not None else ''}
  <b>Entrées :</b> {filled}/7 jours<br>
  {'<b>État dominant :</b> ' + ETAT_LABEL.get(top_etat, top_etat) + f" ({etats[top_etat]} j)<br>" if top_etat else ''}
  {'<b>Meilleure journée :</b> ' + JOURS[best_day.weekday()] + " " + best_day.strftime('%d/%m') if best_day else ''}
</div>
<table style="border-collapse:collapse;width:100%;font-size:14px">
<tr style="background:#f2f2f2"><th align="left">Jour</th><th>Humeur</th><th align="left"></th><th align="left">États</th></tr>
{rows}
</table>
<p style="color:#888;font-size:12px">Rapport automatique — <a href="https://mood.riverdeep1970.xyz/">ouvrir Mood Tracker</a></p>
</body></html>"""

    if dry:
        print("=== DRY RUN ===")
        print(text)
        return

    key = get_key()
    if key:
        payload = json.dumps({"to": [TO_EMAIL], "subject": f"📓 Mood — récap semaine ({period})",
                              "text": text, "html": html}).encode()
        req = urllib.request.Request(f"https://api.agentmail.to/v0/inboxes/{INBOX}/messages/send",
                                     data=payload,
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                                     method="POST")
        try:
            urllib.request.urlopen(req, timeout=30)
            print("(email envoyé)", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"(échec email: {e})", file=sys.stderr)
    print(text)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f"Erreur rapport hebdo mood : {exc}", file=sys.stderr)
        sys.exit(1)
