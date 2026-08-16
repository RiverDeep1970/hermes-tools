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

def token_history():
    """Daily token usage for last 7 days for sparklines."""
    try:
        conn = sqlite3.connect(os.path.join(HERMES, "state.db"))
        cur = conn.cursor()
        now = datetime.now()
        days = []
        for i in range(6, -1, -1):
            d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
            start = datetime.strptime(d, "%Y-%m-%d").timestamp()
            end = start + 86400
            cur.execute("SELECT COALESCE(SUM(input_tokens+output_tokens),0), COALESCE(SUM(estimated_cost_usd),0) FROM sessions WHERE started_at >= ? AND started_at < ?", (start, end))
            tok, cost = cur.fetchone()
            days.append({"d": d, "t": tok or 0, "c": cost or 0})
        conn.close()
        return days
    except:
        return [{"d":"-","t":0,"c":0} for _ in range(7)]

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
*{margin:0;padding:0;box-sizing:border-box;--c1:#0a0a0f;--c2:#13131a;--c3:#1e1e2e;--c4:#1a1a2e;--t:#e0e0e0;--m:#6c6c80;--a:#00d4ff;--g:#22c55e;--y:#eab308;--r:#ef4444;--p:#7c3aed}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:var(--c1);color:var(--t)}
.hdr{background:var(--c2);border-bottom:1px solid var(--c3);padding:14px 24px;display:flex;align-items:center;justify-content:space-between;position:sticky;top:0;z-index:100;backdrop-filter:blur(10px)}
.hdr h1{font-size:1.1em;display:flex;align-items:center;gap:8px}
.dot{width:8px;height:8px;border-radius:50%;display:inline-block}
.logout{color:var(--m);text-decoration:none;font-size:.8em;padding:4px 10px;border:1px solid var(--c3);border-radius:6px}
.app{padding:16px 20px;max-width:1500px;margin:0 auto}
/* Health matrix */
.health{display:flex;gap:8px;margin-bottom:14px;flex-wrap:wrap}
.hitem{display:flex;align-items:center;gap:6px;background:var(--c2);border:1px solid var(--c3);border-radius:8px;padding:8px 12px;font-size:.8em}
.hdot{width:6px;height:6px;border-radius:50%}
/* Grid */
.g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
.g2{display:grid;grid-template-columns:1fr 1fr;gap:12px}
/* Cards */
.c{background:var(--c2);border:1px solid var(--c3);border-radius:10px;padding:14px;margin-bottom:10px}
.ct{font-size:.75em;color:var(--m);margin-bottom:10px;display:flex;align-items:center;gap:6px;text-transform:uppercase;letter-spacing:.5px}
.ct::after{content:'';flex:1;height:1px;background:var(--c3)}
.row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
.metric{flex:1;min-width:100px}
.metric .v{font-size:1.6em;font-weight:700}
.metric .l{font-size:.7em;color:var(--m);margin-top:2px}
.metric .sub{font-size:.75em;color:var(--m);margin-top:4px}
svg{display:block}
/* Tables */
table{width:100%;border-collapse:collapse;font-size:.82em}
td{padding:5px 8px;border-bottom:1px solid var(--c3)}
td:last-child{text-align:right}
/* Badges */
.b{display:inline-block;padding:1px 8px;border-radius:4px;font-size:.7em;font-weight:600}
.bg{background:rgba(34,197,94,.12);color:var(--g)}
.br{background:rgba(239,68,68,.12);color:var(--r)}
.by{background:rgba(234,179,8,.12);color:var(--y)}
.b0{background:rgba(108,108,128,.12);color:var(--m)}
/* Jobs */
.jr{display:flex;justify-content:space-between;padding:5px 0;border-bottom:1px solid var(--c3);font-size:.82em}
.jr:last-child{border-bottom:none}
/* Sparkline tooltip */
.spark-wrap{position:relative;display:inline-block}
/* Responsive */
@media(max-width:900px){.g3{grid-template-columns:1fr}.g2{grid-template-columns:1fr}}
</style></head>
<body>
<div class="hdr"><h1><span class="dot" id="dot"></span> ⚡ Dashboard</h1><a class="logout" href="/logout">Déconnexion</a></div>
<div class="app" id="app">Chargement...</div>
<script>
function spark(vals, w=120, h=30, color='#00d4ff', max){
  if(!vals||!vals.length)return'';
  const m=max||Math.max(...vals,1);
  const pts=vals.map((v,i)=>`${(i/(vals.length-1))*w},${h-(v/m)*h}`).join(' ');
  const fill=vals.map((v,i)=>`${(i/(vals.length-1))*w},${h-(v/m)*h}`).join(' ');
  return`<svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.5" vector-effect="non-scaling-stroke"/><polygon points="0,${h} ${fill} ${w},${h}" fill="${color}" fill-opacity="0.08"/></svg>`;
}

async function load(){
  const r=await fetch('/api/data?_='+Date.now());
  const d=await r.json();
  const s=d.sys,u=d.usage,h=d.hermes,hist=d.history||[];
  document.getElementById('dot').style.background=s.cpu>80?'var(--r)':s.cpu>50?'var(--y)':'var(--g)';

  let html='';

  // === Health matrix ===
  html+='<div class="health">';
  const health=[{n:'CPU',v:s.cpu,thr:80,c:s.cpu>80?'var(--r)':s.cpu>50?'var(--y)':'var(--g)'},
    {n:'RAM',v:s.ram_pct,thr:85,c:s.ram_pct>85?'var(--r)':s.ram_pct>70?'var(--y)':'var(--g)'},
    {n:'Disque',v:s.disk_pct,thr:85,c:s.disk_pct>85?'var(--r)':'var(--g)'},
    {n:'Messages',v:u.msgs,thr:0,c:'var(--a)'}];
  for(const x of health)html+=`<div class="hitem"><span class="hdot" style="background:${x.c}"></span>${x.n} ${x.v}${x.v>1&&x.n!='Messages'?'%':''}</div>`;
  html+='</div>';

  // === 3-col grid: System / LLM / Services ===
  html+='<div class="g3">';

  // COL 1: System metrics
  html+='<div class="c"><div class="ct">📊 Système</div><div class="row">';
  html+=met(s.cpu+'%','CPU',s.cpu>80?'var(--r)':s.cpu>50?'var(--y)':'var(--a)');
  html+=met(fmt(s.ram_u)+'/'+fmt(s.ram_t),'RAM '+s.ram_pct+'%');
  html+=met(s.disk_pct+'%','Disque');
  html+='</div>'+spark([s.cpu,s.ram_pct,s.disk_pct,s.load[0]*10,50],120,28,'var(--a)')+'</div>';

  // COL 2: LLM Usage
  html+='<div class="c"><div class="ct">🧠 LLM — '+u.model+'</div><div class="row">';
  html+=met(fmtT(u.d.t),'Aujourd\'hui');
  html+=met(fmtT(u.w.t),'7 jours');
  html+=met(fmtT(u.m.t),'30 jours');
  html+='</div>';
  const tokVals=hist.map(h=>h.t/1000);
  html+=spark(tokVals,120,28,'var(--p)')+'</div>';

  // COL 3: Services health
  html+='<div class="c"><div class="ct">🔧 Services</div>';
  for(const[n,sv]of Object.entries(h.svc)){
    const cl=sv==='active'?'bg':'br';const lb=sv==='active'?'✅':'❌';
    html+=`<div class="jr"><span>${n}</span><span class="b ${cl}">${lb}</span></div>`;}
  html+='</div></div>';

  // === Bottom: 2-col: Jobs + Activity ===
  html+='<div class="g2">';

  // Left: Jobs
  html+='<div class="c"><div class="ct">⏰ Jobs ('+h.jobs.length+')</div>';
  const errs=h.jobs.filter(j=>j.s==='error');
  if(errs.length)html+=`<div style="color:var(--r);font-size:.8em;margin-bottom:8px">🔴 ${errs.length} en erreur : ${errs.map(e=>e.n).join(', ')}</div>`;
  for(const j of h.jobs.slice(0,20)){
    const cl=j.s==='ok'||!j.s?'bg':j.s==='error'?'br':'by';
    html+=`<div class="jr"><span>${j.n}</span><span class="b ${cl}">${j.s||'ok'}</span></div>`;}
  html+='</div>';

  // Right: Activity + server info
  html+='<div class="c"><div class="ct">📈 Activité</div><div class="row">';
  html+=met(u.sess+'','Sessions');
  html+=met(u.msgs+'','Messages');
  html+=met(fmtT(u.w.c)+'$','Coût/sem');
  html+='</div>';
  html+=`<div style="margin-top:12px;font-size:.82em;color:var(--m)">`;
  html+=`${s.host} · Uptime ${fmtUp(s.uptime)} · ${s.procs_total} process · ${s.conns} connexions`;
  html+=' · Net ↓'+fmt(s.net_r)+' ↑'+fmt(s.net_s);
  html+='</div></div>';

  html+='</div>';

  // Bottom row: token history chart (PC only)
  if(tokVals.length>=7){
    html+=`<div class="c" style="margin-top:10px"><div class="ct">📈 Tokens / jour (7 jours)</div>
    <div style="display:flex;align-items:end;gap:3px;height:80px;padding:10px 0">`;
    const mx=Math.max(...hist.map(h=>h.t),1);
    for(const day of hist){
      const pct=(day.t/mx)*100;
      const cl=day.t>mx*0.8?'var(--r)':day.t>mx*0.5?'var(--y)':'var(--a)';
      html+=`<div style="flex:1;display:flex;flex-direction:column;align-items:center;gap:4px">
        <span style="font-size:.65em;color:var(--m)">${fmtT(day.t)}</span>
        <div style="width:100%;height:${pct}%;background:${cl};border-radius:4px 4px 0 0;min-height:4px;transition:height .3s"></div>
        <span style="font-size:.6em;color:var(--m)">${day.d.slice(5)}</span></div>`;}
    html+='</div></div>';}

  document.getElementById('app').innerHTML=html;
}

function met(v,l,c){return`<div class="metric"><div class="v" style="color:${c||'var(--a)'}">${v}</div><div class="l">${l}</div></div>`}
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
            self._json({"sys": sys_data(), "usage": usage_data(), "hermes": hermes_data(), "history": token_history()})
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