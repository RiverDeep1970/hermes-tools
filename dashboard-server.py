#!/usr/bin/env python3
"""Dashboard Hermes v2 — stable, mobile + tablette."""
import json, os, re, hashlib, uuid, sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from urllib.parse import unquote
import subprocess

PORT = 8082
HERMES = os.path.expanduser("~/.hermes")
SESSIONS = {}
PASS_HASH = hashlib.sha256(b"alexis:medoc2026").hexdigest()
DASH_VER = "v2.0"

def auth(h):
    for c in h.headers.get('Cookie','').split(';'):
        c = c.strip()
        if c.startswith('dash_session='):
            s = SESSIONS.get(c.split('=',1)[1])
            if s and (datetime.now().timestamp() - s) < 86400: return True
    return False

def get_procs():
    try:
        r = subprocess.run(["ps","aux","--sort=-%cpu","--no-headers"], capture_output=True, text=True, timeout=3)
        lines = r.stdout.strip().split("\n")
        return [{"c": l.split()[2], "m": l.split()[3], "n": l.split()[10][:18]}
                for l in lines[:5] if len(l.split()) > 10]
    except: return []

def sys_data():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage('/')
        boot = datetime.fromtimestamp(psutil.boot_time())
        up = int((datetime.now() - boot).total_seconds())
        net = psutil.net_io_counters()
        load = psutil.getloadavg()
        return {
            "cpu": round(cpu,1), "ram": round(mem.percent,1), "ram_u": mem.used, "ram_t": mem.total,
            "swap": round(swap.percent,1), "swap_u": swap.used, "swap_t": swap.total,
            "disk": round(disk.percent,1), "disk_f": disk.free,
            "cores": psutil.cpu_count(), "up": up, "load": [round(l,2) for l in load],
            "net_s": net.bytes_sent, "net_r": net.bytes_recv,
            "conns": len(psutil.net_connections()), "procs": len(psutil.pids()),
            "host": os.uname().nodename, "top": get_procs()
        }
    except: return {"cpu":0,"ram":0,"ram_u":0,"ram_t":1,"swap":0,"disk":0,"up":0,"host":"?","top":[]}

def usage_data():
    try:
        conn = sqlite3.connect(os.path.join(HERMES, "state.db"))
        cur = conn.cursor()
        cur.execute("SELECT model, billing_provider FROM sessions WHERE model IS NOT NULL AND model != '' ORDER BY started_at DESC LIMIT 1")
        row = cur.fetchone()
        model = row[0] if row else "?"; prov = row[1] if row and row[1] else "?"
        now = datetime.now()
        d0 = datetime(now.year, now.month, now.day).timestamp()
        w0 = (now - timedelta(days=now.weekday())).replace(hour=0,minute=0,second=0).timestamp()
        m0 = datetime(now.year, now.month, 1).timestamp()
        cur.execute("SELECT started_at, input_tokens, output_tokens, estimated_cost_usd FROM sessions WHERE started_at IS NOT NULL")
        dt, dc, wt, wc, mt, mc = 0,0,0,0,0,0
        for r in cur.fetchall():
            ts = r[0] or 0; toks = (r[1] or 0)+(r[2] or 0); cst = r[3] or 0
            if ts >= d0: dt+=toks; dc+=cst
            if ts >= w0: wt+=toks; wc+=cst
            if ts >= m0: mt+=toks; mc+=cst
        cur.execute("SELECT COUNT(*) FROM messages WHERE timestamp >= ?", (d0,))
        msgs = cur.fetchone()[0]
        conn.close()
        c_disp = "<0.01$" if dc < 0.01 else f"{dc:.2f}$"
        return {"m":model,"p":prov,"dt":dt,"dc":c_disp,"wt":wt,"wc":wc,"mt":mt,"mc":mc,"msgs":msgs}
    except: return {"m":"?","p":"?","dt":0,"dc":"0$","wt":0,"wc":0,"mt":0,"msgs":0}

def hermes_data():
    svc = {}
    for s in ["mood-tracker","med-tracker","mood-tracker-tunnel","dashboard-tracker"]:
        try:
            r = subprocess.run(["systemctl","is-active",s], capture_output=True, text=True, timeout=3)
            svc[s] = r.stdout.strip()
        except: svc[s] = "unknown"
    jobs = []
    try:
        with open(os.path.join(HERMES, "cron", "jobs.json")) as f:
            data = json.load(f)
        for j in (data.get("jobs",[]) if isinstance(data,dict) else data):
            jobs.append({"n":j.get("name","?"),"s":j.get("last_status","")})
        jobs.sort(key=lambda x: (0 if x["s"]=="error" else 1, x["n"]))
    except: pass
    return {"svc":svc,"jobs":jobs[:25]}

def mem_history():
    try:
        fp = os.path.join(HERMES, "mem-log.json")
        if not os.path.exists(fp): return []
        with open(fp) as f: return json.load(f)[-48:]
    except: return []

HTML = """<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>⚡ Dash</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0a0a0f;color:#e0e0e0}
.hdr{background:#13131a;border-bottom:1px solid #1e1e2e;padding:12px 16px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:10}
.hdr h1{font-size:1em;display:flex;align-items:center;gap:6px}
.dt{width:8px;height:8px;border-radius:50%}
.lg{color:#6c6c80;font-size:.75em;text-decoration:none}
.ap{padding:10px 12px;max-width:900px;margin:0 auto}
.gr{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin-bottom:8px}
.sc{border:1px solid #1e1e2e;border-radius:8px;padding:10px 6px;text-align:center;background:#13131a}
.sc .v{font-size:1.1em;font-weight:700}
.sc .l{font-size:.6em;color:#6c6c80;margin-top:2px}
.sc .ba{height:2px;background:#1e1e2e;border-radius:2px;margin-top:4px;overflow:hidden}
.sc .ba .f{height:100%}
.cd{border:1px solid #1e1e2e;border-radius:8px;padding:10px 12px;margin-bottom:8px;background:#13131a}
.st{font-size:.65em;color:#6c6c80;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px}
.ln{display:flex;justify-content:space-between;padding:3px 0;font-size:.78em;border-bottom:1px solid rgba(255,255,255,.03)}
.ln:last-child{border:0}
.b{display:inline-block;padding:1px 7px;border-radius:3px;font-size:.65em;font-weight:600}
.ok{background:rgba(34,197,94,.12);color:#22c55e}
.er{background:rgba(239,68,68,.12);color:#ef4444}
.wa{background:rgba(234,179,8,.12);color:#eab308}
.in{color:#6c6c80;font-size:.75em}
@media(max-width:480px){.ch{display:none}}
</style></head>
<body>
<div class="hdr"><h1><span class="dt" id="dt"></span> ⚡ Dashboard</h1><a class="lg" href="/logout">Quitter</a></div>
<div class="ap" id="ap">Chargement...</div>
<script>
(function(){
  var A=document.getElementById('ap');
  function f(b){var u=['B','KB','MB','GB'];for(var i=0;i<u.length;i++){if(b<1024)return b.toFixed(1)+' '+u[i];b/=1024}return b.toFixed(1)+' TB'}
  function u(s){var d=Math.floor(s/86400),h=Math.floor((s%86400)/3600),m=Math.floor((s%3600)/60);return(d?d+'j ':'')+(h?h+'h ':'')+m+'m'}
  function n(n){if(n>=1e6)return(n/1e6).toFixed(1)+'M';if(n>=1e3)return(n/1e3).toFixed(1)+'k';return String(n)}

  function ld(){
    var x=new XMLHttpRequest();
    x.open('GET','/api/data?_='+Date.now(),true);
    x.timeout=8000;
    x.onload=function(){
      try{
        var d=JSON.parse(x.responseText),s=d.sys,u=d.usage,h=d.hermes,mem=d.mem||[];
        document.getElementById('dt').style.background=s.cpu>80?'#ef4444':s.cpu>50?'#eab308':'#22c55e';
        var h='<div class="gr">';
        h+=C(s.cpu+'%','CPU',s.cpu,'#00d4ff');h+=C(f(s.ram_u)+'/'+f(s.ram_t),'RAM',s.ram,'#22c55e');
        h+=C(f(s.swap_u)+'/'+f(s.swap_t),'Swap',s.swap,'#7c3aed');
        h+=C(s.disk+'%','Disque',s.disk,'#eab308');h+=C(n(u.dt),'Tokens',0,'#00d4ff');
        h+=C(u.dc,'Coût',0,'#22c55e');
        h+='</div>';
        // Graphe
        if(mem.length>=2){
          h+='<div class="cd ch"><div class="st">📊 RAM '+s.ram+'% / Swap '+s.swap+'%</div><div style="display:flex;align-items:end;gap:1px;height:40px">';
          for(var i=0;i<mem.length;i++){var e=mem[i];
            h+='<div style="flex:1;display:flex;flex-direction:column;gap:1px">';
            h+='<div style="width:100%;height:'+e.s+'%;background:#7c3aed;border-radius:1px 1px 0 0;min-height:1px;opacity:.4"></div>';
            var rc=e.r>80?'#ef4444':e.r>50?'#eab308':'#22c55e';
            h+='<div style="width:100%;height:'+e.r+'%;background:'+rc+';border-radius:0 0 1px 1px;min-height:1px"></div>';}
          h+='</div></div>';}
        // LLM
        h+='<div class="cd"><div class="st">🧠 '+u.m+'</div><div class="in">'
          +n(u.dt)+' tok · '+u.dc+' aujourd\'hui · '+n(u.wt)+' / 7j</div></div>';
        // Services
        h+='<div class="cd"><div class="st">🔧 Services</div>';
        if(h.svc){var sn=Object.keys(h.svc);
          for(var i=0;i<sn.length;i++){var n=sn[i],sv=h.svc[n];
            h+='<div class="ln"><span>'+n+'</span><span class="b '+(sv==='active'?'ok':'er')+'">'+(sv==='active'?'✅':'❌')+'</span></div>';}}
        h+='</div>';
        // Jobs
        h+='<div class="cd"><div class="st">⏰ Jobs</div>';
        if(h.jobs&&h.jobs.length){
          for(var i=0;i<h.jobs.length&&i<20;i++){var j=h.jobs[i];
            var jc=j.s==='ok'||!j.s?'ok':j.s==='error'?'er':'wa';
            h+='<div class="ln"><span>'+j.n+'</span><span class="b '+jc+'">'+(j.s||'ok')+'</span></div>';}}
        h+='</div>';
        // Infos + version
        h+='<div class="cd"><div class="st">🖥️ '+s.host+' · <span style="color:#6c6c80;font-weight:400">'+'v2.0'+'</span></div>';
        h+='<div class="in">⏱️ '+u(s.up)+' · 📶 '+s.conns+' cnx · 💬 '+u.msgs+' msg</div></div>';
        A.innerHTML=h;
      }catch(e){A.innerHTML='<div style="padding:30px;text-align:center;color:#ef4444">❌ '+e.message+'</div>';}
    };
    x.onerror=function(){A.innerHTML='<div style="padding:30px;text-align:center;color:#ef4444">❌ Réseau. <a href="/login" style="color:#00d4ff">Reconnexion</a></div>';};
    x.ontimeout=function(){A.innerHTML='<div style="padding:30px;text-align:center;color:#eab308">⏱️ Timeout. <a href="/" style="color:#00d4ff">Réessayer</a></div>';};
    x.send();
  }
  function C(v,l,p,c){return'<div class="sc" style="border-color:'+c+'33"><div class="v" style="color:'+c+'">'+v+'</div><div class="l">'+l+'</div><div class="ba"><div class="f" style="width:'+Math.min(p,100)+'%;background:'+c+'"></div></div></div>';}
  ld();
  setInterval(ld,30000);
})();
</script></body></html>"""

LOGIN = """<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>⚡ Dash</title><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:#0a0a0f;color:#e0e0e0;height:100vh;display:flex;align-items:center;justify-content:center}.l{background:#13131a;border:1px solid #1e1e2e;border-radius:16px;padding:28px;width:280px}h1{text-align:center;margin-bottom:18px;font-size:1.2em}input{width:100%;padding:11px;background:#1a1a24;border:1px solid #1e1e2e;border-radius:10px;color:#e0e0e0;margin-bottom:10px;font-size:.95em}button{width:100%;padding:11px;background:linear-gradient(135deg,#00d4ff,#7c3aed);color:#fff;border:none;border-radius:10px;font-size:.95em}</style></head><body><div class="l"><h1>⚡ Dashboard</h1><form method="POST" action="/login"><input type="text" name="u" placeholder="Utilisateur" required><input type="password" name="p" placeholder="Mot de passe" required><button>Se connecter</button></form></div></body></html>"""

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/login': self._html(LOGIN)
        elif self.path == '/logout': self._logout()
        elif not auth(self): self._redir('/login')
        elif self.path.startswith('/api/data'):
            self._json({"sys": sys_data(), "usage": usage_data(), "hermes": hermes_data(), "mem": mem_history(), "ver": DASH_VER})
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
                self.send_header('Set-Cookie', f'dash_session={sid}; Path=/; Max-Age=86400; Secure; SameSite=Lax')
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

print(f"⚡ Dashboard v{DASH_VER} sur http://localhost:{PORT}")
HTTPServer(("0.0.0.0", PORT), H).serve_forever()