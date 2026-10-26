#!/usr/bin/env python3
"""Mood Tracker v3 — calendrier, stats, édition, dark mode, export CSV."""
import json, os, csv, io, re, hmac, hashlib, urllib.parse
import calendar as calmod
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo
from collections import defaultdict

ENTRIES_DIR = os.path.expanduser(os.environ.get("MOOD_ENTRIES_DIR", "~/.hermes/life-tracker/entries"))
STATIC_DIR = os.path.expanduser(os.environ.get("MOOD_STATIC_DIR", "~/.hermes/mood-static"))
os.makedirs(ENTRIES_DIR, exist_ok=True)

MOOD_LABELS = {"1":"Mal","2":"Bof","3":"Bien","4":"Super","5":"Fatigué","6":"Malade","7":"Stressé","8":"Motivé"}
EMOJI = {"1":"😞","2":"😐","3":"🙂","4":"😄","5":"😴","6":"🤒","7":"😰","8":"🚀"}
MOOD_COLORS = {"1":"#ff6b6b","2":"#ffa94d","3":"#74b816","4":"#2b8a3e","5":"#748ffc","6":"#da77f2","7":"#f06595","8":"#ffd43b"}

# --- Modèle de données v2 (migration 2026-10-26) ---
# humeur = axe unique de bien-être (1..5), etats et activites = tags indépendants
MOODS = [
    {"v": 1, "e": "😞", "l": "Très mal"},
    {"v": 2, "e": "🙁", "l": "Mal"},
    {"v": 3, "e": "😐", "l": "Neutre"},
    {"v": 4, "e": "🙂", "l": "Bien"},
    {"v": 5, "e": "😄", "l": "Très bien"},
]
ETATS = [
    {"k": "fatigue", "l": "Fatigué", "e": "😴"},
    {"k": "malade", "l": "Malade", "e": "🤒"},
    {"k": "stresse", "l": "Stressé", "e": "😰"},
    {"k": "anxieux", "l": "Anxieux", "e": "😟"},
    {"k": "motif", "l": "Motivé", "e": "🚀"},
    {"k": "serein", "l": "Serein", "e": "😌"},
    {"k": "enerve", "l": "Énervé", "e": "😤"},
    {"k": "triste", "l": "Triste", "e": "😢"},
]
ACTIVITES = [
    {"k": "lecture", "l": "Lecture", "e": "📖"},
    {"k": "serie", "l": "Série", "e": "📺"},
    {"k": "sport", "l": "Sport", "e": "🏃"},
    {"k": "musique", "l": "Musique", "e": "🎵"},
    {"k": "cuisine", "l": "Cuisine", "e": "🍳"},
    {"k": "promenade", "l": "Promenade", "e": "🌿"},
    {"k": "jeu", "l": "Jeu vidéo", "e": "🎮"},
    {"k": "sortie", "l": "Sortie", "e": "🚶"},
    {"k": "travail", "l": "Travail", "e": "💼"},
    {"k": "social", "l": "Amis", "e": "👥"},
]
HUMEUR_EMOJI = {m["v"]: m["e"] for m in MOODS}
HUMEUR_LABEL = {m["v"]: m["l"] for m in MOODS}
ACT_LABEL = {a["k"]: a["l"] for a in ACTIVITES}

# Rétrocompatibilité avec l'ancien format (mood 1..8)
LEGACY_HUMEUR = {"1": 1, "2": 2, "3": 3, "4": 5, "5": 3, "6": 3, "7": 3, "8": 3}
LEGACY_ETAT = {"5": "fatigue", "6": "malade", "7": "stresse", "8": "motif"}
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]+")


def normalize_entry(e):
    """Normalise une entrée (v2 ou ancien format) vers le schéma v2."""
    if not isinstance(e, dict):
        return None
    if "humeur" in e:
        humeur = e.get("humeur")
        etats = e.get("etats") or []
        activites = e.get("activites") or []
        notes = e.get("notes", "")
        energie = e.get("energie")
    else:
        mood = str(e.get("mood", ""))
        humeur = LEGACY_HUMEUR.get(mood)
        etats = [LEGACY_ETAT[mood]] if mood in LEGACY_ETAT else []
        activites = []
        for part in str(e.get("activite", "")).split(","):
            tag = EMOJI_RE.sub("", part).strip().lower()
            if tag and tag not in activites:
                activites.append(tag)
        notes = e.get("note", "")
        energie = e.get("energie")
    try:
        humeur = int(humeur) if humeur not in (None, "") else None
    except (TypeError, ValueError):
        humeur = None
    if humeur is not None and not (1 <= humeur <= 5):
        humeur = None
    try:
        energie = int(energie) if energie not in (None, "") else None
    except (TypeError, ValueError):
        energie = None
    if energie is not None and not (1 <= energie <= 5):
        energie = None
    return {
        "date": e.get("date", ""),
        "version": 2,
        "humeur": humeur,
        "energie": energie,
        "etats": [str(x) for x in etats if isinstance(x, str)],
        "activites": [str(x) for x in activites if isinstance(x, str)],
        "lecture": e.get("lecture", "") or "",
        "serie": e.get("serie", "") or "",
        "notes": notes or "",
    }

# --- Sécurité / configuration ---
PARIS = ZoneInfo("Europe/Paris")
MAX_BODY = 64 * 1024          # plafond du corps de requête
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
COOKIE_NAME = "mood_session"


def _load_token():
    """Jeton depuis l'environnement ou ~/.hermes/.env."""
    tok = os.environ.get("MOOD_TOKEN")
    if tok:
        return tok.strip()
    try:
        with open(os.path.expanduser("~/.hermes/.env")) as f:
            m = re.search(r"^MOOD_TOKEN=(.+)$", f.read(), re.M)
        return m.group(1).strip() if m else ""
    except OSError:
        return ""


MOOD_TOKEN = _load_token()
SESSION_VALUE = (hmac.new(MOOD_TOKEN.encode(), b"mood-session-v1", hashlib.sha256).hexdigest()
                 if MOOD_TOKEN else "")


def today_paris():
    """Date du jour en heure de Paris (le serveur tourne en UTC)."""
    return datetime.now(PARIS).date()


def safe_date(value):
    """Valide une date YYYY-MM-DD et garantit un chemin confiné à ENTRIES_DIR."""
    if not isinstance(value, str) or not DATE_RE.match(value):
        return None
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None
    path = os.path.realpath(os.path.join(ENTRIES_DIR, value + ".json"))
    if not path.startswith(os.path.realpath(ENTRIES_DIR) + os.sep):
        return None
    return path


LOGIN_HTML = """<!DOCTYPE html>
<html lang="fr"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>🔒 Mood</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f5f5f7;color:#1c1c1e;
min-height:100dvh;display:flex;align-items:center;justify-content:center;padding:20px}
@media(prefers-color-scheme:dark){body{background:#000;color:#f5f5f7}}
.card{background:var(--c,#fff);border-radius:16px;padding:24px;width:100%;max-width:360px;box-shadow:0 2px 16px rgba(0,0,0,.08)}
h1{font-size:1.2em;margin-bottom:14px}
p{font-size:.85em;color:#666;margin-bottom:14px}
input{width:100%;padding:12px;border:2px solid #e8e8ed;border-radius:10px;font-size:1em;margin-bottom:10px;background:#fafafa;color:inherit}
input:focus{outline:none;border-color:#007aff}
button{width:100%;padding:12px;border:none;border-radius:10px;background:#007aff;color:#fff;font-size:1em;font-weight:600;cursor:pointer}
.err{color:#ff3b30;font-size:.85em;margin-top:10px;display:none}
</style></head><body>
<form class="card" method="POST" action="/login">
  <h1>📓 Mood</h1>
  <p>Accès protégé. Entre le jeton d'accès.</p>
  <input type="password" name="token" placeholder="Jeton" autofocus autocomplete="current-password">
  <input type="hidden" id="nx" name="next" value="">
  <button type="submit">Entrer</button>
  <div class="err" id="e">Jeton invalide.</div>
</form>
<script>
(function(){
  if(location.search.indexOf('e=1')>-1)document.getElementById('e').style.display='block';
  var m=location.search.match(/[?&]next=([^&]+)/);
  if(m){document.getElementById('nx').value=decodeURIComponent(m[1]);}
})();
</script>
</body></html>"""

HTML = r"""<!DOCTYPE html>
<html lang="fr" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,viewport-fit=cover">
<title>📓 Mood</title>
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#0a84ff">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Mood">
<link rel="apple-touch-icon" href="/apple-touch-icon.png">
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100dvh;padding-bottom:80px;transition:background .3s,color .3s}
:root{--bg:#f5f5f7;--card:#fff;--text:#1c1c1e;--text2:#666;--text3:#999;--border:#e8e8ed;--input-bg:#fafafa;--accent:#007aff;--accent-bg:#e8f0ff;--accent-text:#007aff;--good-bg:#e8ffe8;--good-text:#155724;--shadow:rgba(0,0,0,0.05);--danger:#ff3b30;--orange:#ff9500}
[data-theme=dark]{--bg:#000;--card:#1c1c1e;--text:#f5f5f7;--text2:#8e8e93;--text3:#636366;--border:#38383a;--input-bg:#2c2c2e;--accent:#0a84ff;--accent-bg:#1a2a4a;--accent-text:#0a84ff;--good-bg:#1a3a1a;--good-text:#34c759;--shadow:rgba(0,0,0,0.3);--danger:#ff453a;--orange:#ff9f0a}
.hdr{background:var(--card);padding:12px 16px;box-shadow:0 1px 4px var(--shadow);position:sticky;top:0;z-index:100;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border)}
.hdr h1{font-size:1.15em;color:var(--text)}
.hdr-r{display:flex;gap:8px;align-items:center}
.streak{font-size:.8em;color:var(--orange);font-weight:600;background:var(--input-bg);padding:5px 9px;border-radius:12px}
.dm-btn{background:none;border:2px solid var(--border);border-radius:10px;font-size:1em;padding:6px 10px;cursor:pointer;color:var(--text2);transition:all .2s;line-height:1;min-width:44px;min-height:40px}
.dm-btn:active{transform:scale(.9)}
.c{padding:12px 12px;max-width:500px;margin:0 auto}
.card{background:var(--card);border-radius:16px;padding:16px;box-shadow:0 1px 6px var(--shadow);margin-bottom:12px;transition:background .3s}
h2{font-size:.8em;color:var(--text2);margin-bottom:10px;text-transform:uppercase;letter-spacing:.4px;display:flex;align-items:center;gap:6px}
.tabs{display:flex;background:var(--card);border-bottom:1px solid var(--border);position:sticky;top:51px;z-index:99}
.tab{flex:1;text-align:center;padding:10px 6px;font-size:.85em;color:var(--text3);cursor:pointer;border-bottom:3px solid transparent;transition:all .2s;font-weight:500}
.tab:active{opacity:.7}
.tab.act{color:var(--accent);border-bottom-color:var(--accent)}
.tab-c{display:none;animation:fadeIn .25s ease}
.tab-c.act{display:block}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
/* Q1T : saisie 1 tap */
.q1t{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin-bottom:4px}
.qt{background:var(--input-bg);border:2px solid var(--border);border-radius:14px;padding:10px 2px;cursor:pointer;text-align:center;transition:all .15s ease;min-height:64px}
.qt .e{font-size:1.7em;display:block;line-height:1.15}
.qt .l{font-size:.6em;color:var(--text2);display:block;margin-top:2px}
.qt:active{transform:scale(.9)}
.qt.sel{border-color:var(--accent);background:var(--accent-bg)}
.qt.sel .l{color:var(--accent-text);font-weight:700}
.q1t-hint{text-align:center;font-size:.75em;color:var(--text3);margin-bottom:2px}
.det-toggle{display:block;text-align:center;padding:9px;margin-top:6px;background:var(--input-bg);border:2px dashed var(--border);border-radius:10px;color:var(--accent);font-size:.85em;font-weight:500;cursor:pointer}
.det{display:none;margin-top:12px}
.det.open{display:block}
.grp{margin-bottom:12px}
.grp>label{display:block;font-size:.75em;color:var(--text2);margin-bottom:6px;font-weight:600}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{padding:10px 14px;border:2px solid var(--border);border-radius:16px;background:var(--input-bg);font-size:.82em;cursor:pointer;color:var(--text);transition:all .15s;min-height:44px;display:flex;align-items:center;gap:4px}
.chip:active{transform:scale(.93)}
.chip.sel{border-color:#34c759;background:var(--good-bg);color:var(--good-text);font-weight:600}
.chip.add{border-style:dashed;color:var(--text3)}
.energy{display:grid;grid-template-columns:repeat(5,1fr);gap:5px}
.eb{background:var(--input-bg);border:2px solid var(--border);border-radius:10px;padding:8px 2px;text-align:center;cursor:pointer;font-size:.72em;color:var(--text2);min-height:44px}
.eb.sel{border-color:var(--orange);background:#fff4e6;color:#8a5000;font-weight:700}
[data-theme=dark] .eb.sel{background:#3a2a10;color:#ffb340}
.field{width:100%;padding:10px 12px;border:2px solid var(--border);border-radius:10px;font-size:.95em;margin-bottom:6px;background:var(--input-bg);color:var(--text);transition:border .2s,background .2s}
.field:focus{border-color:var(--accent);outline:none;background:var(--card)}
textarea.field{resize:vertical;min-height:44px;font-family:inherit}
::placeholder{color:var(--text3);opacity:1}
.btn-row{display:flex;gap:8px}
.sb,.db{flex:1;padding:12px;border:none;border-radius:10px;font-size:1em;font-weight:600;cursor:pointer;transition:opacity .2s}
.sb{background:var(--accent);color:#fff}
.db{background:var(--danger);color:#fff}
.sb:active,.db:active{opacity:.7}
.sb:disabled{opacity:.4}
#st,#mod-st{text-align:center;padding:8px;border-radius:8px;display:none;font-size:.82em;margin-top:8px;transition:all .2s}
.succ{background:var(--good-bg);color:var(--good-text);display:block!important}
.err{background:#3a1a1a;color:#ff453a;display:block!important}
/* TREND/HIST */
.hw{display:flex;gap:5px;justify-content:center;padding:6px 0;flex-wrap:wrap}
.hd{width:34px;height:34px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:15px;flex-shrink:0;border:2px solid var(--border)}
.hl{font-size:9px;color:var(--text3);margin-top:1px;text-align:center;white-space:nowrap}
.hc{display:flex;flex-direction:column;align-items:center}
.hp{padding:7px 6px;border-bottom:1px solid var(--border);display:flex;gap:8px;align-items:flex-start;cursor:pointer;transition:background .15s;border-radius:6px;margin:0 -6px}
.hp:hover{background:var(--input-bg)}
.hp:last-child{border:none}
.hp .d{font-size:.75em;color:var(--text3);min-width:32px;flex-shrink:0}
.hp .t{font-size:.85em;color:var(--text);flex:1}
.hp .t .s{color:var(--text2);font-size:.78em}
.hp .e-icon{font-size:1.2em;width:24px;text-align:center}
/* CALENDAR */
.cal-nav{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.cal-nav button{background:var(--input-bg);border:2px solid var(--border);border-radius:10px;padding:6px 12px;font-size:.9em;cursor:pointer;color:var(--text);transition:all .15s;min-width:44px;min-height:40px}
.cal-nav button:active{transform:scale(.92)}
.cal-nav .m-title{font-weight:600;font-size:.95em;color:var(--text)}
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:3px;text-align:center}
.cal-hd{padding:4px;font-size:.7em;color:var(--text3);font-weight:600}
.cal-d{padding:6px 0;font-size:.82em;cursor:pointer;transition:all .15s;border-radius:8px;color:var(--text);position:relative;min-height:38px}
.cal-d:active{transform:scale(.9)}
.cal-d.other{color:var(--text3);opacity:.4}
.cal-d.today{font-weight:700;box-shadow:inset 0 0 0 2px var(--accent)}
.cal-d .mood-dot{display:inline-block;width:28px;height:28px;border-radius:50%;line-height:28px;font-size:13px}
/* STATS */
.stat-row{display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap}
.stat-box{flex:1;min-width:88px;background:var(--input-bg);border-radius:12px;padding:10px;text-align:center;border:1px solid var(--border)}
.stat-box .val{font-size:1.25em;font-weight:700;color:var(--text)}
.stat-box .lbl{font-size:.62em;color:var(--text3);margin-top:2px;text-transform:uppercase}
.stat-bar{display:flex;height:20px;border-radius:10px;overflow:hidden;margin:8px 0}
.stat-bar div{transition:width .5s ease}
.stat-leg{display:flex;flex-wrap:wrap;gap:4px 12px;margin-top:6px}
.stat-leg span{font-size:.75em;color:var(--text2)}
.stat-leg .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:3px}
.corr-row{display:flex;justify-content:space-between;align-items:center;padding:6px 0;border-bottom:1px solid var(--border);font-size:.85em}
.corr-row:last-child{border:none}
.corr-row .bar{height:8px;border-radius:4px;background:var(--accent);flex:1;margin:0 10px;min-width:20px}
.delta{font-size:.8em;font-weight:600}
.delta.up{color:var(--good-text)}.delta.down{color:var(--danger)}
/* MODAL */
.modal-over{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.4);z-index:200;display:flex;align-items:flex-end;justify-content:center;opacity:0;pointer-events:none;transition:opacity .25s}
.modal-over.show{opacity:1;pointer-events:auto}
.modal{background:var(--card);border-radius:20px 20px 0 0;padding:20px;width:100%;max-width:500px;max-height:88vh;overflow-y:auto;transform:translateY(100%);transition:transform .25s ease}
.modal-over.show .modal{transform:translateY(0)}
.modal h3{font-size:1em;color:var(--text);margin-bottom:12px}
.modal .m-close{float:right;background:none;border:none;font-size:1.2em;color:var(--text3);cursor:pointer;padding:4px}
.empty{text-align:center;color:var(--text3);padding:20px;font-size:.85em}
.export-btn{display:block;text-align:center;padding:10px;background:var(--input-bg);border:2px solid var(--border);border-radius:10px;color:var(--accent);font-size:.85em;font-weight:500;cursor:pointer;margin-top:6px;transition:all .15s}
.export-btn:active{transform:scale(.97)}
@media(max-width:380px){.qt .e{font-size:1.45em}.qt .l{font-size:.55em}.cal-d{min-height:34px}}
</style>
</head>
<body>
<div class="hdr">
  <h1>📓 Mood</h1>
  <div class="hdr-r">
    <span class="streak" id="streak" style="display:none"></span>
    <button class="dm-btn" id="install-btn" style="display:none" onclick="doInstall()" title="Installer l'app" aria-label="Installer l'application">📲</button>
    <button class="dm-btn" id="dm-btn" onclick="togDark()" title="Thème" aria-label="Changer de thème">🌙</button>
  </div>
</div>

<div class="tabs" id="tabs">
  <div class="tab act" data-tab="today" onclick="swTab('today')">📝 Aujourd'hui</div>
  <div class="tab" data-tab="cal" onclick="swTab('cal')">📅 Calendrier</div>
  <div class="tab" data-tab="stats" onclick="swTab('stats')">📊 Stats</div>
  <div class="tab" data-tab="search" onclick="swTab('search')">🔎</div>
</div>

<div class="c">
<div class="tab-c act" id="tab-today">
  <div class="card">
    <h2>😊 Comment ça va ?</h2>
    <div class="q1t-hint">Un tap suffit pour enregistrer</div>
    <div class="q1t" id="q1t"></div>
    <div class="det-toggle" id="det-toggle" onclick="toggleDet()">＋ Ajouter des détails</div>
    <div class="det" id="det">
      <div class="grp"><label>⚡ Énergie</label><div class="energy" id="energy"></div></div>
      <div class="grp"><label>🏷️ États</label><div class="chips" id="etats"></div></div>
      <div class="grp"><label>🎯 Activités</label><div class="chips" id="activites"></div></div>
      <div class="grp"><label>📚 Lecture</label><input class="field" id="lecture" placeholder="ex: Dune p.45"></div>
      <div class="grp"><label>📺 Série</label><input class="field" id="serie" placeholder="ex: Silo S3E4"></div>
      <div class="grp"><label>📝 Notes</label><textarea class="field" id="notes" placeholder="Notes libres..."></textarea></div>
      <div class="btn-row">
        <button class="sb" id="sb" onclick="saveDetails()">💾 Enregistrer les détails</button>
        <button class="db" id="db" onclick="delToday()" style="display:none;flex:0 0 60px">🗑️</button>
      </div>
      <div id="st"></div>
    </div>
  </div>
  <div class="card">
    <h2>📅 7 derniers jours</h2>
    <div id="trend"></div>
    <div id="hist"></div>
  </div>
</div>

<div class="tab-c" id="tab-cal">
  <div class="card">
    <div class="cal-nav">
      <button onclick="calMove(-1)" aria-label="Mois précédent">◀</button>
      <span class="m-title" id="cal-title"></span>
      <button onclick="calMove(1)" aria-label="Mois suivant">▶</button>
    </div>
    <div class="cal-grid" id="cal-grid"></div>
  </div>
  <div class="card">
    <h2 id="cal-day-title">Sélectionne un jour</h2>
    <div id="cal-detail"></div>
  </div>
</div>

<div class="tab-c" id="tab-stats">
  <div class="card"><h2>📊 Résumé</h2><div id="stats-summary"></div></div>
  <div class="card"><h2>📈 Répartition de l'humeur</h2><div id="stats-dist"></div></div>
  <div class="card"><h2>📈 Tendance mensuelle</h2><div id="stats-trend"></div></div>
  <div class="card"><h2>🎯 Humeur par activité</h2><div id="stats-corr"></div></div>
  <div class="card"><h2>💾 Données</h2><div class="export-btn" onclick="expCSV()">⬇️ Exporter en CSV</div></div>
</div>

<div class="tab-c" id="tab-search">
  <div class="card">
    <h2>🔎 Rechercher</h2>
    <input class="field" id="q" placeholder="Notes, série, lecture, activité..." oninput="doSearch()" aria-label="Recherche">
    <div id="search-results"><div class="empty">Tape un mot-clé pour chercher dans tout l'historique</div></div>
  </div>
</div>
</div>

<div class="modal-over" id="modal">
  <div class="modal">
    <button class="m-close" onclick="closeMod()" aria-label="Fermer">✕</button>
    <h3 id="mod-title">Modifier</h3>
    <input type="hidden" id="mod-date">
    <div class="grp"><label>😊 Humeur</label><div class="q1t" id="mod-moods"></div></div>
    <div class="grp"><label>⚡ Énergie</label><div class="energy" id="mod-energy"></div></div>
    <div class="grp"><label>🏷️ États</label><div class="chips" id="mod-etats"></div></div>
    <div class="grp"><label>🎯 Activités</label><div class="chips" id="mod-activites"></div></div>
    <div class="grp"><label>📚 Lecture</label><input class="field" id="mod-lecture" placeholder="📚 Lecture"></div>
    <div class="grp"><label>📺 Série</label><input class="field" id="mod-serie" placeholder="📺 Série"></div>
    <div class="grp"><label>📝 Notes</label><textarea class="field" id="mod-notes" placeholder="Notes libres..."></textarea></div>
    <div class="btn-row">
      <button class="sb" onclick="modSave()">💾 Enregistrer</button>
      <button class="db" onclick="modDel()" style="flex:0 0 60px">🗑️</button>
    </div>
    <div id="mod-st"></div>
  </div>
</div>

<script>
// === UTILS ===
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');}
function localDate(){var d=new Date();return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0');}
var META={moods:[],etats:[],activites:[]};
var selH=null, selE=null, selEtats=[], selActs=[], mH=null, mE=null, mEtats=[], mActs=[];
var calY,calM,editDate=null,editMode='edit';

// === INIT UI ===
function buildPicker(containerId, items, onclickName, selected){
  var h='';
  for(var i=0;i<items.length;i++){
    var it=items[i];
    var on=(selected&&selected.indexOf(it.v)>=0)?' sel':'';
    h+='<div class="qt'+on+'" data-v="'+it.v+'" onclick="'+onclickName+'(this)"><span class="e">'+it.e+'</span><span class="l">'+esc(it.l)+'</span></div>';
  }
  document.getElementById(containerId).innerHTML=h;
}
function buildChips(containerId, items, onclickName, selected, allowAdd){
  var h='';
  for(var i=0;i<items.length;i++){
    var it=items[i];
    var on=(selected&&selected.indexOf(it.k)>=0)?' sel':'';
    h+='<div class="chip'+on+'" data-k="'+esc(it.k)+'" onclick="'+onclickName+'(this)">'+(it.e?it.e+' ':'')+esc(it.l)+'</div>';
  }
  if(allowAdd) h+='<div class="chip add" onclick="addActivity()">＋ Ajouter</div>';
  document.getElementById(containerId).innerHTML=h;
}
function buildEnergy(containerId, onclickName, selected){
  var h='';
  for(var i=1;i<=5;i++){
    var on=(selected===i)?' sel':'';
    h+='<div class="eb'+on+'" data-v="'+i+'" onclick="'+onclickName+'(this)">'+i+'</div>';
  }
  document.getElementById(containerId).innerHTML=h;
}

// === DARK MODE ===
(function(){
  var p=(window.matchMedia?window.matchMedia('(prefers-color-scheme:dark)'):{matches:false,addEventListener:function(){}});
  var d=document.documentElement;
  var saved=localStorage.getItem('mood-theme');
  if(saved) d.dataset.theme=saved; else d.dataset.theme=p.matches?'dark':'light';
  document.getElementById('dm-btn').textContent=d.dataset.theme==='dark'?'☀️':'🌙';
})();
function togDark(){
  var d=document.documentElement;
  var t=d.dataset.theme==='dark'?'light':'dark';
  d.dataset.theme=t; localStorage.setItem('mood-theme',t);
  document.getElementById('dm-btn').textContent=t==='dark'?'☀️':'🌙';
}

// === TABS ===
function swTab(t){
  var i;
  var tabs=document.querySelectorAll('.tab'); for(i=0;i<tabs.length;i++) tabs[i].classList.remove('act');
  var cs=document.querySelectorAll('.tab-c'); for(i=0;i<cs.length;i++) cs[i].classList.remove('act');
  document.querySelector('.tab[data-tab="'+t+'"]').classList.add('act');
  document.getElementById('tab-'+t).classList.add('act');
  if(t==='cal') renderCal();
  if(t==='stats') loadStats();
}

// === SELECTION (today) ===
function pickH(el){ selH=parseInt(el.dataset.v,10); quickSave(); }
function pickE(el){
  var v=parseInt(el.dataset.v,10); selE=(selE===v)?null:v;
  var els=document.querySelectorAll('#energy .eb');
  for(var i=0;i<els.length;i++) els[i].classList.toggle('sel', parseInt(els[i].dataset.v,10)===selE);
}
function pickEtat(el){ toggleIn(el,'etats',function(v){selEtats=v;}); }
function pickAct(el){ toggleIn(el,'activites',function(v){selActs=v;}); }
function toggleIn(el,containerId,setter){
  el.classList.toggle('sel');
  var k=el.dataset.k;
  var els=document.querySelectorAll('#'+containerId+' .chip');
  var out=[];
  for(var i=0;i<els.length;i++){ if(els[i].classList.contains('sel')) out.push(els[i].dataset.k); }
  setter(out);
}
function addActivity(){
  var raw=prompt('Nouvelle activité :');
  if(!raw) return;
  var label=raw.trim();
  if(!label) return;
  var k=label.toLowerCase();
  var exists=false;
  for(var i=0;i<META.activites.length;i++){ if(META.activites[i].k===k) exists=true; }
  if(!exists){
    META.activites.push({k:k,l:label,e:'🏷️'});
    var custom=JSON.parse(localStorage.getItem('mood-custom-acts')||'[]');
    if(custom.indexOf(label)<0){ custom.push(label); localStorage.setItem('mood-custom-acts',JSON.stringify(custom)); }
  }
  if(selActs.indexOf(k)<0) selActs.push(k);
  buildChips('activites',META.activites,'pickAct',selActs,true);
}
function toggleDet(){
  var d=document.getElementById('det');
  d.classList.toggle('open');
  document.getElementById('det-toggle').textContent=d.classList.contains('open')?'－ Masquer les détails':'＋ Ajouter des détails';
}

// === SAVE (1 tap) ===
async function quickSave(){
  if(!selH){return;}
  var payload={humeur:selH};
  try{
    var r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    var j=await r.json();
    if(j.ok){ flash('✅ '+labelH(selH)+' enregistré'); loadToday(); }
    else flash('❌ Erreur');
  }catch(e){ queueSave('POST','/save',payload); flash('📶 Hors-ligne — noté, synchro en attente'); }
}
function flash(msg){
  var el=document.getElementById('st');
  el.className='succ'; el.textContent=msg;
  setTimeout(function(){ el.className=''; el.textContent=''; },2500);
}
function labelH(v){ for(var i=0;i<META.moods.length;i++){ if(META.moods[i].v===v) return META.moods[i].e+' '+META.moods[i].l; } return ''; }
function labelTxt(v){ for(var i=0;i<META.moods.length;i++){ if(META.moods[i].v===v) return META.moods[i].l; } return ''; }
function monthLabel(ym){
  var M=['janv.','févr.','mars','avr.','mai','juin','juil.','août','sept.','oct.','nov.','déc.'];
  var p=String(ym).split('-');
  var i=parseInt(p[1],10)-1;
  return (M[i]||p[1]||ym)+(p[0]?' '+String(p[0]).slice(2):'');
}

// === SAVE (details) ===
async function saveDetails(){
  if(!selH){ flash('Choisis une humeur !'); document.getElementById('st').className='err'; return; }
  var sb=document.getElementById('sb'); sb.disabled=true;
  var d={humeur:selH, energie:selE, etats:selEtats, activites:selActs,
         lecture:document.getElementById('lecture').value.trim(),
         serie:document.getElementById('serie').value.trim(),
         notes:document.getElementById('notes').value.trim()};
  try{
    var r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
    var j=await r.json();
    if(j.ok){ document.getElementById('st').className='succ'; document.getElementById('st').textContent='✅ Enregistré !'; loadToday(); }
    else throw 0;
  }catch(e){ document.getElementById('st').className='err'; document.getElementById('st').textContent='❌ Erreur'; }
  sb.disabled=false;
}
async function delToday(){
  if(!confirm("Supprimer l'entrée d'aujourd'hui ?")) return;
  try{
    var r=await fetch('/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({date:localDate()})});
    var j=await r.json();
    if(j.ok){ flash('🗑️ Supprimé'); loadToday(); }
    else flash('❌ Erreur');
  }catch(e){ flash('❌ Erreur'); }
}

// === LOAD TODAY ===
async function loadToday(){
  var r=await fetch('/data'); var d=await r.json();
  META=d.meta||META;
  var custom=JSON.parse(localStorage.getItem('mood-custom-acts')||'[]');
  for(var c=0;c<custom.length;c++){
    var k=custom[c].toLowerCase(), found=false;
    for(var a=0;a<META.activites.length;a++){ if(META.activites[a].k===k) found=true; }
    if(!found) META.activites.push({k:k,l:custom[c],e:'🏷️'});
  }
  buildPicker('q1t',META.moods,'pickH',selH?[selH]:[]);
  buildEnergy('energy','pickE',selE);
  buildChips('etats',META.etats,'pickEtat',selEtats,false);
  buildChips('activites',META.activites,'pickAct',selActs,true);
  // streak
  if(d.streak>0){ var se=document.getElementById('streak'); se.style.display='inline-block'; se.textContent='🔥 '+d.streak+' j'+(d.record?' (rec. '+d.record+')':''); }
  // trend
  var h='<div class="hw">';
  for(var i=0;i<d.trend.length;i++){
    var day=d.trend[i];
    var em=day.h?emojiH(day.h):'—';
    var bg=day.h?colorH(day.h):'var(--border)';
    h+='<div class="hc"><div class="hd" style="background:'+bg+'">'+em+'</div><div class="hl">'+esc(String(day.d).slice(5))+'</div></div>';
  }
  h+='</div>';
  document.getElementById('trend').innerHTML=h;
  // history
  var h2='';
  for(var j=0;j<d.entries.length;j++){
    var e=d.entries[j];
    h2+='<div class="hp" onclick="openEdit(\''+esc(e.date)+'\')"><div class="d">'+esc(String(e.date).slice(5))+'</div><div class="t">'+emojiH(e.humeur)+' '+esc(e.text)+(e.note?'<br><span class="s">'+esc(e.note)+'</span>':'')+'</div></div>';
  }
  document.getElementById('hist').innerHTML=h2||'<div class="empty">Rien noté ces 7 derniers jours — un tap suffit 🙂</div>';
  // prefill
  var t=d.today;
  selH=t?t.humeur:null; selE=t&&t.energie?t.energie:null;
  selEtats=t?(t.etats||[]).slice():[]; selActs=t?(t.activites||[]).slice():[];
  if(selH){ var qs=document.querySelectorAll('#q1t .qt'); for(var k2=0;k2<qs.length;k2++) qs[k2].classList.toggle('sel',parseInt(qs[k2].dataset.v,10)===selH); }
  var eb=document.querySelectorAll('#energy .eb'); for(var k3=0;k3<eb.length;k3++) eb[k3].classList.toggle('sel',parseInt(eb[k3].dataset.v,10)===selE);
  buildChips('etats',META.etats,'pickEtat',selEtats,false);
  buildChips('activites',META.activites,'pickAct',selActs,true);
  document.getElementById('lecture').value=t?(t.lecture||''):'';
  document.getElementById('serie').value=t?(t.serie||''):'';
  document.getElementById('notes').value=t?(t.notes||''):'';
  document.getElementById('db').style.display=t?'block':'none';
}
function emojiH(v){ for(var i=0;i<META.moods.length;i++){ if(META.moods[i].v===v) return META.moods[i].e; } return '—'; }
function colorH(v){ var c={1:'#ff6b6b',2:'#ffa94d',3:'#ffd43b',4:'#74b816',5:'#2b8a3e'}; return c[v]||'#ccc'; }
loadToday().then(function(){
  // lien 1-tap depuis le rappel : /?h=4 enregistre l'humeur au chargement
  var mh=location.search.match(/[?&]h=([1-5])/);
  if(mh){ selH=parseInt(mh[1],10); quickSave(); if(history.replaceState){ try{history.replaceState(null,'',location.pathname);}catch(e){} } }
});

// === CALENDAR ===
(function(){ var n=new Date(); calY=n.getFullYear(); calM=n.getMonth(); })();
function calMove(d){ calM+=d; if(calM>11){calM=0;calY++;} if(calM<0){calM=11;calY--;} renderCal(); }
async function renderCal(){
  var r=await fetch('/calendar?y='+calY+'&m='+calM); var d=await r.json();
  document.getElementById('cal-title').textContent=(d.month_name||d.month)+' '+d.year;
  var h='<div class="cal-hd">L</div><div class="cal-hd">M</div><div class="cal-hd">M</div><div class="cal-hd">J</div><div class="cal-hd">V</div><div class="cal-hd">S</div><div class="cal-hd">D</div>';
  var today=localDate();
  for(var i=0;i<d.offset;i++) h+='<div class="cal-d other"></div>';
  for(var k=0;k<d.days.length;k++){
    var day=d.days[k];
    var ds=d.year+'-'+String(d.month+1).padStart(2,'0')+'-'+String(day.day).padStart(2,'0');
    var cls='cal-d'+(ds===today?' today':'');
    if(day.humeur){
      var c=colorH(day.humeur);
      h+='<div class="'+cls+'" onclick="calDay(\''+ds+'\')" style="background:'+c+'20"><span class="mood-dot">'+emojiH(day.humeur)+'</span></div>';
    } else {
      h+='<div class="'+cls+'" onclick="calDay(\''+ds+'\')">'+day.day+'</div>';
    }
  }
  document.getElementById('cal-grid').innerHTML=h;
  var withEntry=null;
  for(var m=0;m<d.days.length;m++){ if(d.days[m].humeur){ withEntry=d.days[m]; break; } }
  if(withEntry){
    calDay(d.year+'-'+String(d.month+1).padStart(2,'0')+'-'+String(withEntry.day).padStart(2,'0'));
  } else {
    document.getElementById('cal-day-title').textContent=(d.month_name||d.month)+' '+d.year;
    document.getElementById('cal-detail').innerHTML='<div class="empty">Aucune entrée ce mois</div>';
  }
}
async function calDay(ds){
  document.getElementById('cal-day-title').textContent=ds;
  try{
    var r=await fetch('/get-entry?date='+ds); var j=await r.json();
    if(j.found){
      var e=j.entry;
      var html='<div class="hp"><div class="e-icon">'+emojiH(e.humeur)+'</div><div class="t">';
      if(e.energie) html+='⚡ Énergie '+e.energie+'/5<br>';
      if(e.etats&&e.etats.length) html+='🏷️ '+esc(e.etats.join(', '))+'<br>';
      if(e.activites&&e.activites.length) html+='🎯 '+esc(e.activites.join(', '))+'<br>';
      if(e.lecture) html+='📚 '+esc(e.lecture)+'<br>';
      if(e.serie) html+='📺 '+esc(e.serie)+'<br>';
      if(e.notes) html+='<span class="s">'+esc(e.notes)+'</span>';
      html+='</div></div>';
      html+='<div style="margin-top:8px"><button class="export-btn" onclick="openEdit(\''+ds+'\')">✏️ Modifier</button></div>';
      document.getElementById('cal-detail').innerHTML=html;
    } else {
      document.getElementById('cal-detail').innerHTML='<div class="empty">Aucune entrée pour ce jour.<br><button class="export-btn" style="display:inline;padding:6px 12px;margin-top:8px" onclick="openEdit(\''+ds+'\',\'create\')">＋ Ajouter ce jour</button></div>';
    }
  }catch(e){ document.getElementById('cal-detail').innerHTML='<div class="empty">Erreur</div>'; }
}

// === STATS ===
async function loadStats(){
  try{
    var r=await fetch('/stats'); var d=await r.json();
    var sum='<div class="stat-row">';
    sum+='<div class="stat-box"><div class="val">'+(d.avg!=null?d.avg.toFixed(1):'—')+'</div><div class="lbl">Moyenne /5</div></div>';
    sum+='<div class="stat-box"><div class="val">'+(d.median!=null?d.median:'—')+'</div><div class="lbl">Médiane</div></div>';
    sum+='<div class="stat-box"><div class="val">'+d.total+'</div><div class="lbl">Entrées</div></div>';
    sum+='</div><div class="stat-row">';
    sum+='<div class="stat-box"><div class="val">'+(d.best!=null?emojiH(d.best):'—')+'</div><div class="lbl">Meilleure'+(d.best!=null?'<br>'+esc(labelTxt(d.best)):'')+'</div></div>';
    sum+='<div class="stat-box"><div class="val">'+(d.worst!=null?emojiH(d.worst):'—')+'</div><div class="lbl">Pire'+(d.worst!=null?'<br>'+esc(labelTxt(d.worst)):'')+'</div></div>';
    sum+='<div class="stat-box"><div class="val">🔥 '+d.streak+'</div><div class="lbl">Série</div></div>';
    sum+='<div class="stat-box"><div class="val">'+d.record+'</div><div class="lbl">Record</div></div>';
    sum+='</div>';
    if(d.m7!=null){
      sum+='<div class="stat-row"><div class="stat-box" style="flex:1 1 100%"><div class="val">'+(d.m7.toFixed(1))+'/5';
      if(d.delta!=null){ sum+=' <span class="delta '+(d.delta>=0?'up':'down')+'">'+(d.delta>=0?'▲ +':'▼ ')+d.delta.toFixed(1)+'</span>'; }
      sum+='</div><div class="lbl">Moyenne 7 jours'+(d.delta!=null?' (vs 7 j précédents)':'')+'</div></div></div>';
    }
    document.getElementById('stats-summary').innerHTML=sum;
    // répartition
    if(d.dist&&d.dist.length){
      var mx=1; for(var i=0;i<d.dist.length;i++){ if(d.dist[i].c>mx) mx=d.dist[i].c; }
      var bar='<div class="stat-bar">';
      for(var j=0;j<d.dist.length;j++){ var pct=Math.round(d.dist[j].c/mx*100); bar+='<div style="flex:'+pct+';background:'+colorH(d.dist[j].v)+';height:20px" title="'+esc(d.dist[j].l)+': '+d.dist[j].c+'"></div>'; }
      bar+='</div><div class="stat-leg">';
      for(var k=0;k<d.dist.length;k++){ bar+='<span><span class="dot" style="background:'+colorH(d.dist[k].v)+'"></span>'+emojiH(d.dist[k].v)+' '+esc(d.dist[k].l)+' ('+d.dist[k].c+')</span>'; }
      bar+='</div>';
      document.getElementById('stats-dist').innerHTML=bar;
    } else document.getElementById('stats-dist').innerHTML='<div class="empty">Pas assez de données</div>';
    // tendance
    if(d.monthly&&d.monthly.length){
      var th='<div class="hw">';
      for(var m=0;m<d.monthly.length;m++){
        var mo=d.monthly[m];
        var em=mo.avg?emojiH(Math.round(mo.avg)):'—';
        th+='<div class="hc"><div class="hd" style="background:'+(mo.avg?colorH(Math.round(mo.avg)):'var(--border)')+'">'+em+'</div><div class="hl">'+esc(monthLabel(mo.label))+'</div></div>';
      }
      th+='</div>';
      document.getElementById('stats-trend').innerHTML=th;
    } else document.getElementById('stats-trend').innerHTML='<div class="empty">Pas assez de données</div>';
    // corrélation
    if(d.corr&&d.corr.length){
      var ch=''; var mxv=5;
      for(var c=0;c<d.corr.length;c++){
        var it=d.corr[c];
        ch+='<div class="corr-row"><span style="min-width:90px">'+esc(it.label)+'</span><span class="bar" style="max-width:'+Math.round(it.avg/mxv*100)+'%"></span><b>'+it.avg.toFixed(1)+'</b><span style="color:var(--text3);font-size:.75em;margin-left:6px">('+it.n+')</span></div>';
      }
      document.getElementById('stats-corr').innerHTML=ch;
    } else document.getElementById('stats-corr').innerHTML='<div class="empty">Ajoute des activités pour voir ce qui influence ton humeur</div>';
  }catch(e){ document.getElementById('stats-summary').innerHTML='<div class="empty">Erreur de chargement</div>'; }
}

// === EXPORT ===
async function expCSV(){
  try{
    var r=await fetch('/export'); var blob=await r.blob();
    var a=document.createElement('a'); a.href=URL.createObjectURL(blob);
    a.download='mood-export-'+localDate()+'.csv'; a.click(); URL.revokeObjectURL(a.href);
  }catch(e){ alert('Erreur export'); }
}

// === MODAL ===
async function openEdit(dateStr,mode){
  editDate=dateStr; editMode=mode||'edit';
  document.getElementById('mod-date').value=dateStr;
  document.getElementById('mod-title').textContent=editMode==='create'?'＋ '+dateStr:'✏️ '+dateStr;
  mH=null; mE=null; mEtats=[]; mActs=[];
  buildPicker('mod-moods',META.moods,'modPick',[]);
  buildEnergy('mod-energy','modPickE',null);
  buildChips('mod-etats',META.etats,'modPickEtat',[],false);
  buildChips('mod-activites',META.activites,'modPickAct',[],true);
  document.getElementById('mod-lecture').value='';
  document.getElementById('mod-serie').value='';
  document.getElementById('mod-notes').value='';
  document.getElementById('mod-st').className='';
  document.getElementById('mod-st').textContent='';
  try{
    var r=await fetch('/get-entry?date='+dateStr); var j=await r.json();
    if(j.found){
      var e=j.entry;
      mH=e.humeur||null; mE=e.energie||null; mEtats=(e.etats||[]).slice(); mActs=(e.activites||[]).slice();
      var qs=document.querySelectorAll('#mod-moods .qt'); for(var i=0;i<qs.length;i++) qs[i].classList.toggle('sel',parseInt(qs[i].dataset.v,10)===mH);
      var eb=document.querySelectorAll('#mod-energy .eb'); for(var k=0;k<eb.length;k++) eb[k].classList.toggle('sel',parseInt(eb[k].dataset.v,10)===mE);
      buildChips('mod-etats',META.etats,'modPickEtat',mEtats,false);
      buildChips('mod-activites',META.activites,'modPickAct',mActs,true);
      document.getElementById('mod-lecture').value=e.lecture||'';
      document.getElementById('mod-serie').value=e.serie||'';
      document.getElementById('mod-notes').value=e.notes||'';
    }
  }catch(e){}
  document.getElementById('modal').classList.add('show');
}
function modPick(el){ var qs=document.querySelectorAll('#mod-moods .qt'); for(var i=0;i<qs.length;i++) qs[i].classList.remove('sel'); el.classList.add('sel'); mH=parseInt(el.dataset.v,10); }
function modPickE(el){ var v=parseInt(el.dataset.v,10); mE=(mE===v)?null:v; var eb=document.querySelectorAll('#mod-energy .eb'); for(var i=0;i<eb.length;i++) eb[i].classList.toggle('sel',parseInt(eb[i].dataset.v,10)===mE); }
function modPickEtat(el){ toggleIn(el,'mod-etats',function(v){mEtats=v;}); }
function modPickAct(el){ toggleIn(el,'mod-activites',function(v){mActs=v;}); }
async function modSave(){
  if(!mH){ document.getElementById('mod-st').className='err'; document.getElementById('mod-st').textContent='Choisis une humeur !'; return; }
  var d={date:editDate,humeur:mH,energie:mE,etats:mEtats,activites:mActs,
         lecture:document.getElementById('mod-lecture').value.trim(),
         serie:document.getElementById('mod-serie').value.trim(),
         notes:document.getElementById('mod-notes').value.trim()};
  try{
    var r=await fetch('/update',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
    var j=await r.json();
    if(j.ok){ closeMod(); loadToday(); renderCal(); }
    else throw 0;
  }catch(e){ document.getElementById('mod-st').className='err'; document.getElementById('mod-st').textContent='❌ Erreur'; }
}
async function modDel(){
  if(!confirm('Supprimer cette entrée ?')) return;
  try{
    var r=await fetch('/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({date:editDate})});
    var j=await r.json();
    if(j.ok){ closeMod(); loadToday(); renderCal(); }
    else alert('Erreur');
  }catch(e){ alert('Erreur'); }
}
function closeMod(){ document.getElementById('modal').classList.remove('show'); editDate=null; }

// === PWA ===
if('serviceWorker' in navigator){ try{ navigator.serviceWorker.register('/sw.js').catch(function(){}); }catch(e){} }
var deferredInstall=null;
window.addEventListener('beforeinstallprompt',function(e){ e.preventDefault(); deferredInstall=e; var b=document.getElementById('install-btn'); if(b) b.style.display='inline-block'; });
window.addEventListener('appinstalled',function(){ var b=document.getElementById('install-btn'); if(b) b.style.display='none'; });
function doInstall(){
  if(deferredInstall){ deferredInstall.prompt(); deferredInstall=null; var b=document.getElementById('install-btn'); if(b) b.style.display='none'; }
  else alert("Pour installer : ouvre le menu du navigateur puis « Ajouter à l'écran d'accueil ».");
}

// === HORS-LIGNE : file d'attente des saisies ===
function queueSave(method,url,payload){
  try{ var q=JSON.parse(localStorage.getItem('mood-pending')||'[]'); q.push({m:method,u:url,d:payload}); localStorage.setItem('mood-pending',JSON.stringify(q)); }catch(e){}
}
async function flushPending(){
  var q; try{ q=JSON.parse(localStorage.getItem('mood-pending')||'[]'); }catch(e){ q=[]; }
  if(!q.length) return;
  var rest=[];
  for(var i=0;i<q.length;i++){
    var sent=false;
    try{
      var r=await fetch(q[i].u,{method:q[i].m,headers:{'Content-Type':'application/json'},body:JSON.stringify(q[i].d)});
      sent=r.ok;
    }catch(e){ sent=false; }
    if(!sent) rest.push(q[i]);
  }
  try{ localStorage.setItem('mood-pending',JSON.stringify(rest)); }catch(e){}
}
window.addEventListener('online',function(){ flushPending().then(function(){ loadToday(); }); });
flushPending();

// === RECHERCHE ===
async function doSearch(){
  var q=document.getElementById('q').value.trim();
  var box=document.getElementById('search-results');
  if(!q){ box.innerHTML='<div class="empty">Tape un mot-clé pour chercher dans tout l\'historique</div>'; return; }
  try{
    var r=await fetch('/search?q='+encodeURIComponent(q)); var d=await r.json();
    if(!d.count){ box.innerHTML='<div class="empty">Aucun résultat</div>'; return; }
    var h='';
    for(var i=0;i<d.results.length;i++){
      var e=d.results[i], parts=[];
      if(e.activites&&e.activites.length) parts.push('🎯 '+e.activites.join(', '));
      if(e.lecture) parts.push('📚 '+e.lecture);
      if(e.serie) parts.push('📺 '+e.serie);
      if(e.notes) parts.push(e.notes);
      h+='<div class="hp" onclick="openEdit(\''+esc(e.date)+'\')"><div class="d">'+esc(String(e.date).slice(5))+'</div><div class="t">'+emojiH(e.humeur)+' '+esc(parts.join(' — '))+'</div></div>';
    }
    box.innerHTML=h;
  }catch(err){ box.innerHTML='<div class="empty">Erreur</div>'; }
}
</script>
</body></html>
"""

class Handler(BaseHTTPRequestHandler):
    # ------------------------------------------------------------ sécurité
    def _cookies(self):
        out = {}
        for part in (self.headers.get('Cookie') or '').split(';'):
            if '=' in part:
                k, v = part.split('=', 1)
                out[k.strip()] = v.strip()
        return out

    def _authed(self):
        if not SESSION_VALUE:
            return False
        return hmac.compare_digest(self._cookies().get(COOKIE_NAME, ''), SESSION_VALUE)

    def _require_auth(self):
        if self._authed():
            return True
        nxt = self.path if self.path.startswith('/') and not self.path.startswith('//') else '/'
        self._redirect('/login?next=' + urllib.parse.quote(nxt, safe=''))
        return False

    def _read_body(self):
        """Lit et valide le corps JSON (plafonné). Retourne dict, ou None si invalide."""
        try:
            length = int(self.headers.get('Content-Length', 0) or 0)
        except (TypeError, ValueError):
            return None
        if length < 0 or length > MAX_BODY:
            return None
        if not length:
            return {}
        try:
            data = json.loads(self.rfile.read(length))
        except (ValueError, OSError):
            return None
        return data if isinstance(data, dict) else None

    def _redirect(self, where):
        self.send_response(303)
        self.send_header('Location', where)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def _load_entry(self, date_str):
        fpath = safe_date(date_str)
        if not fpath or not os.path.exists(fpath):
            return None
        try:
            with open(fpath) as f:
                return json.load(f)
        except (ValueError, OSError):
            return None

    # ------------------------------------------------------------ routage
    def do_GET(self):
        try:
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            if parsed.path == '/login':
                self._html(LOGIN_HTML)
                return
            STATIC = {
                '/manifest.json': ('manifest.json', 'application/manifest+json'),
                '/sw.js': ('sw.js', 'application/javascript; charset=utf-8'),
                '/icon-192.png': ('icon-192.png', 'image/png'),
                '/icon-512.png': ('icon-512.png', 'image/png'),
                '/icon-maskable-512.png': ('icon-maskable-512.png', 'image/png'),
                '/apple-touch-icon.png': ('apple-touch-icon.png', 'image/png'),
            }
            if parsed.path in STATIC:
                self._serve_file(*STATIC[parsed.path])
                return
            if parsed.path == '/logout':
                self.send_response(303)
                self.send_header('Set-Cookie', f'{COOKIE_NAME}=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax')
                self.send_header('Location', '/login')
                self.send_header('Content-Length', '0')
                self.end_headers()
                return
            if not self._require_auth():
                return

            if parsed.path == '/data':
                self._handle_data()
            elif parsed.path == '/calendar':
                try:
                    y = int(params.get('y', [today_paris().year])[0])
                    m = int(params.get('m', [today_paris().month - 1])[0])
                except (TypeError, ValueError):
                    self._json({"ok": False, "error": "bad params"}, 400)
                    return
                if not (1970 <= y <= 2200) or not (0 <= m <= 11):
                    self._json({"ok": False, "error": "bad range"}, 400)
                    return
                self._handle_calendar(y, m)
            elif parsed.path == '/get-entry':
                self._handle_get_entry(params.get('date', [''])[0])
            elif parsed.path == '/search':
                self._handle_search(params.get('q', [''])[0])
            elif parsed.path == '/stats':
                self._handle_stats()
            elif parsed.path == '/export':
                self._handle_export()
            else:
                self._html(HTML)
        except Exception:
            self._json({"ok": False, "error": "server"}, 500)

    def do_POST(self):
        try:
            path = urllib.parse.urlparse(self.path).path
            if path == '/login':
                self._handle_login()
                return
            if not self._require_auth():
                return
            body = self._read_body()
            if body is None:
                self._json({"ok": False, "error": "bad body"}, 400)
                return
            if path == '/save':
                self._handle_save(body)
            elif path == '/delete':
                self._handle_delete(body)
            else:
                self._json({"ok": False, "error": "unknown"}, 404)
        except Exception:
            self._json({"ok": False, "error": "server"}, 500)

    def do_PUT(self):
        try:
            if not self._require_auth():
                return
            body = self._read_body()
            if body is None:
                self._json({"ok": False, "error": "bad body"}, 400)
                return
            if urllib.parse.urlparse(self.path).path == '/update':
                self._handle_update(body)
            else:
                self._json({"ok": False, "error": "unknown"}, 404)
        except Exception:
            self._json({"ok": False, "error": "server"}, 500)

    def _handle_login(self):
        try:
            length = int(self.headers.get('Content-Length', 0) or 0)
        except (TypeError, ValueError):
            length = 0
        if length <= 0 or length > MAX_BODY:
            self._redirect('/login?e=1')
            return
        try:
            raw = self.rfile.read(length).decode('utf-8', 'replace')
        except OSError:
            self._redirect('/login?e=1')
            return
        q = urllib.parse.parse_qs(raw)
        token = (q.get('token', [''])[0] or '').strip()
        nxt = (q.get('next', [''])[0] or '')
        if not nxt.startswith('/') or nxt.startswith('//'):
            nxt = '/'
        if SESSION_VALUE and token and hmac.compare_digest(token, MOOD_TOKEN):
            self.send_response(303)
            self.send_header('Set-Cookie',
                             f'{COOKIE_NAME}={SESSION_VALUE}; Path=/; Max-Age=31536000; HttpOnly; SameSite=Lax')
            self.send_header('Location', nxt)
            self.send_header('Content-Length', '0')
            self.end_headers()
        else:
            self._redirect('/login?e=1')

    # ---- HELPERS DONNÉES ----

    def _all_dates(self):
        out = set()
        try:
            for fname in os.listdir(ENTRIES_DIR):
                if not fname.endswith(".json"):
                    continue
                ds = fname[:-5]
                try:
                    date.fromisoformat(ds)
                except ValueError:
                    continue
                out.add(ds)
        except OSError:
            pass
        return out

    def _streaks(self):
        """(série courante, record). La série reste vivante si aujourd'hui n'est pas saisi."""
        dates = self._all_dates()
        if not dates:
            return 0, 0
        today = today_paris()
        start = today if today.isoformat() in dates else today - timedelta(days=1)
        streak = 0
        d = start
        while d.isoformat() in dates:
            streak += 1
            d -= timedelta(days=1)
        ordered = sorted(date.fromisoformat(x) for x in dates)
        record = cur = 1
        for i in range(1, len(ordered)):
            cur = cur + 1 if (ordered[i] - ordered[i - 1]).days == 1 else 1
            record = max(record, cur)
        return streak, max(record, streak)

    def _write_entry(self, date_str, entry):
        fpath = safe_date(date_str)
        if not fpath:
            return False
        try:
            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
            return True
        except OSError:
            return False

    @staticmethod
    def _merge(existing, body, date_str):
        """Fusionne : chaque champ présent dans body remplace l'existant, les autres sont conservés."""
        base = existing or {"date": date_str, "version": 2, "humeur": None,
                            "etats": [], "activites": [], "lecture": "", "serie": "", "notes": ""}
        out = dict(base)
        out["date"] = date_str
        out["version"] = 2
        if "energie" in body:
            try:
                en = int(body["energie"])
            except (TypeError, ValueError):
                en = None
            if en is not None and 1 <= en <= 5:
                out["energie"] = en
            else:
                out.pop("energie", None)
        for k in ("etats", "activites"):
            if k in body:
                v = body[k]
                out[k] = ([str(x).strip().lower() for x in v if str(x).strip()]
                          if isinstance(v, list) else [])
        for k in ("lecture", "serie", "notes"):
            if k in body:
                v = body[k]
                out[k] = v if isinstance(v, str) else ""
        now = datetime.now(PARIS).isoformat()
        out["created_at"] = base.get("created_at") or now
        out["updated_at"] = now
        return out

    @staticmethod
    def _clean_humeur(value):
        try:
            h = int(value)
        except (TypeError, ValueError):
            return None
        return h if 1 <= h <= 5 else None

    # ---- HANDLERS ----

    def _handle_data(self):
        today = today_paris()
        entries, trend, today_data = [], [], None
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            ds = d.isoformat()
            e = self._load_entry(ds)
            day = {"d": ds, "h": None}
            if e:
                ne = normalize_entry(e)
                if ne and ne["humeur"]:
                    day["h"] = ne["humeur"]
                    parts = []
                    if ne["activites"]:
                        parts.append("🎯 " + ", ".join(ACT_LABEL.get(a, a) for a in ne["activites"]))
                    if ne["lecture"]:
                        parts.append("📚 " + ne["lecture"])
                    if ne["serie"]:
                        parts.append("📺 " + ne["serie"])
                    entries.append({"date": ds, "humeur": ne["humeur"],
                                    "text": " — ".join(parts), "note": ne["notes"]})
                    if d == today:
                        today_data = ne
            trend.append(day)
        streak, record = self._streaks()
        self._json({"entries": entries[:7], "trend": trend, "today": today_data,
                    "streak": streak, "record": record,
                    "meta": {"moods": MOODS, "etats": ETATS, "activites": ACTIVITES}})

    def _handle_save(self, body):
        date_str = today_paris().strftime("%Y-%m-%d")
        existing = self._load_entry(date_str)
        ne = normalize_entry(existing) if existing else None
        humeur = self._clean_humeur(body.get("humeur")) if "humeur" in body else (ne["humeur"] if ne else None)
        if humeur is None:
            self._json({"ok": False, "error": "bad humeur"}, 400)
            return
        entry = self._merge(ne, body, date_str)
        entry["humeur"] = humeur
        if not self._write_entry(date_str, entry):
            self._json({"ok": False, "error": "write"}, 500)
            return
        self._json({"ok": True})

    def _handle_update(self, body):
        date_str = body.get("date", "")
        if not safe_date(date_str):
            self._json({"ok": False, "error": "bad date"}, 400)
            return
        existing = self._load_entry(date_str)
        ne = normalize_entry(existing) if existing else None
        humeur = self._clean_humeur(body.get("humeur")) if "humeur" in body else (ne["humeur"] if ne else None)
        if humeur is None:
            self._json({"ok": False, "error": "bad humeur"}, 400)
            return
        entry = self._merge(ne, body, date_str)
        entry["humeur"] = humeur
        if not self._write_entry(date_str, entry):
            self._json({"ok": False, "error": "write"}, 500)
            return
        self._json({"ok": True})

    def _handle_delete(self, body):
        fpath = safe_date(body.get("date", ""))
        if not fpath:
            self._json({"ok": False, "error": "bad date"}, 400)
            return
        if os.path.exists(fpath):
            os.remove(fpath)
            self._json({"ok": True})
        else:
            self._json({"ok": False, "error": "not found"})

    def _handle_get_entry(self, date_str):
        e = self._load_entry(date_str)
        ne = normalize_entry(e) if e else None
        if ne:
            self._json({"found": True, "entry": ne})
        else:
            self._json({"found": False})

    def _handle_calendar(self, y, m):
        month_names = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                       "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        month_days = calmod.Calendar().monthdays2calendar(y, m + 1)
        offset = calmod.monthrange(y, m + 1)[0]
        days = []
        for week in month_days:
            for day_num, wd in week:
                if day_num == 0:
                    continue
                ds = f"{y:04d}-{m+1:02d}-{day_num:02d}"
                e = self._load_entry(ds)
                ne = normalize_entry(e) if e else None
                days.append({"day": day_num, "wd": wd, "humeur": ne["humeur"] if ne else None})
        self._json({"year": y, "month": m, "month_name": month_names[m],
                    "offset": offset, "days": days})

    def _handle_stats(self):
        today = today_paris()
        try:
            files = os.listdir(ENTRIES_DIR)
        except OSError:
            files = []
        rows = []
        for fname in files:
            if not fname.endswith(".json"):
                continue
            ds = fname[:-5]
            try:
                d = date.fromisoformat(ds)
            except ValueError:
                continue
            e = self._load_entry(ds)
            ne = normalize_entry(e) if e else None
            if ne and ne["humeur"]:
                rows.append({"date": ds, "d": d, "mood": ne["humeur"],
                             "activites": ne["activites"], "energie": ne["energie"]})
        rows.sort(key=lambda x: x["date"])
        total = len(rows)
        if total == 0:
            self._json({"total": 0, "avg": None, "median": None, "best": None, "worst": None,
                        "streak": 0, "record": 0, "m7": None, "delta": None,
                        "dist": [], "monthly": [], "corr": []})
            return
        vals = [r["mood"] for r in rows]
        avg = sum(vals) / len(vals)
        median = sorted(vals)[(len(vals) - 1) // 2]
        last7 = [r["mood"] for r in rows if (today - r["d"]).days <= 6]
        prev7 = [r["mood"] for r in rows if 7 <= (today - r["d"]).days <= 13]
        m7 = sum(last7) / len(last7) if last7 else None
        delta = (m7 - sum(prev7) / len(prev7)) if (last7 and prev7) else None
        dist = {}
        for v in vals:
            dist[v] = dist.get(v, 0) + 1
        dist_list = [{"v": k, "c": c, "l": HUMEUR_LABEL.get(k, "")} for k, c in sorted(dist.items())]
        streak, record = self._streaks()
        monthly = {}
        for r in rows:
            monthly.setdefault(r["date"][:7], []).append(r["mood"])
        monthly_list = [{"label": ym, "avg": sum(v) / len(v)} for ym, v in sorted(monthly.items())][-12:]
        acc = {}
        for r in rows:
            for a in r["activites"]:
                acc.setdefault(a, []).append(r["mood"])
        corr = [{"label": ACT_LABEL.get(a, a), "avg": sum(v) / len(v), "n": len(v)} for a, v in acc.items()]
        corr.sort(key=lambda x: x["avg"], reverse=True)
        self._json({"total": total, "avg": round(avg, 2), "median": median,
                    "best": max(vals), "worst": min(vals), "streak": streak, "record": record,
                    "m7": round(m7, 2) if m7 is not None else None,
                    "delta": round(delta, 2) if delta is not None else None,
                    "dist": dist_list, "monthly": monthly_list, "corr": corr[:8]})

    def _handle_export(self):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["date", "humeur", "energie", "etats", "activites", "lecture", "serie", "notes"])
        try:
            files = sorted(os.listdir(ENTRIES_DIR))
        except OSError:
            files = []
        for fname in files:
            if not fname.endswith(".json"):
                continue
            ds = fname[:-5]
            e = self._load_entry(ds)
            ne = normalize_entry(e) if e else None
            if not ne:
                continue
            w.writerow([ne["date"] or ds, ne["humeur"] or "", ne["energie"] or "",
                        "|".join(ne["etats"]), "|".join(ne["activites"]),
                        ne["lecture"], ne["serie"], ne["notes"]])
        csv_data = buf.getvalue().encode("utf-8-sig")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", "attachment; filename=mood-export.csv")
        self.send_header("Content-Length", str(len(csv_data)))
        self.end_headers()
        self.wfile.write(csv_data)

    def _serve_file(self, fname, ctype):
        path = os.path.join(STATIC_DIR, fname)
        try:
            with open(path, 'rb') as f:
                data = f.read()
        except OSError:
            self.send_response(404)
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def _handle_search(self, query):
        q = (query or "").strip().lower()
        if not q or len(q) > 100:
            self._json({"q": query, "count": 0, "results": []})
            return
        try:
            files = sorted(os.listdir(ENTRIES_DIR), reverse=True)
        except OSError:
            files = []
        results = []
        for fname in files:
            if not fname.endswith(".json"):
                continue
            ds = fname[:-5]
            e = self._load_entry(ds)
            ne = normalize_entry(e) if e else None
            if not ne:
                continue
            hay = " ".join([ne["lecture"], ne["serie"], ne["notes"],
                            " ".join(ne["etats"]), " ".join(ne["activites"]),
                            " ".join(ACT_LABEL.get(a, a) for a in ne["activites"])]).lower()
            if q in hay:
                results.append({"date": ds, "humeur": ne["humeur"], "etats": ne["etats"],
                                "activites": ne["activites"], "lecture": ne["lecture"],
                                "serie": ne["serie"], "notes": ne["notes"]})
            if len(results) >= 50:
                break
        self._json({"q": query, "count": len(results), "results": results})

    def _security_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; style-src 'self' 'unsafe-inline'; "
                         "script-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                         "connect-src 'self'; worker-src 'self'; base-uri 'none'; form-action 'self'; "
                         "frame-ancestors 'none'")

    def _json(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(payload)

    def _html(self, h):
        payload = h.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(payload)))
        self._security_headers()
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a): pass

if __name__ == "__main__":
    PORT = int(os.environ.get("MOOD_PORT", "8080"))
    print(f"🌐 Mood Tracker v3: http://localhost:{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()