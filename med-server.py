#!/usr/bin/env python3
"""Médicaments Tracker — serveur web + API."""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, date, timedelta
import os
import sqlite3
import urllib.parse
import hashlib
import hmac

# ── Auth config ──
APP_USER = "alexis"
APP_PASS = "medoc2026"  # ⚠️ à changer
PASS_HASH = hashlib.sha256(f"{APP_USER}:{APP_PASS}".encode()).hexdigest()
SESSION_COOKIE = "medoc_session"
SESSION_TTL = 60 * 60 * 24  # 24h

# Sessions stockées en mémoire (id -> timestamp)
SESSIONS = {}

def check_auth(self, is_api=False):
    """Vérifie si la requête est authentifiée."""
    cookies = self.headers.get('Cookie', '')
    if SESSION_COOKIE in cookies:
        # Extraire le session id
        for c in cookies.split(';'):
            c = c.strip()
            if c.startswith(SESSION_COOKIE + '='):
                sid = c.split('=', 1)[1]
                ts = SESSIONS.get(sid)
                if ts and (datetime.now().timestamp() - ts) < SESSION_TTL:
                    return True
    return False

DB_PATH = os.path.expanduser("~/.hermes/med-tracker.db")
PORT = 8081

# Init DB
conn = sqlite3.connect(DB_PATH)
conn.execute("""CREATE TABLE IF NOT EXISTS meds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    dosage TEXT,
    notes TEXT,
    morning INTEGER DEFAULT 1,
    midday INTEGER DEFAULT 1,
    evening INTEGER DEFAULT 1,
    active INTEGER DEFAULT 1,
    created_at TEXT DEFAULT (datetime('now'))
)""")
conn.execute("""CREATE TABLE IF NOT EXISTS intakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    med_id INTEGER,
    meal TEXT,
    taken_at TEXT DEFAULT (datetime('now')),
    taken_date TEXT DEFAULT (date('now')),
    FOREIGN KEY(med_id) REFERENCES meds(id)
)""")
conn.commit()
conn.close()

HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>💊 Médicaments</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; padding: 0; max-width: 100%; }
/* Header */
.app-header { background: #fff; padding: 14px 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.06); position: sticky; top: 0; z-index: 100; }
.app-header h1 { font-size: 1.2em; color: #333; text-align: center; }
.logout { position: absolute; right: 16px; top: 12px; font-size: 0.8em; color: #bbb; text-decoration: none; }
/* Onglets */
.tabs { display: flex; background: #fff; border-bottom: 1px solid #eee; }
.tab { flex: 1; padding: 12px 4px; text-align: center; cursor: pointer; font-weight: 600; font-size: 0.8em; color: #888; border-bottom: 3px solid transparent; transition: color .2s; }
.tab.active { color: #007aff; border-bottom-color: #007aff; }
/* Contenu */
.content { padding: 14px 16px 80px; }
.card { background: white; border-radius: 14px; padding: 16px; box-shadow: 0 1px 8px rgba(0,0,0,0.05); margin-bottom: 14px; }
h2 { font-size: 0.95em; color: #666; margin-bottom: 10px; }
/* Stats row */
.stats-row { display: flex; gap: 10px; margin-bottom: 14px; }
.stat-box { flex: 1; background: white; border-radius: 14px; padding: 14px; text-align: center; box-shadow: 0 1px 8px rgba(0,0,0,0.05); }
.stat-box .num { font-size: 1.6em; font-weight: 700; color: #007aff; }
.stat-box .lbl { font-size: 0.7em; color: #999; margin-top: 3px; }
/* Alertes */
.alert-box { background: #fff3cd; border-radius: 10px; padding: 10px 14px; margin-bottom: 14px; font-size: 0.85em; color: #856404; }
.alert-box strong { color: #664d03; }
.alert-box.today-ok { background: #d4edda; color: #155724; }
/* Meds - Today */
.meal-section { margin-bottom: 16px; }
.meal-title { font-size: 1em; font-weight: 600; margin-bottom: 6px; padding: 6px 0; border-bottom: 2px solid #f0f0f0; }
.med-item { display: flex; align-items: center; padding: 14px 0; border-bottom: 1px solid #f0f0f0; }
.med-item:last-child { border-bottom: none; }
.med-item input[type="checkbox"] { width: 26px; height: 26px; margin-right: 12px; cursor: pointer; accent-color: #007aff; flex-shrink: 0; }
.med-item label { flex: 1; font-size: 1em; cursor: pointer; }
.med-item.taken label { text-decoration: line-through; color: #999; }
/* Ajout */
.add-form { display: flex; gap: 8px; margin-bottom: 10px; }
.add-form input { flex: 1; padding: 12px; border: 2px solid #e0e0e0; border-radius: 10px; font-size: 1em; }
.add-form button { padding: 12px 16px; background: #007aff; color: white; border: none; border-radius: 10px; cursor: pointer; font-size: 1em; font-weight: 600; }
.meal-checkboxes { display: flex; gap: 14px; margin: 8px 0; }
.meal-checkboxes label { font-size: 0.85em; color: #666; display: flex; align-items: center; gap: 4px; cursor: pointer; }
.meal-checkboxes input { width: 16px; height: 16px; accent-color: #007aff; }
/* Liste */
.med-list { list-style: none; }
.med-list li { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid #f0f0f0; }
.med-list li:last-child { border-bottom: none; }
.med-list li .del { color: #ff3b30; cursor: pointer; padding: 6px 10px; font-size: 1em; }
.med-list li .info { font-size: 0.8em; color: #999; }
/* Bouton Valider */
.btn-save { width: 100%; padding: 14px; background: #007aff; color: white; border: none; border-radius: 12px; font-size: 1.1em; font-weight: 600; cursor: pointer; margin-top: 6px; }
.btn-save:hover { background: #0056b3; }
select { padding: 8px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 0.9em; }
#status { text-align: center; margin: 8px 0; padding: 8px; border-radius: 10px; display: none; font-size: 0.85em; }
.success { background: #d4edda; color: #155724; }
.error { background: #f8d7da; color: #721c24; }
.tab-content { display: none; }
.tab-content.active { display: block; }
</style>
</head>
<body>
<div class="app-header">
  <h1>💊 Médicaments</h1>
  <a class="logout" href="/logout">Déconnexion</a>
</div>
<div class="tabs">
  <div class="tab active" data-tab="today" onclick="switchTab('today')">📋 Aujourd'hui</div>
  <div class="tab" data-tab="manage" onclick="switchTab('manage')">⚙️ Gérer</div>
  <div class="tab" data-tab="history" onclick="switchTab('history')">📅 Historique</div>
</div>
<div class="content">
<div id="tab-today" class="tab-content active">
  <div id="stats-header"></div>
  <div class="card" id="today-content"></div>
</div>

<div id="tab-manage" class="tab-content">
  <div class="card">
    <h2>➕ Ajouter un médicament</h2>
    <div class="add-form">
      <input type="text" id="new-name" placeholder="Nom du médicament">
      <button onclick="addMed()" style="font-size:1.4em;font-weight:700;padding:8px 18px">+</button>
    </div>
    <div class="meal-checkboxes">
      <label><input type="checkbox" id="m-morning" checked> 🌅 Matin</label>
      <label><input type="checkbox" id="m-midday"> 🌞 Midi</label>
      <label><input type="checkbox" id="m-evening"> 🌙 Soir</label>
    </div>
  </div>
  <div class="card">
    <h2>📋 Liste des médicaments</h2>
    <ul class="med-list" id="med-list"></ul>
  </div>
</div>

<div id="tab-history" class="tab-content">
  <div class="card" id="history-content"></div>
</div>

<div id="status"></div>
</div>

<script>
function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
  document.querySelector(`.tab[data-tab="${name}"]`).classList.add('active');
  document.getElementById('tab-' + name).classList.add('active');
  if (name === 'today') loadToday();
  if (name === 'manage') loadMeds();
  if (name === 'history') loadHistory();
}

async function loadToday() {
  try {
    const resp = await fetch('/api/today?_=' + Date.now());
    if (!resp.ok) { document.getElementById('today-content').innerHTML = '<p style="color:#999;text-align:center">Erreur de chargement</p>'; return; }
    const data = await resp.json();
    const meals = { morning: '🌅 Matin', midday: '🌞 Midi', evening: '🌙 Soir' };
    let html = '<div class="med-day">';
    let hasItems = false;
    for (const [meal, label] of Object.entries(meals)) {
      if (!data[meal] || !data[meal].length) continue;
      hasItems = true;
      html += '<div class="meal-section"><div class="meal-title">' + label + '</div>';
      for (const m of data[meal]) {
        html += '<div class="med-item' + (m.taken ? ' taken' : '') + '">';
        html += '<input type="checkbox" class="med-check" data-id="' + m.id + '" data-meal="' + meal + '" ' + (m.taken ? 'checked' : '') + '>';
        html += '<label>' + m.name + ' <span class="dosage">' + (m.dosage || '') + '</span></label>';
        html += '</div>';
      }
      html += '</div>';
    }
    html += '</div>';
    if (!hasItems) html = '<p style="color:#999;text-align:center">Aucun medicament pour aujourd hui</p>';
    else html += '<button class="btn-save" onclick="saveToday()">✅ Valider les prises</button>';
    document.getElementById('today-content').innerHTML = html;
    loadStats();
  } catch(e) {
    document.getElementById('today-content').innerHTML = '<p style="color:#999;text-align:center">Erreur: ' + e.message + '</p>';
  }
}

async function saveToday() {
  const checks = document.querySelectorAll('.med-check');
  const intakes = [];
  for (const c of checks) {
    intakes.push({id: parseInt(c.dataset.id), meal: c.dataset.meal, taken: c.checked});
  }
  try {
    const resp = await fetch('/api/save', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({intakes}) });
    const data = await resp.json();
    if (data.ok) {
      document.getElementById('today-content').innerHTML += '<div style="text-align:center;color:#22c55e;margin-top:8px">✅ Prises enregistrées</div>';
      loadToday();
    }
  } catch(e) {
    document.getElementById('today-content').innerHTML += '<div style="text-align:center;color:#ef4444;margin-top:8px">❌ Erreur: ' + e.message + '</div>';
  }
}

async function loadStats() {
  const resp = await fetch('/api/stats?_=' + Date.now());
  const data = await resp.json();
  const mealLbl = { morning: 'matin', midday: 'midi', evening: 'soir' };

  let html = '<div class="stats-row">';
  html += '<div class="stat-box" style="flex:2"><div style="font-size:11px;color:#999;margin-bottom:6px">📅 5 derniers jours</div>';
  html += '<div style="display:flex;gap:6px;justify-content:center">';
  if (data.days) {
    for (const d of data.days) {
      const icons = {full:'✅', none:'❌', partial:'⚠️', empty:'—'};
      const colors = {full:'#22c55e', none:'#ef4444', partial:'#eab308', empty:'#555'};
      html += '<div style="text-align:center;min-width:44px">';
      html += '<div style="font-size:18px;color:' + (colors[d.status] || '#555') + '">' + (icons[d.status] || '?') + '</div>';
      html += '<div style="font-size:9px;color:#999;margin-top:1px">' + d.date.slice(5) + '</div>';
      html += '<div style="font-size:8px;color:#666">' + d.n + '</div>';
      html += '</div>';
    }
  }
  html += '</div></div>';
  html += '<div class="stat-box"><div class="num">' + data.today.taken + '/' + data.today.due + '</div><div class="lbl">pris aujourd hui</div></div>';
  html += '</div>';

  if (data.missed && data.missed.length > 0) {
    html += '<div class="alert-box"><strong>⚠️ Prise(s) oubliée(s) :</strong><br>';
    for (const m of data.missed) {
      html += '• ' + m.med + ' (' + mealLbl[m.meal] + ')<br>';
    }
    html += '</div>';
  } else if (data.today.taken >= data.today.due) {
    html += '<div class="alert-box today-ok">✅ Toutes les prises du jour sont effectuées !</div>';
  }

  document.getElementById('stats-header').innerHTML = html;
}

async function toggleMed(id, meal) {
  try {
    await fetch('/api/toggle', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id, meal}) });
  } catch(e) {
    loadToday();
  }
}

async function loadMeds() {
  const [active, disabled] = await Promise.all([
    fetch('/api/meds').then(r=>r.json()),
    fetch('/api/disabled').then(r=>r.json())
  ]);
  const labels = { morning:'🌅', midday:'🌞', evening:'🌙' };
  let html = '<h2>💊 Médicaments actifs</h2>';
  if (active.length) {
    html += '<ul class="med-list">';
    for (const m of active) {
      const meals = [m.morning && labels.morning, m.midday && labels.midday, m.evening && labels.evening].filter(Boolean).join(' ');
      html += '<li><div><strong>' + m.name + '</strong> <span class="info">' + meals + '</span></div><span class="del" onclick="delMed(' + m.id + ')">⏸️</span></li>';
    }
    html += '</ul>';
  } else {
    html += '<p style="color:#999;text-align:center;margin:10px 0">Aucun médicament actif</p>';
  }

  if (disabled.length) {
    html += '<h2 style="margin-top:16px;color:#666">⏸️ Médicaments désactivés</h2>';
    html += '<ul class="med-list">';
    for (const m of disabled) {
      html += '<li><div><strong style="color:#666">' + m.name + '</strong> <span class="info"></span></div><span class="del" onclick="activateMed(' + m.id + ')" style="color:#22c55e">▶️ Réactiver</span></li>';
    }
    html += '</ul>';
  }

  document.getElementById('med-list').innerHTML = html;
}

async function addMed() {
  const name = document.getElementById('new-name').value.trim();
  if (!name) return;
  const morning = document.getElementById('m-morning').checked ? 1 : 0;
  const midday = document.getElementById('m-midday').checked ? 1 : 0;
  const evening = document.getElementById('m-evening').checked ? 1 : 0;
  await fetch('/api/add', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name, morning, midday, evening}) });
  document.getElementById('new-name').value = '';
  document.getElementById('new-dosage').value = '';
  loadMeds();
}

async function delMed(id) {
  if (!confirm('Désactiver ce médicament ?')) return;
  await fetch('/api/delete', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id}) });
  loadMeds();
}

async function activateMed(id) {
  await fetch('/api/activate', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id}) });
  loadMeds();
}

async function loadHistory() {
  const resp = await fetch('/api/history');
  const data = await resp.json();
  const meals = { morning: '🌅', midday: '🌞', evening: '🌙' };
  let html = '';
  for (const day of data.days) {
    html += '<div class="meal-section"><div class="meal-title">📅 ' + day.date + '</div>';
    if (day.intakes.length === 0) {
      html += '<p style="color:#999">Aucune prise</p>';
    } else {
      for (const i of day.intakes) {
        const taken = i.taken === '1' || i.taken === 1;
        html += '<div class="med-item' + (taken ? ' taken' : '') + '">';
        html += '<span>' + (meals[i.meal] || '') + ' ' + i.name + (taken ? ' ✅' : ' ❌') + '</span>';
        html += '</div>';
      }
    }
    html += '</div>';
  }
  document.getElementById('history-content').innerHTML = html;
}

loadToday();
</script>
</body>
</html>"""

# ── Page de login ──
LOGIN_HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>🔐 Connexion - Médicaments</title>
<style>
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; background:#f5f5f5; height:100vh; display:flex; align-items:center; justify-content:center; }
.login-card { background:white; border-radius:16px; padding:30px; box-shadow:0 2px 12px rgba(0,0,0,0.08); width:320px; }
h1 { font-size:1.3em; text-align:center; margin-bottom:20px; color:#333; }
input { width:100%; padding:12px; border:2px solid #e0e0e0; border-radius:10px; font-size:1em; margin-bottom:12px; }
button { width:100%; padding:12px; background:#007aff; color:white; border:none; border-radius:10px; font-size:1em; cursor:pointer; }
button:hover { background:#0056b3; }
.error { color:#ff3b30; text-align:center; margin-top:12px; font-size:0.9em; }
</style>
</head>
<body>
<div class="login-card">
<h1>💊 Médicaments</h1>
<form method="POST" action="/login">
  <input type="text" name="username" placeholder="Utilisateur" required>
  <input type="password" name="password" placeholder="Mot de passe" required>
  <button type="submit">Se connecter</button>
</form>
<div class="error" id="error"></div>
</div>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/login':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(LOGIN_HTML.encode())
        elif self.path == '/logout':
            self._logout()
        elif not check_auth(self):
            # Not authenticated -> redirect to login
            self.send_response(302)
            self.send_header('Location', '/login')
            self.end_headers()
        elif self.path.startswith('/api/today'):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            today = date.today().isoformat()
            meds = c.execute("SELECT id, name, dosage, morning, midday, evening FROM meds WHERE active=1").fetchall()
            taken = {}
            for r in c.execute("SELECT med_id, meal FROM intakes WHERE taken_date=?", (today,)):
                taken[(r[0], r[1])] = True
            result = {"date": today, "morning": [], "midday": [], "evening": []}
            meals = [(3, "morning"), (4, "midday"), (5, "evening")]
            for m in meds:
                for col, meal in meals:
                    if m[col]:
                        entry = {"id": m[0], "name": m[1], "dosage": m[2], "taken": taken.get((m[0], meal), False)}
                        result[meal].append(entry)
            conn.close()
            self._json(result)
        elif self.path.startswith('/api/stats'):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            today = date.today().isoformat()

            # Current streak: count consecutive days where ALL due meds×meals were taken
            meds_all = c.execute("SELECT id, morning, midday, evening FROM meds WHERE active=1").fetchall()
            streak = 0
            for offset in range(0, 365):
                d = (date.today() - timedelta(days=offset)).isoformat()
                # Récupérer les prises par (med_id, meal)
                taken = {}
                for r in c.execute("SELECT med_id, meal FROM intakes WHERE taken_date=?", (d,)):
                    taken[(r[0], r[1])] = True
                # Vérifier si tous les repas de tous les médicaments sont pris
                all_taken = True
                meals_cols = [(1, "morning"), (2, "midday"), (3, "evening")]
                for m in meds_all:
                    for col, meal in meals_cols:
                        if m[col] and not taken.get((m[0], meal)):
                            all_taken = False
                            break
                    if not all_taken:
                        break
                if all_taken:
                    streak += 1
                else:
                    break

            # Today's taken progress (par repas)
            meds_today = c.execute("SELECT id, morning, midday, evening FROM meds WHERE active=1").fetchall()
            taken_today = {}
            for r in c.execute("SELECT med_id, meal FROM intakes WHERE taken_date=?", (today,)):
                taken_today[(r[0], r[1])] = True
            total_due = 0
            total_taken = 0
            for m in meds_today:
                for col, meal in meals_cols:
                    if m[col]:
                        total_due += 1
                        if taken_today.get((m[0], meal)):
                            total_taken += 1

            # Missed alerts (due at past meals today, not taken)
            now_hour = datetime.now().hour
            missed = []
            meal_order = [("morning", 8), ("midday", 12), ("evening", 19)]
            for meal, meal_hour in meal_order:
                if now_hour >= meal_hour:
                    for m in meds_today:
                        if m[{"morning":1,"midday":2,"evening":3}[meal]] and not taken_today.get((m[0], meal)):
                            name = c.execute("SELECT name FROM meds WHERE id=?", (m[0],)).fetchone()[0]
                            missed.append({"med": name, "meal": meal})

            conn.close()
            # Derniers 5 jours : vert (tout pris), rouge (rien pris), orange (partiel)
            days = []
            for offset in range(4, -1, -1):
                d = (date.today() - timedelta(days=offset)).isoformat()
                taken_d = {}
                conn2 = sqlite3.connect(DB_PATH)
                c2 = conn2.cursor()
                for r in c2.execute("SELECT med_id, meal FROM intakes WHERE taken_date=?", (d,)):
                    taken_d[(r[0], r[1])] = True
                total = 0
                pris = 0
                for m in meds_all:
                    for col, meal in meals_cols:
                        if m[col]:
                            total += 1
                            if taken_d.get((m[0], meal)):
                                pris += 1
                conn2.close()
                if total == 0:
                    status = "empty"
                elif pris == total:
                    status = "full"
                elif pris == 0:
                    status = "none"
                else:
                    status = "partial"
                days.append({"date": d, "status": status, "n": f"{pris}/{total}"})
            self._json({
                "streak": streak,
                "today": {"taken": total_taken, "due": max(total_due, 1)},
                "missed": missed,
                "days": days
            })
        elif self.path.startswith('/api/history'):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            today = date.today()
            days = []
            for offset in range(3):
                d = today - timedelta(days=offset)
                ds = d.isoformat()
                intakes = c.execute("""SELECT i.meal, m.name, i.med_id
                    FROM intakes i JOIN meds m ON m.id=i.med_id
                    WHERE i.taken_date=? ORDER BY i.meal""", (ds,)).fetchall()
                days.append({"date": ds, "intakes": [{"meal": r[0], "name": r[1], "taken": 1} for r in intakes]})
            conn.close()
            self._json({"days": days})
        elif self.path.startswith('/api/meds'):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            meds = [{"id":r[0],"name":r[1],"dosage":r[2],"morning":r[3],"midday":r[4],"evening":r[5]} for r in c.execute("SELECT id,name,dosage,morning,midday,evening FROM meds WHERE active=1 ORDER BY name")]
            conn.close()
            self._json(meds)
        elif self.path.startswith('/api/disabled'):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            meds = [{"id":r[0],"name":r[1],"dosage":r[2]} for r in c.execute("SELECT id,name,dosage FROM meds WHERE active=0 ORDER BY name")]
            conn.close()
            self._json(meds)
        else:
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode())

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        body_raw = self.rfile.read(length)

        # Login form (x-www-form-urlencoded)
        if self.path == '/login':
            content_type = self.headers.get('Content-Type', '')
            if 'json' in content_type:
                body = json.loads(body_raw)
                user = body.get('username', '')
                pwd = body.get('password', '')
            else:
                params = urllib.parse.parse_qs(body_raw.decode())
                user = params.get('username', [''])[0]
                pwd = params.get('password', [''])[0]

            if hashlib.sha256(f"{user}:{pwd}".encode()).hexdigest() == PASS_HASH:
                import uuid
                sid = uuid.uuid4().hex
                SESSIONS[sid] = datetime.now().timestamp()
                self.send_response(302)
                self.send_header('Location', '/')
                self.send_header('Set-Cookie', f'{SESSION_COOKIE}={sid}; Path=/; Max-Age=86400; HttpOnly')
                self.end_headers()
            else:
                self.send_response(302)
                self.send_header('Location', '/login?error=1')
                self.end_headers()
            return

        # API protection
        if not check_auth(self):
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Non authentifié"}).encode())
            return

        body = json.loads(body_raw)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        if self.path.startswith('/api/toggle'):
            today = date.today().isoformat()
            med_id = body["id"]
            meal = body["meal"]
            exists = c.execute("SELECT COUNT(*) FROM intakes WHERE med_id=? AND meal=? AND taken_date=?", (med_id, meal, today)).fetchone()[0]
            if exists:
                c.execute("DELETE FROM intakes WHERE med_id=? AND meal=? AND taken_date=?", (med_id, meal, today))
            else:
                c.execute("INSERT INTO intakes (med_id, meal, taken_date) VALUES (?,?,?)", (med_id, meal, today))
            conn.commit()
            self._json({"ok":True})

        elif self.path.startswith('/api/add'):
            c.execute("INSERT INTO meds (name, dosage, morning, midday, evening) VALUES (?,?,?,?,?)",
                (body["name"], body.get("dosage",""), body.get("morning",1), body.get("midday",1), body.get("evening",1)))
            conn.commit()
            self._json({"ok":True})

        elif self.path.startswith('/api/delete'):
            c.execute("UPDATE meds SET active=0 WHERE id=?", (body["id"],))
            conn.commit()
            self._json({"ok":True})

        elif self.path.startswith('/api/activate'):
            c.execute("UPDATE meds SET active=1 WHERE id=?", (body["id"],))
            conn.commit()
            self._json({"ok":True})

        elif self.path.startswith('/api/save'):
            today = date.today().isoformat()
            for intake in body.get("intakes", []):
                med_id = intake["id"]
                meal = intake["meal"]
                if intake.get("taken"):
                    exists = c.execute("SELECT COUNT(*) FROM intakes WHERE med_id=? AND meal=? AND taken_date=?", (med_id, meal, today)).fetchone()[0]
                    if not exists:
                        c.execute("INSERT INTO intakes (med_id, meal, taken_date) VALUES (?,?,?)", (med_id, meal, today))
                else:
                    c.execute("DELETE FROM intakes WHERE med_id=? AND meal=? AND taken_date=?", (med_id, meal, today))
            conn.commit()
            self._json({"ok":True})

        conn.close()

    def _logout(self):
        cookies = self.headers.get('Cookie', '')
        for c in cookies.split(';'):
            c = c.strip()
            if c.startswith(SESSION_COOKIE + '='):
                sid = c.split('=', 1)[1]
                SESSIONS.pop(sid, None)
        self.send_response(302)
        self.send_header('Location', '/login')
        self.send_header('Set-Cookie', f'{SESSION_COOKIE}=; Path=/; Max-Age=0')
        self.end_headers()

    def _json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args): pass

print(f"💊 Med Tracker: http://localhost:{PORT}")
HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()