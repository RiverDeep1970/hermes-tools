#!/usr/bin/env python3
"""Tests Phase 1 (modèle v2, 1-tap, stats) — instance de test isolée.

Utilise une date dédiée (2001-01-01) pour ne pas dépendre des données existantes,
et la supprime en fin de test.
"""
import http.client
import json
import os
import subprocess
import sys
import urllib.parse

PORT = int(os.environ.get("MOOD_PORT", "8099"))
TOKEN = os.environ.get("MOOD_TOKEN") or subprocess.run(
    "grep '^MOOD_TOKEN=' ~/.hermes/.env | cut -d= -f2",
    shell=True, capture_output=True, text=True).stdout.strip()
TEST_DATE = "2001-01-01"

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✅ {name}")
    else:
        fail += 1
        print(f"  ❌ {name} {detail}")


def req(method, path, body=None, cookie=None, form=None):
    c = http.client.HTTPConnection("127.0.0.1", PORT, timeout=10)
    h = {}
    data = None
    if form is not None:
        data = form.encode(); h["Content-Type"] = "application/x-www-form-urlencoded"
    elif body is not None:
        data = json.dumps(body).encode(); h["Content-Type"] = "application/json"
    if cookie:
        h["Cookie"] = cookie
    c.request(method, path, body=data, headers=h)
    r = c.getresponse(); p = r.read(); hd = {k.lower(): v for k, v in r.getheaders()}
    c.close()
    return r.status, hd, p


def entry(date):
    _, _, b = req("GET", "/get-entry?date=" + date, cookie=COOKIE)
    return json.loads(b).get("entry")


s, h, _ = req("POST", "/login", form="token=" + urllib.parse.quote(TOKEN))
COOKIE = h.get("set-cookie", "").split(";")[0]

print("=== 1. Création rétroactive (PUT /update) ===")
s, _, _ = req("PUT", "/update", {"date": TEST_DATE, "humeur": 2, "etats": ["triste"]}, cookie=COOKIE)
check("PUT /update crée un jour passé", s == 200, s)
e = entry(TEST_DATE)
check("humeur enregistrée", e and e["humeur"] == 2, e)
check("etats enregistrés", e and e["etats"] == ["triste"], e)

print("=== 2. Fusion des champs ===")
req("PUT", "/update", {"date": TEST_DATE, "humeur": 2, "energie": 4, "activites": ["sport"],
                       "lecture": "Dune", "notes": "note1"}, cookie=COOKIE)
e = entry(TEST_DATE)
check("energie", e.get("energie") == 4, e)
check("activites", e["activites"] == ["sport"], e)
check("lecture", e["lecture"] == "Dune", e)
check("notes", e["notes"] == "note1", e)
req("PUT", "/update", {"date": TEST_DATE, "humeur": 3}, cookie=COOKIE)
e = entry(TEST_DATE)
check("1-tap (humeur seule) préserve les autres champs",
      e["humeur"] == 3 and e["activites"] == ["sport"] and e["notes"] == "note1", e)

print("=== 3. Validations ===")
check("humeur 0 rejetée", req("POST", "/save", {"humeur": 0}, cookie=COOKIE)[0] == 400)
check("humeur 6 rejetée", req("POST", "/save", {"humeur": 6}, cookie=COOKIE)[0] == 400)
check("humeur 'abc' rejetée", req("POST", "/save", {"humeur": "abc"}, cookie=COOKIE)[0] == 400)
check("energie hors plage ignorée",
      req("PUT", "/update", {"date": TEST_DATE, "humeur": 3, "energie": 99}, cookie=COOKIE)[0] == 200
      and entry(TEST_DATE).get("energie") is None)
check("path traversal bloqué", req("PUT", "/update", {"date": "../../x", "humeur": 3}, cookie=COOKIE)[0] == 400)

print("=== 4. Endpoints v2 ===")
_, _, b = req("GET", "/data", cookie=COOKIE)
d = json.loads(b)
check("/data expose meta.moods (5)", len(d["meta"]["moods"]) == 5, len(d["meta"]["moods"]))
check("/data expose streak et record", "streak" in d and "record" in d)
_, _, b = req("GET", "/calendar?y=2026&m=9", cookie=COOKIE)
cal = json.loads(b)
check("calendrier: month_name + offset", cal["month_name"] == "Octobre" and cal["offset"] == 3)
check("calendrier: jours ont la clé humeur", all("humeur" in x for x in cal["days"]))
_, _, b = req("GET", "/stats", cookie=COOKIE)
st = json.loads(b)
check("/stats expose median, m7, corr", all(k in st for k in ("median", "m7", "corr")))
_, _, b = req("GET", "/export", cookie=COOKIE)
hdr = b.decode("utf-8-sig").splitlines()[0]
check("export CSV v2", hdr.startswith("date,humeur,energie,etats,activites,lecture,serie,notes"), hdr)

print("=== 5. Lien 1-tap (redirection login) ===")
s, h, _ = req("GET", "/?h=4")
check("sans cookie → /login?next=…", s == 303 and "next=" in (h.get("location") or ""), h.get("location"))
s, h, _ = req("POST", "/login", form="token=" + urllib.parse.quote(TOKEN) + "&next=%2F%3Fh%3D4")
check("login conserve la destination", (h.get("location") or "") == "/?h=4", h.get("location"))
s, h, _ = req("POST", "/login", form="token=" + urllib.parse.quote(TOKEN) + "&next=%2F%2Fevil.com")
check("next externe neutralisé", (h.get("location") or "") == "/", h.get("location"))

print("=== 6. Nettoyage ===")
s, _, _ = req("POST", "/delete", {"date": TEST_DATE}, cookie=COOKIE)
check("jour de test supprimé", s == 200 and entry(TEST_DATE) is None)

print(f"\n=== RESULTAT PHASE 1: {ok} OK, {fail} échec(s) ===")
sys.exit(1 if fail else 0)
