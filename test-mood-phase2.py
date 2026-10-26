#!/usr/bin/env python3
"""Tests Phase 2 : PWA (manifest/SW/icônes), accessibilité, recherche — instance isolée."""
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
TEST_DATE = "2002-02-02"

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


print("=== 1. Fichiers PWA (publics) ===")
for path, needle in [("/manifest.json", "manifest"), ("/sw.js", "javascript"),
                     ("/icon-192.png", "image/png"), ("/icon-512.png", "image/png"),
                     ("/icon-maskable-512.png", "image/png"), ("/apple-touch-icon.png", "image/png")]:
    s, h, b = req("GET", path)
    check(f"{path} → 200", s == 200 and needle in (h.get("content-type") or "")
          and len(b) > 100, f"status={s} ct={h.get('content-type')} len={len(b)}")

s, _, b = req("GET", "/manifest.json")
mf = json.loads(b)
check("manifest: standalone + start_url + 3 icônes",
      mf.get("display") == "standalone" and mf.get("start_url") == "/" and len(mf.get("icons", [])) == 3, mf)
check("manifest: icône maskable", any(i.get("purpose") == "maskable" for i in mf["icons"]))
s, _, b = req("GET", "/sw.js")
check("sw.js: gère le cache et le hors-ligne", b"caches" in b and b"fetch" in b)
check("sw.js: document en network-first (jamais de page périmée)",
      b"req.mode === 'navigate'" in b and b"mood-v2-" in b)

print("=== 2. Page : PWA + accessibilité ===")
s, h, _ = req("POST", "/login", form="token=" + urllib.parse.quote(TOKEN))
CK = h.get("set-cookie", "").split(";")[0]
s, h, page = req("GET", "/", cookie=CK)
html = page.decode()
check("link manifest", 'rel="manifest"' in html)
check("apple-touch-icon + meta iOS",
      'apple-touch-icon' in html and 'apple-mobile-web-app-capable' in html)
check("zoom débloqué", 'user-scalable=no' not in html and 'maximum-scale' not in html)
check("viewport-fit=cover", 'viewport-fit=cover' in html)
check("4 onglets déclarés",
      all(f'data-tab="{t}"' in html for t in ("today", "cal", "stats", "search")))
check("4 panes", all(f'id="tab-{t}"' in html for t in ("today", "cal", "stats", "search")))
check("bouton installer", 'install-btn' in html and 'beforeinstallprompt' in html)
check("enregistrement SW", "serviceWorker" in html and "/sw.js" in html)
check("mise à jour auto du SW (controllerchange + reg.update)",
      "controllerchange" in html and "reg.update()" in html)
check("file d'attente hors-ligne", 'mood-pending' in html and 'flushPending' in html)
check("champ de recherche", 'id="q"' in html and 'doSearch' in html)
check("CSP: worker-src autorisé", 'worker-src' in (h.get("content-security-policy") or ""))
check("cibles tactiles ≥44px (chips)", 'min-height:44px' in html)

print("=== 3. Recherche ===")
req("PUT", "/update", {"date": TEST_DATE, "humeur": 4, "notes": "randonnée au col",
                       "serie": "Silo", "activites": ["sport"]}, cookie=CK)
check("note trouvée", json.loads(req("GET", "/search?q=randonn", cookie=CK)[2])["count"] == 1)
check("insensible à la casse", json.loads(req("GET", "/search?q=SILO", cookie=CK)[2])["count"] >= 1)
check("par activité", json.loads(req("GET", "/search?q=sport", cookie=CK)[2])["count"] >= 1)
check("aucun résultat", json.loads(req("GET", "/search?q=zzzzz", cookie=CK)[2])["count"] == 0)
check("requête vide sans erreur", json.loads(req("GET", "/search?q=", cookie=CK)[2])["count"] == 0)
check("recherche protégée par auth", req("GET", "/search?q=a", cookie=None)[0] == 303)
req("POST", "/delete", {"date": TEST_DATE}, cookie=CK)

print(f"\n=== RESULTAT PHASE 2: {ok} OK, {fail} échec(s) ===")
sys.exit(1 if fail else 0)
