#!/usr/bin/env python3
"""Serveur web mood tracker — accessible via SSH forward."""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
import os
import urllib.parse

ENTRIES_DIR = os.path.expanduser("~/.hermes/life-tracker/entries")
os.makedirs(ENTRIES_DIR, exist_ok=True)

HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📓 Mood Tracker</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5; padding: 20px; max-width: 500px; margin: 0 auto; }
h1 { text-align: center; color: #333; margin-bottom: 20px; font-size: 1.5em; }
.card { background: white; border-radius: 16px; padding: 20px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); margin-bottom: 20px; }
h2 { font-size: 1em; color: #666; margin-bottom: 12px; }
.moods { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
.mood-btn { padding: 14px; border: 2px solid #e0e0e0; border-radius: 12px; background: white; font-size: 1em; cursor: pointer; transition: all 0.2s; text-align: center; }
.mood-btn:hover { border-color: #007aff; background: #f0f7ff; }
.mood-btn.selected { border-color: #007aff; background: #007aff; color: white; }
.mood-btn .emoji { font-size: 1.5em; display: block; margin-bottom: 4px; }
.mood-btn .label { font-size: 0.85em; }
input, textarea { width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 10px; font-size: 1em; margin-bottom: 10px; }
textarea { resize: vertical; min-height: 60px; }
.submit-btn { width: 100%; padding: 14px; background: #007aff; color: white; border: none; border-radius: 12px; font-size: 1.1em; cursor: pointer; }
.submit-btn:hover { background: #0056b3; }
#status { text-align: center; margin-top: 10px; padding: 10px; border-radius: 10px; display: none; }
.success { background: #d4edda; color: #155724; }
.error { background: #f8d7da; color: #721c24; }
.history { margin-top: 10px; }
.history-item { padding: 8px 0; border-bottom: 1px solid #eee; font-size: 0.9em; color: #555; }
.history-item .hdate { color: #999; font-size: 0.8em; }
</style>
</head>
<body>
<h1>📓 Bilan du jour</h1>
<div class="card">
  <h2>😊 Humeur</h2>
  <div class="moods" id="moods">
    <div class="mood-btn" data-value="1" onclick="selectMood(this)"><span class="emoji">😞</span><span class="label">Mal</span></div>
    <div class="mood-btn" data-value="2" onclick="selectMood(this)"><span class="emoji">😐</span><span class="label">Bof</span></div>
    <div class="mood-btn" data-value="3" onclick="selectMood(this)"><span class="emoji">🙂</span><span class="label">Bien</span></div>
    <div class="mood-btn" data-value="4" onclick="selectMood(this)"><span class="emoji">😄</span><span class="label">Super</span></div>
    <div class="mood-btn" data-value="5" onclick="selectMood(this)"><span class="emoji">😴</span><span class="label">Fatigué</span></div>
    <div class="mood-btn" data-value="6" onclick="selectMood(this)"><span class="emoji">🤒</span><span class="label">Malade</span></div>
    <div class="mood-btn" data-value="7" onclick="selectMood(this)"><span class="emoji">😰</span><span class="label">Stressé</span></div>
    <div class="mood-btn" data-value="8" onclick="selectMood(this)"><span class="emoji">🚀</span><span class="label">Motivé</span></div>
  </div>
</div>
<div class="card">
  <h2>📝 Détails (optionnel)</h2>
  <input type="text" id="lecture" placeholder="📚 Lecture (ex: Dune p.45)">
  <input type="text" id="serie" placeholder="📺 Série (ex: Silo S3E4)">
  <input type="text" id="activite" placeholder="🏃 Activité (ex: Vélo 30min)">
  <textarea id="notes" placeholder="📝 Notes libres..."></textarea>
  <button class="submit-btn" onclick="submitMood()">✅ Envoyer</button>
  <div id="status"></div>
</div>
<div class="card">
  <h2>📅 Derniers jours</h2>
  <div class="history" id="history"></div>
</div>
<script>
let selectedMood = null;
function selectMood(el) {
  document.querySelectorAll('.mood-btn').forEach(b => b.classList.remove('selected'));
  el.classList.add('selected');
  selectedMood = el.dataset.value;
}
async function submitMood() {
  if (!selectedMood) { showStatus('Sélectionne une humeur !', 'error'); return; }
  const data = { mood: selectedMood, lecture: document.getElementById('lecture').value, serie: document.getElementById('serie').value, activite: document.getElementById('activite').value, notes: document.getElementById('notes').value };
  const resp = await fetch('/save', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
  const result = await resp.json();
  if (result.ok) { showStatus('✅ Enregistré !', 'success'); loadHistory(); }
  else { showStatus('❌ Erreur', 'error'); }
}
function showStatus(msg, type) {
  const s = document.getElementById('status'); s.textContent = msg; s.className = type; s.style.display = 'block';
  setTimeout(() => s.style.display = 'none', 3000);
}
async function loadHistory() {
  const resp = await fetch('/history');
  const data = await resp.json();
  const h = document.getElementById('history');
  h.innerHTML = data.entries.map(e => '<div class="history-item"><span class="hdate">' + e.date + '</span> — ' + e.mood + (e.note ? ' — ' + e.note : '') + '</div>').join('');
}
loadHistory();
</script>
</body>
</html>"""

MOOD_LABELS = {"1":"Mal","2":"Bof","3":"Bien","4":"Super","5":"Fatigué","6":"Malade","7":"Stressé","8":"Motivé"}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/history':
            entries = []
            for fname in sorted(os.listdir(ENTRIES_DIR), reverse=True)[:7]:
                if not fname.endswith('.json'): continue
                with open(os.path.join(ENTRIES_DIR, fname)) as f:
                    try:
                        e = json.load(f)
                        entries.append({"date": e.get("date",""), "mood": MOOD_LABELS.get(e.get("mood",""),""), "note": e.get("note","") or e.get("lecture","") or e.get("serie","")})
                    except: pass
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"entries": entries}).encode())
        else:
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML.encode())

    def do_POST(self):
        if self.path == '/save':
            length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(length))
            now = datetime.now()
            date = now.strftime("%Y-%m-%d")
            fpath = os.path.join(ENTRIES_DIR, f"{date}.json")

            entry = {"date": date, "mood": body.get("mood",""), "mood_label": MOOD_LABELS.get(body.get("mood",""),"")}
            if body.get("lecture"): entry["lecture"] = body["lecture"]
            if body.get("serie"): entry["serie"] = body["serie"]
            if body.get("activite"): entry["activite"] = body["activite"]
            notes = body.get("notes","") or ""

            # Merge with existing (preserve old fields not sent by form)
            if os.path.exists(fpath):
                with open(fpath) as f:
                    existing = json.load(f)
                    # Preserve existing fields if form didn't send them
                    if not body.get("lecture") and existing.get("lecture"):
                        entry["lecture"] = existing["lecture"]
                    if not body.get("serie") and existing.get("serie"):
                        entry["serie"] = existing["serie"]
                    if not body.get("activite") and existing.get("activite"):
                        entry["activite"] = existing["activite"]
                    if existing.get("note"): notes = existing["note"] + ("; " + notes if notes else "")
            entry["note"] = notes

            with open(fpath, "w") as f:
                json.dump(entry, f)

            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode())

    def log_message(self, format, *args):
        pass  # Silence logs

PORT = 8080
print(f"🌐 Mood Tracker: http://localhost:{PORT}")
print(f"🔌 SSH: ssh -L {PORT}:localhost:{PORT} ubuntu@<IP_VM>")
print("   Puis ouvrir http://localhost:8080 dans ton navigateur")
HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()