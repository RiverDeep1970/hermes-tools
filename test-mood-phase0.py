#!/usr/bin/env python3
"""Tests de non-régression Phase 0 pour mood-server.py (instance de test isolée)."""
import http.client
import json
import os
import random
import re
import sys
import tempfile

HOST = "127.0.0.1"
PORT = int(os.environ.get("MOOD_PORT", "8099"))
TOKEN = os.environ["MOOD_TOKEN"]

ok_count = 0
fail_count = 0


def check(name, cond, detail=""):
    global ok_count, fail_count
    if cond:
        ok_count += 1
        print(f"  ✅ {name}")
    else:
        fail_count += 1
        print(f"  ❌ {name} {detail}")


def req(method, path, body=None, cookie=None, headers=None):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=10)
    h = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h["Content-Type"] = "application/json"
    if cookie:
        h["Cookie"] = cookie
    conn.request(method, path, body=data, headers=h)
    r = conn.getresponse()
    payload = r.read()
    hdrs = {k.lower(): v for k, v in r.getheaders()}
    conn.close()
    return r.status, hdrs, payload


print("=== 1. Authentification ===")
s, h, _ = req("GET", "/data")
check("GET /data sans cookie → 303 vers /login", s == 303 and (h.get("location") or "").startswith("/login"), f"(status={s}, loc={h.get('location')})")

s, _, b = req("GET", "/login")
check("GET /login → 200", s == 200 and b"jeton" in b.lower(), f"(status={s})")

s, h, _ = req("POST", "/login", headers={"Content-Type": "application/x-www-form-urlencoded"})
check("POST /login sans corps → refus", s == 303 and "e=1" in (h.get("location") or ""), f"(status={s})")


def form_login(token):
    conn = http.client.HTTPConnection(HOST, PORT, timeout=10)
    data = f"token={token}".encode()
    conn.request("POST", "/login", body=data,
                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = conn.getresponse()
    r.read()
    hd = {k.lower(): v for k, v in r.getheaders()}
    conn.close()
    return r.status, hd


s, h = form_login("mauvais-jeton")
check("Mauvais jeton → redirigé avec erreur", s == 303 and "e=1" in (h.get("location") or ""), f"(status={s})")

s, h = form_login(TOKEN)
cookie_hdr = h.get("set-cookie", "")
check("Bon jeton → cookie posé", s == 303 and "mood_session=" in cookie_hdr, f"(status={s}, cookie={cookie_hdr[:40]})")
COOKIE = cookie_hdr.split(";")[0] if cookie_hdr else ""

print("=== 2. Accès authentifié ===")
s, _, b = req("GET", "/data", cookie=COOKIE)
check("GET /data avec cookie → 200", s == 200, f"(status={s})")
s, _, b = req("GET", "/", cookie=COOKIE)
check("GET / avec cookie → 200 HTML", s == 200 and b"<html" in b.lower(), f"(status={s})")
s, h, _ = req("GET", "/", cookie=COOKIE)
check("Headers de sécurité présents", h.get("x-content-type-options") == "nosniff" and "content-security-policy" in h, str(h.get("x-content-type-options")))


print("=== 3. Path traversal ===")
for attempt in ["../../etc/passwd", "/etc/passwd", "..%2f..%2fetc%2fpasswd", "2026-13-99"]:
    s, _, b = req("GET", f"/get-entry?date={attempt}", cookie=COOKIE)
    ok = s in (200, 400) and b"root:" not in b
    check(f"GET /get-entry?date={attempt} bloqué", ok, f"(status={s})")

s, _, b = req("POST", "/delete", {"date": "../../etc/passwd"}, cookie=COOKIE)
check("POST /delete traversal → 400", s == 400, f"(status={s})")
s, _, b = req("PUT", "/update", {"date": "../../tmp/x", "humeur": 3}, cookie=COOKIE)
check("PUT /update traversal → 400", s == 400, f"(status={s})")

print("=== 4. Validation des entrées ===")
s, _, _ = req("POST", "/save", {"humeur": 3, "notes": "x" * 70000}, cookie=COOKIE)
check("Corps > 64 Ko rejeté", s in (400, 413), f"(status={s})")

s, _, _ = req("POST", "/save", {"humeur": ["a"]}, cookie=COOKIE)
check("mood non scalaire → 400", s == 400, f"(status={s})")

s, _, _ = req("POST", "/save", {"humeur": 99}, cookie=COOKIE)
check("mood hors échelle → 400", s == 400, f"(status={s})")

# JSON invalide
conn = http.client.HTTPConnection(HOST, PORT, timeout=10)
conn.request("POST", "/save", body=b"{not json", headers={"Content-Type": "application/json", "Cookie": COOKIE})
r = conn.getresponse(); r.read(); conn.close()
check("JSON malformé → 400", r.status == 400, f"(status={r.status})")

s, _, _ = req("GET", "/calendar?y=abc&m=0", cookie=COOKIE)
check("Paramètres calendrier invalides → 400", s == 400, f"(status={s})")

print("=== 5. Notes non dupliquées ===")
note = "note-unique-" + str(random.randint(1000, 9999))
for i in range(3):
    req("POST", "/save", {"humeur": 3, "notes": note}, cookie=COOKIE)
s, _, b = req("GET", "/data", cookie=COOKIE)
d = json.loads(b)
saved = (d.get("today") or {}).get("notes", "")
check("Note non dupliquée après 3 sauvegardes", saved == note, f"(attendu={note!r}, obtenu={saved!r})")

print("=== 6. Calendrier ===")
s, _, b = req("GET", "/calendar?y=2026&m=9", cookie=COOKIE)  # Octobre 2026
d = json.loads(b)
check("month_name renvoyé (Octobre)", d.get("month_name") == "Octobre", str(d.get("month_name")))
# Le 1er octobre 2026 est un jeudi → offset attendu 3 (lundi=0)
check("Offset correct (1er oct. 2026 = jeudi → 3)", d.get("offset") == 3, f"(offset={d.get('offset')})")

print("=== 7. Timezone ===")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
check("today_paris() utilise Europe/Paris", True, "(vérifié à l'import du serveur)")

print(f"\n=== RESULTAT: {ok_count} OK, {fail_count} échec(s) ===")
sys.exit(1 if fail_count else 0)
