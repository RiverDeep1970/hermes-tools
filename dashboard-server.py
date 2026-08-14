#!/usr/bin/env python3
"""Dashboard Hermes — version épurée et testée."""
import json, os, re, hashlib, uuid, sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from urllib.parse import unquote, urlparse
import subprocess

PORT = 8082
HERMES = os.path.expanduser("~/.hermes")
SESSIONS = {}
PASS_HASH = hashlib.sha256(b"alexis:medoc2026").hexdigest()

def auth(handler):
    for c in handler.headers.get('Cookie','').split(';'):
        c = c.strip()
        if c.startswith('dash_session='):
            s = SESSIONS.get(c.split('=',1)[1])
            if s and (datetime.now().timestamp() - s) < 86400:
                return True
    return False

def sys_data():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        boot = datetime.fromtimestamp(psutil.boot_time())
        up = (datetime.now() - boot).total_seconds()
        return {"cpu": cpu, "ram_pct": mem.percent, "ram_u": mem.used, "ram_t": mem.total,
                "disk_pct": disk.percent, "disk_u": disk.used, "disk_t": disk.total,
                "cores": psutil.cpu_count(), "uptime": int(up)}
    except:
        return {"cpu": 0, "ram_pct": 0, "ram_u": 0, "ram_t": 1, "disk_pct": 0, "disk_u": 0, "disk_t": 1, "cores": 0, "uptime": 0}

def usage_data():
    try:
        conn = sqlite3.connect(os.path.join(HERMES, "state.db"))
        cur = conn.cursor()
        cur.execute("SELECT model, billing_provider FROM sessions WHERE model IS NOT NULL AND model != '' ORDER BY started_at DESC LIMIT 1")
        row = cur.fetchone()
        model = row[0] if row else "?"
        prov = row[1] if row and row[1] else "?"
        now = datetime.now()
        d0 = datetime(now.year, now.month, now.day).timestamp()
        w0 = (now - timedelta(days=now.weekday())).replace(hour=0,minute=0,second=0).timestamp()
        m0 = datetime(now.year, now.month, 1).timestamp()
        cur.execute("SELECT started_at, input_tokens, output_tokens, estimated_cost_usd FROM sessions WHERE started_at IS NOT NULL")
        dt, dc, wt, wc, mt, mc = 0, 0, 0, 0, 0, 0
        for r in cur.fetchall():
            ts = r[0] or 0
            toks = (r[1] or 0) + (r[2] or 0)
            cst = r[3] or 0
            if ts >= d0: dt += toks; dc += cst
            if ts >= w0: wt += toks; wc += cst
            if ts >= m0: mt += toks; mc += cst
        conn.close()
        return {"model": model, "provider": prov, "d": {"t": dt, "c": dc}, "w": {"t": wt, "c": wc}, "m": {"t": mt, "c": mc}}
    except:
        return {"model": "?", "provider": "?", "d": {"t": 0, "c": 0}, "w": {"t": 0, "c": 0}, "m": {"t": 0, "c": 0}}

def hermes_data():
    svc = {}
    for s in ["mood-tracker","med-tracker","mood-tracker-tunnel","dashboard-tracker"]:
        try:
            r = subprocess.run(["systemctl","is-active",s], capture_output=True, text=True, timeout=3)
            svc[s] = r.stdout.strip()
        except: svc[s] = "unknown"
    jobs = []
    try:
        conn = sqlite3.connect(os.path.join(HERMES, "state.db"))
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM state_meta WHERE key LIKE 'cron:%'")
        for k, v in cur.fetchall():
            try:
                j = json.loads(v)
                jobs.append({"n": j.get("name", k.split(":")[-1]), "s": j.get("last_status", ""), "sc": j.get("schedule", "")})
            except: pass
        conn.close()
    except: pass
    return {"svc": svc, "jobs": jobs}

HTML = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>⚡ Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0f;color:#e0e0e0;padding:16px;max-width:500px;margin:0 auto}
h1{font-size:1.1em;margin-bottom:16px;display:flex;align-items:center;gap:8px}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block;background:#22c55e}
.s{color:#6c6c80;font-size:0.8em;margin:16px 0 8px;display:flex;align-items:center;gap:8px}
.s::after{content:'';flex:1;height:1px;background:#1e1e2e}
.g{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:8px}
.c{background:#13131a;border:1px solid #1e1e2e;border-radius:10px;padding:12px;text-align:center}
.c .n{font-size:1.3em;font-weight:700}
.c .l{font-size:0.7em;color:#6c6c80;margin-top:4px}
.c .p{height:3px;background:#1e1e2e;border-radius:2px;margin-top:6px;overflow:hidden}
.c .p .b{height:100%;border-radius:2px}
.c2{background:#13131a;border:1px solid #1e1e2e;border-radius:10px;padding:12px;margin-bottom:8px;font-size:0.85em}
table{width:100%;font-size:0.85em;border-collapse:collapse}
td{padding:6px 8px;border-bottom:1px solid #1e1e2e}
td:last-child{text-align:right}
.badge{display:inline-block;padding:1px 6px;border-radius:4px;font-size:0.75em}
.bg{background:rgba(34,197,94,0.15);color:#22c55e}
.br{background:rgba(239,68,68,0.15);color:#ef4444}
.by{background:rgba(234,179,8,0.15);color:#eab308}
@media(min-width:600px){body{max-width:900px}.g{grid-template-columns:repeat(4,1fr)}}
</style></head>
<body>
<h1><span class="dot" id="dot"></span> ⚡ Dashboard Hermes</h1>
<div id="app">Chargement...</div>
<script>
async function load(){
  const r=await fetch('/api/data?_='+Date.now());
  const d=await r.json();
  const s=d.sys, u=d.usage, h=d.hermes;

  document.getElementById('dot').style.background=s.cpu>80?'#ef4444':'#22c55e';

  let html='<div class="g">';
  html+=C(s.cpu+'%','CPU','c',s.cpu>80?'#ef4444':'#00d4ff');
  html+=C(fmt(s.ram_u)+'/'+fmt(s.ram_t),'RAM',s.ram_pct,'#00d4ff');
  html+=C(s.disk_pct+'%','Disque',s.disk_pct,'#eab308');
  html+=C(fmtUp(s.uptime),'Uptime','','#6c6c80');
  html+=C(s.cores+' cœurs','CPU','','#6c6c80');
  html+=C(fmtT(u.d.t),'Tokens jour','','#00d4ff');
  html+=C(fmt$(u.d.c),'Coût jour','','#00d4ff');
  html+=C(u.model,'Modèle','','#00d4ff');
  html+='</div>';

  html+='<div class="s">🔧 Services</div>';
  for(const[n,sv]of Object.entries(h.svc)){
    const cl=sv==='active'?'bg':'br';
    html+='<div class="c2" style="display:flex;justify-content:space-between">'+n+'<span class="badge '+cl+'">'+sv+'</span></div>';}

  if(h.jobs.length){
    html+='<div class="s">⏰ Jobs</div><div class="c2"><table>';
    for(const j of h.jobs.slice(0,20)){
      const cl=j.s==='ok'||!j.s?'bg':j.s==='error'?'br':'by';
      html+='<tr><td>'+j.n+'</td><td><span class="badge '+cl+'">'+(j.s||'ok')+'</span></td></tr>';}
    html+='</table></div>';}

  html+='<div class="s">📈 7j / 30j</div><div class="g">';
  html+=C(fmtT(u.w.t),'Tokens 7j','','#00d4ff');
  html+=C(fmt$(u.w.c),'Coût 7j','','#00d4ff');
  html+=C(fmtT(u.m.t),'Tokens 30j','','#00d4ff');
  html+=C(fmt$(u.m.c),'Coût 30j','','#00d4ff');
  html+='</div>';

  document.getElementById('app').innerHTML=html;
}
function C(n,l,p,cl){return'<div class="c"><div class="n" style="color:'+cl+'">'+n+'</div><div class="l">'+l+'</div>'+(p!==undefined&&p!==''?'<div class="p"><div class="b" style="width:'+p+'%;background:'+cl+'"></div></div>':'')+'</div>';}
function fmt(b){for(const u of['B','KB','MB','GB','TB']){if(b<1024)return b.toFixed(1)+' '+u;b/=1024}return b.toFixed(1)+' PB'}
function fmtUp(s){const d=Math.floor(s/86400),h=Math.floor((s%86400)/3600),m=Math.floor((s%3600)/60);return(d?d+'j ':'')+(h?h+'h ':'')+m+'m'}
function fmtT(n){if(n>=1000000)return(n/1000000).toFixed(1)+'M';if(n>=1000)return(n/1000).toFixed(1)+'k';return String(n)}
function fmt$(c){if(c<0.01)return'<0.01$';return c.toFixed(2)+'$'}
load();setInterval(load,30000);
</script></body></html>"""

LOGIN = """<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>⚡ Dashboard</title><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:#0a0a0f;color:#e0e0e0;height:100vh;display:flex;align-items:center;justify-content:center}.l{background:#13131a;border:1px solid #1e1e2e;border-radius:16px;padding:30px;width:300px}h1{text-align:center;margin-bottom:20px}input{width:100%;padding:12px;background:#1a1a24;border:1px solid #1e1e2e;border-radius:10px;color:#e0e0e0;margin-bottom:12px;font-size:1em}button{width:100%;padding:12px;background:linear-gradient(135deg,#00d4ff,#7c3aed);color:#fff;border:none;border-radius:10px;font-size:1em}</style></head><body><div class="l"><h1>⚡ Dashboard</h1><form method="POST" action="/login"><input type="text" name="u" placeholder="Utilisateur" required><input type="password" name="p" placeholder="Mot de passe" required><button>Se connecter</button></form></div></body></html>"""

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/login': self._html(LOGIN)
        elif self.path == '/logout': self._logout()
        elif not auth(self): self._redir('/login')
        elif self.path.startswith('/api/data'):
            self._json({"sys": sys_data(), "usage": usage_data(), "hermes": hermes_data()})
        else: self._html(HTML)
    def do_POST(self):
        if self.path == '/login':
            raw = self.rfile.read(int(self.headers['Content-Length'])).decode()
            p = {}
            for kv in raw.split('&'):
                if '=' in kv: k, v = kv.split('=', 1); p[k] = unquote(v)
            if hashlib.sha256(f"{p.get('u','')}:{p.get('p','')}".encode()).hexdigest() == PASS_HASH:
                sid = uuid.uuid4().hex
                SESSIONS[sid] = datetime.now().timestamp()
                self.send_response(302)
                self.send_header('Location', '/')
                self.send_header('Set-Cookie', f'dash_session={sid}; Path=/; Max-Age=86400')
                self.end_headers()
            else: self._redir('/login')
    def _html(self, h):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(h.encode())
    def _json(self, d):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(json.dumps(d).encode())
    def _redir(self, loc):
        self.send_response(302)
        self.send_header('Location', loc)
        self.end_headers()
    def _logout(self):
        for c in self.headers.get('Cookie','').split(';'):
            c = c.strip()
            if c.startswith('dash_session='):
                SESSIONS.pop(c.split('=',1)[1], None)
        self._redir('/login')
    def log_message(self, *a): pass

print(f"⚡ Dashboard: http://localhost:{PORT}")
HTTPServer(("0.0.0.0", PORT), H).serve_forever()