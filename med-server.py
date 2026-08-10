#!/usr/bin/env python3
"""Médicaments Tracker — serveur web + API."""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, date, timedelta
import os
import sqlite3
import urllib.parse

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
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; padding: 20px; max-width: 500px; margin: 0 auto; }
h1 { text-align: center; color: #333; margin-bottom: 20px; font-size: 1.5em; }
.card { background: white; border-radius: 16px; padding: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); margin-bottom: 20px; }
h2 { font-size: 1em; color: #666; margin-bottom: 12px; }
.meal-section { margin-bottom: 20px; }
.meal-title { font-size: 1.1em; font-weight: 600; margin-bottom: 8px; padding: 8px 0; border-bottom: 2px solid #f0f0f0; }
.med-item { display: flex; align-items: center; padding: 10px 0; border-bottom: 1px solid #f0f0f0; }
.med-item:last-child { border-bottom: none; }
.med-item input[type="checkbox"] { width: 22px; height: 22px; margin-right: 12px; cursor: pointer; }
.med-item label { flex: 1; font-size: 1em; cursor: pointer; }
.med-item .dosage { color: #999; font-size: 0.85em; }
.med-item.taken label { text-decoration: line-through; color: #999; }
.add-form { display: flex; gap: 8px; margin-bottom: 10px; }
.add-form input { flex: 1; padding: 10px; border: 2px solid #e0e0e0; border-radius: 10px; font-size: 1em; }
.add-form button { padding: 10px 16px; background: #007aff; color: white; border: none; border-radius: 10px; cursor: pointer; }
.meal-checkboxes { display: flex; gap: 12px; margin: 8px 0; }
.meal-checkboxes label { font-size: 0.85em; color: #666; }
.med-list { list-style: none; }
.med-list li { display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid #f0f0f0; }
.med-list li .del { color: #ff3b30; cursor: pointer; padding: 4px 8px; }
.med-list li .info { font-size: 0.85em; color: #999; }
select { padding: 8px; border: 2px solid #e0e0e0; border-radius: 8px; font-size: 0.9em; }
#status { text-align: center; margin-top: 10px; padding: 10px; border-radius: 10px; display: none; }
.success { background: #d4edda; color: #155724; }
.error { background: #f8d7da; color: #721c24; }
.tabs { display: flex; gap: 0; margin-bottom: 20px; }
.tab { flex: 1; padding: 10px; text-align: center; cursor: pointer; border-bottom: 3px solid transparent; font-weight: 500; }
.tab.active { border-bottom-color: #007aff; color: #007aff; }
.tab-content { display: none; }
.tab-content.active { display: block; }
</style>
</head>
<body>
<h1>💊 Médicaments</h1>
<div class="tabs">
  <div class="tab active" data-tab="today" onclick="switchTab('today')">📋 Aujourd'hui</div>
  <div class="tab" data-tab="manage" onclick="switchTab('manage')">⚙️ Gérer</div>
  <div class="tab" data-tab="history" onclick="switchTab('history')">📅 Historique</div>
</div>

<div id="tab-today" class="tab-content active">
  <div class="card" id="today-content"></div>
</div>

<div id="tab-manage" class="tab-content">
  <div class="card">
    <h2>➕ Ajouter un médicament</h2>
    <div class="add-form">
      <input type="text" id="new-name" placeholder="Nom du médicament">
      <input type="text" id="new-dosage" placeholder="Dosage" style="max-width:100px">
      <button onclick="addMed()">Ajouter</button>
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
  const resp = await fetch('/api/today');
  const data = await resp.json();
  const meals = { morning: '🌅 Matin', midday: '🌞 Midi', evening: '🌙 Soir' };
  let html = '<h2>📅 ' + data.date + '</h2>';
  for (const [meal, label] of Object.entries(meals)) {
    if (!data[meal] || !data[meal].length) continue;
    html += '<div class="meal-section"><div class="meal-title">' + label + '</div>';
    for (const m of data[meal]) {
      html += '<div class="med-item' + (m.taken ? ' taken' : '') + '">';
      html += '<input type="checkbox" ' + (m.taken ? 'checked' : '') + ' onchange="toggleMed(' + m.id + ",'" + meal + "',this)" + '">';
      html += '<label>' + m.name + ' <span class="dosage">' + (m.dosage || '') + '</span></label>';
      html += '</div>';
    }
    html += '</div>';
  }
  if (!html.includes('med-item')) html += '<p style="color:#999;text-align:center">Aucun medicament pour aujourd hui</p>';
  document.getElementById('today-content').innerHTML = html;
}

async function toggleMed(id, meal, el) {
  await fetch('/api/toggle', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id, meal, taken:el.checked}) });
}

async function loadMeds() {
  const resp = await fetch('/api/meds');
  const data = await resp.json();
  const labels = { morning:'🌅', midday:'🌞', evening:'🌙' };
  let html = '';
  for (const m of data) {
    const meals = [m.morning && labels.morning, m.midday && labels.midday, m.evening && labels.evening].filter(Boolean).join(' ');
    html += '<li><div><strong>' + m.name + '</strong> <span class="info">' + (m.dosage||'') + ' ' + meals + '</span></div><span class="del" onclick="delMed(' + m.id + ')">✕</span></li>';
  }
  if (!html) html = '<li style="color:#999;text-align:center">Aucun médicament</li>';
  document.getElementById('med-list').innerHTML = html;
}

async function addMed() {
  const name = document.getElementById('new-name').value.trim();
  if (!name) return;
  const dosage = document.getElementById('new-dosage').value.trim();
  const morning = document.getElementById('m-morning').checked ? 1 : 0;
  const midday = document.getElementById('m-midday').checked ? 1 : 0;
  const evening = document.getElementById('m-evening').checked ? 1 : 0;
  await fetch('/api/add', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name, dosage, morning, midday, evening}) });
  document.getElementById('new-name').value = '';
  document.getElementById('new-dosage').value = '';
  loadMeds();
}

async function delMed(id) {
  if (!confirm('Supprimer ce médicament ?')) return;
  await fetch('/api/delete', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({id}) });
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

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/today':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            today = date.today().isoformat()
            meds = c.execute("SELECT id, name, dosage, morning, midday, evening FROM meds WHERE active=1").fetchall()
            taken = {r[0] for r in c.execute("SELECT med_id FROM intakes WHERE taken_date=?", (today,))}
            result = {"date": today, "morning": [], "midday": [], "evening": []}
            for m in meds:
                entry = {"id": m[0], "name": m[1], "dosage": m[2], "taken": m[0] in taken}
                if m[3]: result["morning"].append(entry)
                if m[4]: result["midday"].append(entry)
                if m[5]: result["evening"].append(entry)
            conn.close()
            self._json(result)
        elif self.path == '/api/history':
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
        elif self.path == '/api/meds':
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            meds = [{"id":r[0],"name":r[1],"dosage":r[2],"morning":r[3],"midday":r[4],"evening":r[5]} for r in c.execute("SELECT id,name,dosage,morning,midday,evening FROM meds WHERE active=1 ORDER BY name")]
            conn.close()
            self._json(meds)
        else:
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode())

    def do_POST(self):
        length = int(self.headers['Content-Length'])
        body = json.loads(self.rfile.read(length))
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        if self.path == '/api/toggle':
            today = date.today().isoformat()
            if body.get("taken"):
                c.execute("INSERT INTO intakes (med_id, meal, taken_date) VALUES (?,?,?)", (body["id"], body["meal"], today))
            else:
                c.execute("DELETE FROM intakes WHERE med_id=? AND meal=? AND taken_date=?", (body["id"], body["meal"], today))
            conn.commit()
            self._json({"ok":True})

        elif self.path == '/api/add':
            c.execute("INSERT INTO meds (name, dosage, morning, midday, evening) VALUES (?,?,?,?,?)",
                (body["name"], body.get("dosage",""), body.get("morning",1), body.get("midday",1), body.get("evening",1)))
            conn.commit()
            self._json({"ok":True})

        elif self.path == '/api/delete':
            c.execute("UPDATE meds SET active=0 WHERE id=?", (body["id"],))
            conn.commit()
            self._json({"ok":True})

        conn.close()

    def _json(self, data):
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, *args): pass

print(f"💊 Med Tracker: http://localhost:{PORT}")
HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()