#!/usr/bin/env python3
"""Serveur web mood tracker — version améliorée."""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, date, timedelta
import os
import urllib.parse

ENTRIES_DIR = os.path.expanduser("~/.hermes/life-tracker/entries")
os.makedirs(ENTRIES_DIR, exist_ok=True)

HTML = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>📓 Mood</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f7;padding:0;max-width:100%;min-height:100dvh}
/* Header */
.hdr{background:#fff;padding:14px 20px;box-shadow:0 1px 4px rgba(0,0,0,0.06);position:sticky;top:0;z-index:100}
.hdr h1{font-size:1.2em;color:#333;text-align:center}
/* Contenu */
.c{padding:14px 16px;max-width:500px;margin:0 auto}
.card{background:#fff;border-radius:16px;padding:20px;box-shadow:0 1px 8px rgba(0,0,0,0.05);margin-bottom:16px}
h2{font-size:.9em;color:#888;margin-bottom:12px;text-transform:uppercase;letter-spacing:.5px}
/* Mood: 4x2 avec touches larges */
.moods{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:8px}
.mb{padding:12px 4px;border:2px solid #e8e8ed;border-radius:14px;background:#fafafa;cursor:pointer;text-align:center;transition:all .2s}
.mb .e{font-size:1.6em;display:block;line-height:1.2}
.mb .l{font-size:.7em;color:#888;display:block;margin-top:2px}
.mb:active{transform:scale(.95)}
.mb.sel{border-color:#007aff;background:#e8f0ff}
.mb.sel .l{color:#007aff;font-weight:600}
.mb.used{border-color:#34c759;background:#e8ffe8}
/* Champs */
.field{width:100%;padding:12px 14px;border:2px solid #e8e8ed;border-radius:12px;font-size:1em;margin-bottom:8px;background:#fafafa;transition:border .2s}
.field:focus{border-color:#007aff;outline:none;background:#fff}
textarea.field{resize:vertical;min-height:50px;font-family:inherit}
/* Quick activités */
.quick{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}
.qb{padding:6px 14px;border:2px solid #e8e8ed;border-radius:20px;background:#fafafa;font-size:.85em;cursor:pointer;transition:all .2s}
.qb:active{transform:scale(.95)}
.qb.sel{border-color:#34c759;background:#e8ffe8;color:#155724;font-weight:500}
/* Bouton */
.sb{width:100%;padding:14px;background:#007aff;color:#fff;border:none;border-radius:12px;font-size:1.1em;font-weight:600;cursor:pointer;transition:opacity .2s}
.sb:active{opacity:.8}
.sb:disabled{opacity:.4}
#st{text-align:center;padding:10px;border-radius:10px;display:none;font-size:.85em;margin-top:10px}
.succ{background:#d4edda;color:#155724;display:block!important}
.err{background:#f8d7da;color:#721c24;display:block!important}
/* Historique visuel */
.hw{display:flex;gap:6px;justify-content:center;padding:8px 0}
.hd{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0}
.hl{font-size:9px;color:#999;margin-top:2px;text-align:center}
.hc{display:flex;flex-direction:column;align-items:center}
/* Détail jour */
.hp{padding:8px 0;border-bottom:1px solid #f0f0f0;display:flex;gap:10px;align-items:flex-start}
.hp:last-child{border:none}
.hp .d{font-size:.8em;color:#999;min-width:36px}
.hp .t{font-size:.9em;color:#333;flex:1}
.hp .t .s{color:#888;font-size:.8em}
@media(max-width:380px){.moods{grid-template-columns:repeat(4,1fr);gap:6px}.mb{padding:10px 2px}.mb .e{font-size:1.3em}}
</style>
</head>
<body>
<div class="hdr"><h1>📓 Bilan du jour</h1></div>
<div class="c">
<div class="card">
  <h2>😊 Humeur</h2>
  <div class="moods" id="moods"></div>
</div>
<div class="card" id="entry-card">
  <h2>📝 Détails</h2>
  <input class="field" id="lecture" placeholder="📚 Lecture (ex: Dune p.45)">
  <input class="field" id="serie" placeholder="📺 Série (ex: Silo S3E4)">
  <div class="quick" id="quick-act"></div>
  <textarea class="field" id="notes" placeholder="Notes libres..."></textarea>
  <button class="sb" id="sb" onclick="save()">✅ Enregistrer</button>
  <div id="st"></div>
</div>
<div class="card">
  <h2>📅 7 derniers jours</h2>
  <div id="trend"></div>
  <div id="hist"></div>
</div>
</div>
<script>
const ML=[
  {v:"1",e:"😞",l:"Mal"},{v:"2",e:"😐",l:"Bof"},{v:"3",e:"🙂",l:"Bien"},{v:"4",e:"😄",l:"Super"},
  {v:"5",e:"😴",l:"Fatigué"},{v:"6",e:"🤒",l:"Malade"},{v:"7",e:"😰",l:"Stressé"},{v:"8",e:"🚀",l:"Motivé"}
];
const ACT=["📖 Lecture","📺 Série","🏃 Sport","🎵 Musique","🍳 Cuisine","🌿 Promenade"];
const EM={1:"😞",2:"😐",3:"🙂",4:"😄",5:"😴",6:"🤒",7:"😰",8:"🚀"};
let sel=null, sact=[];

// Rendu moods
(function(){
  let h='';
  for(const m of ML) h+='<div class="mb" data-v="'+m.v+'" onclick="pick(this)"><span class="e">'+m.e+'</span><span class="l">'+m.l+'</span></div>';
  document.getElementById('moods').innerHTML=h;
})();

// Quick activités
(function(){
  let h='';
  for(const a of ACT) h+='<div class="qb" onclick="togAct(this)">'+a+'</div>';
  document.getElementById('quick-act').innerHTML=h;
})();

function pick(el){
  document.querySelectorAll('.mb').forEach(b=>b.classList.remove('sel'));
  el.classList.add('sel'); sel=el.dataset.v;
}
function togAct(el){
  el.classList.toggle('sel');
  const t=el.textContent.trim();
  sact=sact.includes(t)?sact.filter(x=>x!==t):[...sact,t];
}

async function save(){
  if(!sel){document.getElementById('st').className='err';document.getElementById('st').textContent='Choisis une humeur !';return}
  document.getElementById('sb').disabled=true;
  const d={mood:sel,lecture:document.getElementById('lecture').value.trim(),serie:document.getElementById('serie').value.trim(),activite:sact.join(', '),notes:document.getElementById('notes').value.trim()};
  try{
    const r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
    const j=await r.json();
    if(j.ok){document.getElementById('st').className='succ';document.getElementById('st').textContent='✅ Enregistré !';loadAll()}
    else throw Error();
  }catch(e){document.getElementById('st').className='err';document.getElementById('st').textContent='❌ Erreur'}
  setTimeout(()=>document.getElementById('st').className='st',3000);
  document.getElementById('sb').disabled=false;
}

async function loadAll(){
  const r=await fetch('/data');
  const d=await r.json();
  
  // Trend (7 dots)
  let h='<div class="hw">';
  for(const day of d.trend){
    const cl=day.m?EM[day.m]||'—':'—';
    const bg=day.m?{1:'#ff6b6b',2:'#ffa94d',3:'#74b816',4:'#2b8a3e',5:'#748ffc',6:'#da77f2',7:'#f06595',8:'#ffd43b'}[day.m]||'#ccc':'#e8e8ed';
    h+='<div class="hc"><div class="hd" style="background:'+bg+'">'+cl+'</div><div class="hl">'+day.d.slice(5)+'</div></div>';
  }
  h+='</div>';
  document.getElementById('trend').innerHTML=h;
  
  // Détail des entrées
  let h2='';
  for(const e of d.entries){
    const ei=EM[e.m]||'—';
    h2+='<div class="hp"><div class="d">'+e.date.slice(5)+'</div><div class="t">'+ei+' '+e.text+(e.note?'<br><span class="s">'+e.note+'</span>':'')+'</div></div>';
  }
  document.getElementById('hist').innerHTML=h2||'<div style="color:#999;text-align:center;padding:10px">Aucune entrée</div>';
  
  // Highlight today's mood if exists
  if(d.today){
    sel=d.today.m;
    document.querySelectorAll('.mb').forEach(b=>{if(b.dataset.v===d.today.m)b.classList.add('sel')});
  }
}
loadAll();
</script>
</body></html>"""

MOOD_LABELS = {"1":"Mal","2":"Bof","3":"Bien","4":"Super","5":"Fatigué","6":"Malade","7":"Stressé","8":"Motivé"}
EMOJI = {"1":"😞","2":"😐","3":"🙂","4":"😄","5":"😴","6":"🤒","7":"😰","8":"🚀"}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/data':
            entries = []
            trend = []
            today = date.today()
            today_data = None
            for i in range(6, -1, -1):
                d = today - timedelta(days=i)
                fname = d.isoformat() + ".json"
                fpath = os.path.join(ENTRIES_DIR, fname)
                day_info = {"d": d.isoformat(), "m": None}
                if os.path.exists(fpath):
                    with open(fpath) as f:
                        try:
                            e = json.load(f)
                            m = e.get("mood", "")
                            day_info["m"] = int(m) if m else None
                            # Build entry text
                            parts = []
                            if e.get("lecture"): parts.append("📚 " + e["lecture"])
                            if e.get("serie"): parts.append("📺 " + e["serie"])
                            if e.get("activite"): parts.append("🏃 " + e["activite"])
                            text = " — ".join(parts) if parts else ""
                            entries.append({
                                "date": d.isoformat(),
                                "m": int(m) if m else 0,
                                "text": text,
                                "note": e.get("note", "")
                            })
                            if d == today:
                                today_data = {"m": int(m) if m else 0, "lecture": e.get("lecture",""), "serie": e.get("serie",""), "activite": e.get("activite",""), "notes": e.get("note","")}
                        except: pass
                trend.append(day_info)
            self._json({"entries": entries[:7], "trend": trend, "today": today_data})
        else:
            self._html(HTML)

    def do_POST(self):
        if self.path == '/save':
            length = int(self.headers['Content-Length'])
            body = json.loads(self.rfile.read(length))
            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d")
            fpath = os.path.join(ENTRIES_DIR, f"{date_str}.json")

            entry = {"date": date_str, "mood": body.get("mood",""), "mood_label": MOOD_LABELS.get(body.get("mood",""),"")}
            if body.get("lecture"): entry["lecture"] = body["lecture"]
            if body.get("serie"): entry["serie"] = body["serie"]
            if body.get("activite"): entry["activite"] = body["activite"]
            notes = body.get("notes","") or ""

            if os.path.exists(fpath):
                with open(fpath) as f:
                    existing = json.load(f)
                    if not body.get("lecture") and existing.get("lecture"): entry["lecture"] = existing["lecture"]
                    if not body.get("serie") and existing.get("serie"): entry["serie"] = existing["serie"]
                    if not body.get("activite") and existing.get("activite"): entry["activite"] = existing["activite"]
                    if existing.get("note"): notes = existing["note"] + ("; " + notes if notes else "")
            entry["note"] = notes

            with open(fpath, "w") as f:
                json.dump(entry, f)

            self._json({"ok": True})

    def _json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _html(self, h):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(h.encode())

    def log_message(self, *a): pass

PORT = 8080
print(f"🌐 Mood Tracker: http://localhost:{PORT}")
HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()