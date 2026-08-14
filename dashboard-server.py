#!/usr/bin/env python3
"""Dashboard Hermes — version améliorée PC."""
import json, os, re, hashlib, uuid, sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from urllib.parse import unquote
import subprocess

PORT = 8082
HERMES = os.path.expanduser("~/.hermes")
SESSIONS = {}
PASS_HASH = hashlib.sha256(b"alexis:medoc2026").hexdigest()

def auth(h):
    for c in h.headers.get('Cookie','').split(';'):
        c = c.strip()
        if c.startswith('dash_session='):
            s = SESSIONS.get(c.split('=',1)[1])
            if s and (datetime.now().timestamp() - s) < 86400: return True
    return False

def get_top_proc():
    try:
        r = subprocess.run(["ps","aux","--sort=-%cpu","--no-headers"], capture_output=True, text=True, timeout=3)
        lines = r.stdout.strip().split("\n")
        return [{"cpu": l.split()[2], "mem": l.split()[3], "name": l.split()[10][:20], "user": l.split()[0]}
                for l in lines[:8] if len(l.split()) > 10]
    except: return []

def sys_data():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        boot = datetime.fromtimestamp(psutil.boot_time())
        up = int((datetime.now() - boot).total_seconds())
        net = psutil.net_io_counters()
        procs = get_top_proc()
        load = psutil.getloadavg()
        return {
            "cpu": cpu, "ram_pct": mem.percent, "ram_u": mem.used, "ram_t": mem.total,
            "disk_pct": disk.percent, "disk_u": disk.used, "disk_t": disk.total, "disk_f": disk.free,
            "cores": psutil.cpu_count(), "uptime": up,
            "load": [round(l,2) for l in load],
            "net_s": net.bytes_sent, "net_r": net.bytes_recv,
            "conns": len(psutil.net_connections()),
            "procs_total": len(psutil.pids()),
            "host": os.uname().nodename,
            "procs": procs
        }
    except: return {"cpu":0,"ram_pct":0,"ram_u":0,"ram_t":1,"disk_pct":0,"disk_u":0,"disk_t":1,"cores":0,"uptime":0,"load":[0,0,0],"net_s":0,"net_r":0,"conns":0,"procs_total":0,"host":"?","procs":[]}

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
        # Sessions and messages today
        cur.execute("SELECT COUNT(*) FROM sessions WHERE started_at >= ?", (d0,))
        sess_today = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM messages WHERE timestamp >= ?", (d0,))
        msgs_today = cur.fetchone()[0]
        conn.close()
        return {"model":model,"provider":prov,"d":{"t":dt,"c":dc},"w":{"t":wt,"c":wc},"m":{"t":mt,"c":mc},"sess":sess_today,"msgs":msgs_today}
    except: return {"model":"?","provider":"?","d":{"t":0,"c":0},"w":{"t":0,"c":0},"m":{"t":0,"c":0},"sess":0,"msgs":0}

def hermes_data():
    svc = {}
    for s in ["mood-tracker","med-tracker","mood-tracker-tunnel","dashboard-tracker","hermes-gateway"]:
        try:
            r = subprocess.run(["systemctl","is-active",s], capture_output=True, text=True, timeout=3)
            svc[s] = r.stdout.strip()
        except: svc[s] = "unknown"
    jobs = []
    try:
        with open(os.path.join(HERMES, "cron", "jobs.json")) as f:
            data = json.load(f)
        items = data.get("jobs", []) if isinstance(data, dict) else data
        for j in items:
            sched = j.get("schedule", {})
            sched_disp = sched.get("display", "") if isinstance(sched, dict) else str(sched)
            jobs.append({"n": j.get("name", "?"), "s": j.get("last_status", ""), "sc": sched_disp})
        jobs.sort(key=lambda x: (0 if x["s"]=="error" else 1, x["n"]))
    except: pass
    return {"svc": svc, "jobs": jobs}

# ── HTML ─────────────────────────────────────────────────────
HTML = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>⚡ Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;--c1:#0a0a0f;--c2:#13131a;--c3:#1e1e2e;--t:#e0e0e0;--m:#6c6c80;--a:#00d4ff;--g:#22c55e;--y:#eab308;--r:#ef4444;--p:#7c3aed}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--c1);color:var(--t);min-height:100vh}
/* Header */
.hdr{background:var(--c2);border-bottom:1px solid var(--c3);padding:14px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100}
.hdr h1{font-size:1.1em;display:flex;align-items:center;gap:8px}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.logout{color:var(--m);text-decoration:none;font-size:.8em;padding:4px 10px;border:1px solid var(--c3);border-radius:6px}
/* Grid PC: 2 colonnes */
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.col{min-width:0}
/* Cartes */
.c{background:var(--c2);border:1px solid var(--c3);border-radius:10px;padding:14px;margin-bottom:10px}
.ct{font-size:.75em;color:var(--m);margin-bottom:10px;display:flex;align-items:center;gap:6px}
.ct::after{content:'';flex:1;height:1px;background:var(--c3)}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:6px}
.mcard{background:var(--c2);border:1px solid var(--c3);border-radius:8px;padding:10px;text-align:center}
.mcard .n{font-size:1.2em;font-weight:700}
.mcard .l{font-size:.65em;color:var(--m);margin-top:3px}
.mcard .bar{height:3px;background:var(--c3);border-radius:2px;margin-top:5px;overflow:hidden}
.mcard .bar .f{height:100%;border-radius:2px}
/* Table */
table{width:100%;border-collapse:collapse;font-size:.82em}
td{padding:5px 8px;border-bottom:1px solid var(--c3)}
td:last-child{text-align:right}
td:first-child{padding-left:0}
/* Badges */
.b{display:inline-block;padding:1px 6px;border-radius:4px;font-size:.7em;font-weight:600}
.bg{background:rgba(34,197,94,.12);color:var(--g)}
.br{background:rgba(239,68,68,.12);color:var(--r)}
.by{background:rgba(234,179,8,.12);color:var(--y)}
.b0{background:rgba(108,108,128,.12);color:var(--m)}
/* Progress bar simple */
.pbar{height:4px;background:var(--c3);border-radius:2px;margin-top:6px;overflow:hidden}
.pbar .pf{height:100%;border-radius:2px}
/* Services */
.svc{display:flex;justify-content:space-between;align-items:center;padding:6px 0}
/* Process */
.proc{display:grid;grid-template-columns:1fr 60px 60px;padding:4px 0;font-size:.8em;border-bottom:1px solid var(--c3);gap:4px}
.proc:last-child{border-bottom:none}
/* Responsive */
@media(max-width:700px){.grid2{grid-template-columns:1fr}.hdr{padding:10px 14px}}
</style></head>
<body>
<div class="hdr"><h1><span class="dot" id="dot"></span> ⚡ Dashboard</h1><a class="logout" href="/logout">Déconnexion</a></div>
<div id="app" style="padding:16px 20px;max-width:1400px;margin:0 auto">Chargement...</div>
<script>
async function load(){
  const r=await fetch('/api/data?_='+Date.now());
  const d=await r.json();
  const s=d.sys,u=d.usage,h=d.hermes;
  document.getElementById('dot').style.background=s.cpu>80?'var(--r)':s.cpu>50?'var(--y)':'var(--g)';

  // Layout 2 colonnes
  let L='<div class="grid2"><div class="col">',R='<div class="col">';
  let left=[],right=[];

  // === COLONNE GAUCHE ===
  // Stats rapides
  L+='<div class="c"><div class="ct">📊 Système</div><div class="cards">';
  L+=mc(s.cpu+'%','CPU',s.cpu,s.cpu>80?3:s.cpu>50?2:1);
  L+=mc(fmt(s.ram_u)+'/'+fmt(s.ram_t),'RAM',s.ram_pct,1);
  L+=mc(s.disk_pct+'%','Disque',s.disk_pct,2);
  L+=mc(s.procs_total+'','Processus');
  L+=mc(s.cores+' cœurs','CPU');
  L+=mc(s.conns+'','Connexions');
  L+=mc(fmtUp(s.uptime),'Uptime');
  L+=mc(s.load[0].toFixed(1),'Load 1m');
  L+='</div></div>';

  // Processus top CPU
  if(s.procs&&s.procs.length){
    L+='<div class="c"><div class="ct">⚡ Top CPU</div>';
    for(const p of s.procs.slice(0,5)){
      L+='<div class="proc"><span>'+p.name+'</span><span>'+p.cpu+'%</span><span>'+p.mem+'%</span></div>';}
    L+='</div>';}

  // Jobs cron
  R+='<div class="c"><div class="ct">⏰ Jobs Cron ('+h.jobs.length+')</div><table>';
  const errs=h.jobs.filter(j=>j.s==='error').length;
  if(errs)R+='<tr><td colspan="2" style="color:var(--r);font-size:.75em">🔴 '+errs+' en erreur</td></tr>';
  for(const j of h.jobs.slice(0,25)){
    const cl=j.s==='ok'||!j.s?'bg':j.s==='error'?'br':'by';
    const lb=j.s||'ok';
    R+='<tr><td>'+j.n+'</td><td><span class="b '+cl+'">'+lb+'</span></td></tr>';}
  R+='</table></div>';

  // === COLONNE DROITE ===
  // Services
  R+='<div class="c"><div class="ct">🔧 Services</div>';
  for(const[n,sv]of Object.entries(h.svc)){
    const cl=sv==='active'?'bg':sv==='inactive'?'by':'br';
    const lb=sv==='active'?'✅ Actif':sv==='inactive'?'⏸️':'❌ '+sv;
    R+='<div class="svc"><span>'+n+'</span><span class="b '+cl+'">'+lb+'</span></div>';}
  R+='</div>';

  // LLM Usage
  R+='<div class="c"><div class="ct">🧠 LLM — '+u.model+'</div><div class="cards">';
  R+=mc(fmtT(u.d.t),'Tokens jour','',1);
  R+=mc(fmt$(u.d.c),'Coût jour','',1);
  R+=mc(fmtT(u.w.t),'Tokens 7j','',1);
  R+=mc(fmt$(u.w.c),'Coût 7j','',1);
  R+=mc(fmtT(u.m.t),'Tokens 30j','',1);
  R+=mc(fmt$(u.m.c),'Coût 30j','',1);
  R+='</div></div>';

  // Sessions & messages aujourd'hui
  R+='<div class="c"><div class="ct">📈 Activité Hermes</div><div class="cards">';
  R+=mc(u.sess+'','Sessions ajd','',1);
  R+=mc(u.msgs+'','Messages ajd','',1);
  R+='</div></div>';

  // Host info
  R+='<div class="c"><div class="ct">🖥️ Serveur</div><table>';
  R+='<tr><td>Hostname</td><td>'+s.host+'</td></tr>';
  R+='<tr><td>Disque libre</td><td>'+fmt(s.disk_f)+'</td></tr>';
  R+='<tr><td>Réseau envoyé</td><td>'+fmt(s.net_s)+'</td></tr>';
  R+='<tr><td>Réseau reçu</td><td>'+fmt(s.net_r)+'</td></tr>';
  R+='</table></div>';

  document.getElementById('app').innerHTML=L+'</div>'+R+'</div></div>';
}

function mc(n,l,p,t){let bar='';if(p!==undefined&&p!==''){const cl=t===3?'var(--r)':t===2?'var(--y)':'var(--a)';bar='<div class="bar"><div class="f" style="width:'+p+'%;background:'+cl+'"></div></div>'}return'<div class="mcard"><div class="n">'+n+'</div><div class="l">'+l+'</div>'+bar+'</div>'}
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