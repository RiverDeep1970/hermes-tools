#!/usr/bin/env python3
"""Dashboard Hermes v3 — version stable."""
import json, os, hashlib, uuid, sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta
from urllib.parse import unquote

PORT = 8082
HERMES = os.path.expanduser("~/.hermes")
SESSIONS = {}
PASS_HASH = hashlib.sha256(b"alexis:medoc2026").hexdigest()

with open(os.path.join(os.path.dirname(__file__), "dashboard.html")) as f:
    PAGE = f.read()

LOGIN = """<!DOCTYPE html><html lang="fr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>Dash</title><style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,sans-serif;background:#0a0a0f;color:#ddd;height:100vh;display:flex;align-items:center;justify-content:center}.l{background:#13131a;border:1px solid #1e1e2e;border-radius:16px;padding:28px;width:280px}h1{text-align:center;margin-bottom:18px;font-size:1.2em}input{width:100%;padding:11px;background:#1a1a24;border:1px solid #1e1e2e;border-radius:10px;color:#ddd;margin-bottom:10px;font-size:.95em}button{width:100%;padding:11px;background:linear-gradient(135deg,#00d4ff,#7c3aed);color:#fff;border:none;border-radius:10px;font-size:.95em}</style></head><body><div class="l"><h1>Dashboard</h1><form method="POST" action="/login"><input type="text" name="u" placeholder="Utilisateur" required><input type="password" name="p" placeholder="Mot de passe" required><button>Se connecter</button></form></div></body></html>"""

def auth(h):
    for c in h.headers.get('Cookie','').split(';'):
        c = c.strip()
        if c.startswith('dash_session='):
            s = SESSIONS.get(c.split('=',1)[1])
            if s and (datetime.now().timestamp() - s) < 86400: return True
    return False

def sys_data():
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.3)
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        disk = psutil.disk_usage('/')
        boot = datetime.fromtimestamp(psutil.boot_time())
        up = int((datetime.now() - boot).total_seconds())
        return {
            "c": round(cpu,1), "r": round(mem.percent,1),
            "ru": mem.used, "rt": mem.total,
            "s": round(swap.percent,1), "su": swap.used, "st": swap.total,
            "d": round(disk.percent,1),
            "u": up, "cn": len(psutil.net_connections()),
            "h": os.uname().nodename
        }
    except: return {"c":0,"r":0,"ru":0,"rt":1,"s":0,"d":0,"u":0,"h":"?","cn":0}

def usage_data():
    try:
        conn = sqlite3.connect(os.path.join(HERMES, "state.db"))
        cur = conn.cursor()
        cur.execute("SELECT model FROM sessions WHERE model IS NOT NULL ORDER BY started_at DESC LIMIT 1")
        row = cur.fetchone()
        model = row[0] if row else "?"
        now = datetime.now()
        d0 = datetime(now.year, now.month, now.day).timestamp()
        w0 = (now - timedelta(days=now.weekday())).replace(hour=0,minute=0,second=0).timestamp()
        cur.execute("SELECT started_at, input_tokens, output_tokens, estimated_cost_usd FROM sessions WHERE started_at IS NOT NULL")
        dt, dc, wt, wc = 0,0,0,0
        for r in cur.fetchall():
            ts = r[0] or 0; toks = (r[1] or 0)+(r[2] or 0); cst = r[3] or 0
            if ts >= d0: dt+=toks; dc+=cst
            if ts >= w0: wt+=toks; wc+=cst
        cur.execute("SELECT COUNT(*) FROM messages WHERE timestamp >= ?", (d0,))
        msgs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM sessions WHERE started_at >= ?", (d0,))
        sess_today = cur.fetchone()[0]
        conn.close()
        cd = "<0.01$" if dc < 0.01 else f"{dc:.2f}$"
        cw = "<0.01$" if wc < 0.01 else f"{wc:.2f}$"
        return {"m":model,"dt":dt,"dc":cd,"wt":wt,"wc":cw,"msgs":msgs,"ss":sess_today}
    except: return {"m":"?","dt":0,"dc":"0$","wt":0,"wc":"0$","msgs":0,"ss":0}

def mem_history():
    try:
        fp = os.path.join(HERMES, "mem-log.json")
        if not os.path.exists(fp): return []
        with open(fp) as f: return json.load(f)[-48:]
    except: return []

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/login': self._html(LOGIN)
        elif self.path == '/logout': self._logout()
        elif self.path.startswith('/api/data'):
            if not auth(self): self._json({"e":"auth"},401)
            else: self._json({"sys":sys_data(),"usage":usage_data(),"mem":mem_history()})
        elif self.path.startswith('/api/'): self._json({"e":"unknown"},404)
        else: self._html(PAGE)
    def do_POST(self):
        if self.path == '/login':
            raw = self.rfile.read(int(self.headers['Content-Length'])).decode()
            p = {}
            for kv in raw.split('&'):
                if '=' in kv: k, v = kv.split('=',1); p[k] = unquote(v)
            if hashlib.sha256(f"{p.get('u','')}:{p.get('p','')}".encode()).hexdigest() == PASS_HASH:
                sid = uuid.uuid4().hex
                SESSIONS[sid] = datetime.now().timestamp()
                self.send_response(302)
                self.send_header('Location', '/')
                self.send_header('Set-Cookie', f'dash_session={sid}; Path=/; Max-Age=86400; SameSite=Lax')
                self.end_headers()
            else: self._redir('/login')
    def _html(self, h):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        self.end_headers()
        self.wfile.write(h.encode())
    def _json(self, d, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
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

print(f"Dashboard v3 sur http://localhost:{PORT}")
HTTPServer(("0.0.0.0", PORT), H).serve_forever()