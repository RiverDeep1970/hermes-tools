#!/usr/bin/env python3
"""Journal web server - sert l'edition courante et la page videos."""
import json, os, re
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8090
BASE = os.path.expanduser("~/.hermes/editions")
READ_STATUS_FILE = os.path.join(BASE, "read_status.json")
STATIC_DIR = os.path.expanduser("~/.hermes/journal-static")
STATIC_MIME = {"journal.css": "text/css; charset=utf-8", "journal.js": "application/javascript; charset=utf-8"}

# --- videos ---
VIDEO_DIR = os.path.expanduser("~/.hermes/video-journal/out")
VIDEO_INDEX = os.path.expanduser("~/.hermes/video-journal/videos.json")
VIDEO_STATE = os.path.expanduser("~/.hermes/video-journal/production.json")
PRODUCTION_MAX_AGE = 45 * 60  # au-dela, l'etat est considere perime (script tue)
# Nombre d'editions publiees sur le site (la page ET /api/videos). Le disque en
# garde davantage (voir --keep de update-videos-index.py) : marge de securite.
SITE_LIMIT = 7
MEDIA_MIME = {"mp4": "video/mp4", "jpg": "image/jpeg", "png": "image/png",
              "txt": "text/plain; charset=utf-8"}
# nom de fichier strict : [web/]slug.ext, aucune remontee de chemin possible
MEDIA_RE = re.compile(r"^(?:web/)?[A-Za-z0-9][A-Za-z0-9._-]*\.(?:mp4|jpg|png|txt)$")

def load_read_status():
    if not os.path.exists(READ_STATUS_FILE):
        return {}
    try:
        with open(READ_STATUS_FILE) as f:
            return json.load(f)
    except:
        return {}

def save_read_status(data):
    with open(READ_STATUS_FILE, "w") as f:
        json.dump(data, f)

def load_videos():
    """Index des videos. Ne renvoie que les SITE_LIMIT dernieres editions."""
    if not os.path.exists(VIDEO_INDEX):
        return {"updated": "", "videos": []}
    try:
        with open(VIDEO_INDEX) as f:
            data = json.load(f)
        if not isinstance(data, dict) or "videos" not in data:
            return {"updated": "", "videos": []}
        vids = data.get("videos") or []
        if not isinstance(vids, list):
            return {"updated": "", "videos": []}
        if len(vids) > SITE_LIMIT:
            data = dict(data)
            data["videos"] = vids[:SITE_LIMIT]
        return data
    except:
        return {"updated": "", "videos": []}

def load_production():
    """Renvoie l'etat de production en cours, ou None (absent ou perime)."""
    if not os.path.exists(VIDEO_STATE):
        return None
    try:
        with open(VIDEO_STATE) as f:
            d = json.load(f)
        started = d.get("started", "")
        from datetime import datetime
        t = datetime.strptime(started, "%Y-%m-%dT%H:%M:%SZ")
        age = (datetime.utcnow() - t).total_seconds()
        if age < 0 or age > PRODUCTION_MAX_AGE:
            return None
        return d
    except Exception:
        return None


# Journal HTML template
PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Le Journal</title>
<link rel="stylesheet" href="/static/journal.css">
</head>
<body>
<div class="hd"><h1>Le Journal</h1><div class="ed" id="edition"></div><div class="navv"><a href="/videos">Vidéos</a></div></div>
<div class="tabs" id="tabs"></div>
<div class="ticker-wrap"><div class="ticker" id="ticker"></div></div>
<div class="wp" id="content">Chargement...</div>
<script src="/static/journal.js"></script>
</body>
</html>"""

VIDEOS_PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Les Vidéos du Journal</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Georgia,'Times New Roman',serif;background:#f5f3ef;color:#1a1a1a}
.hd{background:#1a1a2e;color:#e8d5b7;padding:14px 16px;text-align:center;position:sticky;top:0;z-index:10}
.hd h1{font-size:28px;letter-spacing:3px;font-weight:400}
.hd .ed{font-size:12px;color:#a09070;margin-top:2px}
.hd .navv a{color:#c9a84c;font-size:13px;text-decoration:none}
.hd .navv a:hover{text-decoration:underline}
.wp{padding:14px;max-width:860px;margin:0 auto}
.lead{font-size:13px;color:#666;margin-bottom:16px;line-height:1.5}
.banner{display:none;background:#fdf6e3;border:1px solid #c9a84c;border-left:4px solid #c9a84c;color:#7a5c12;padding:11px 14px;border-radius:5px;margin-bottom:16px;font-size:13px;line-height:1.5}
.banner.on{display:block}
.banner b{color:#1a1a2e}
.card{background:#fff;border:1px solid #e2ddd4;border-radius:6px;padding:14px;margin-bottom:18px}
.card .date{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px}
.card h2{font-size:19px;font-weight:400;color:#1a1a2e;margin-bottom:4px}
.meta{font-size:12px;color:#999;margin-bottom:10px}
.thumb{width:100%;max-width:480px;border-radius:4px;display:block;margin-bottom:12px;background:#1a1a2e}
.btns{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px}
.btns button{font-family:inherit;font-size:13px;padding:8px 14px;border:1px solid #c9a84c;background:#fff;color:#1a1a2e;border-radius:4px;cursor:pointer}
.btns button:hover{background:#fdf8ec}
.btns button.on{background:#c9a84c;color:#fff;font-weight:700}
.btns a{font-family:inherit;font-size:13px;padding:8px 14px;border:1px solid #ddd;background:#fff;color:#666;border-radius:4px;text-decoration:none;line-height:1.2}
.player{margin-bottom:2px}
.chapters{margin-top:12px;border-top:1px solid #eee;padding-top:10px}
.chapters .ch-hd{font-size:11px;text-transform:uppercase;letter-spacing:1px;color:#888;margin-bottom:6px}
.chapters button.ch{display:block;width:100%;text-align:left;font-family:inherit;font-size:13px;line-height:1.35;padding:7px 9px;border:0;border-left:3px solid transparent;background:#faf9f6;color:#444;border-radius:3px;cursor:pointer;margin-bottom:3px}
.chapters button.ch:hover{background:#f2efe8}
.chapters button.ch.on{background:#fdf8ec;border-left-color:#c9a84c;color:#1a1a2e;font-weight:700}
.chapters .ct{display:inline-block;min-width:44px;color:#c9a84c;font-variant-numeric:tabular-nums}
.chapters button.ch.on .ct{color:#a8862c}
.chapters .chtxt{display:inline-block;margin-top:7px;font-size:12px;color:#999;text-decoration:none}
.chapters .chtxt:hover{text-decoration:underline;color:#c9a84c}
video{width:100%;max-width:480px;background:#000;border-radius:4px;display:block}
.vshort video{max-width:300px}
.empty{color:#888;font-style:italic;padding:20px 0}
.ft{text-align:center;font-size:11px;color:#aaa;padding:20px 0 30px}
</style>
</head>
<body>
<div class="hd"><h1>Les Vidéos</h1><div class="ed">Le Journal en images</div><div class="navv"><a href="/">← Retour au journal</a></div></div>
<div class="wp">
<div id="banner" class="banner __BANNER_CLASS__">__BANNER__</div>
<div class="lead">Le récapitulatif quotidien de l'édition, en version longue (16:9) et en format court (9:16). Les vidéos restent disponibles en téléchargement.</div>
<div id="list">__CARDS__</div>
<div class="ft">Généré automatiquement à partir de l'édition du jour.</div>
</div>
<script>
(function(){
  var box=document.getElementById('list');
  if(!box) return;
  var bn=document.getElementById('banner');
  if(bn&&bn.className.indexOf('on')>=0){setTimeout(function(){location.reload();},30000);}
  function up(el,cls){
    while(el&&el.nodeType===1&&(' '+el.className+' ').indexOf(' '+cls+' ')<0){el=el.parentNode;}
    return (el&&el.nodeType===1)?el:null;
  }
  function longBtn(card){return card.querySelector('button[data-src][data-v=""]');}
  function setOn(card,btn){
    var all=card.querySelectorAll('.btns button[data-src]');
    for(var i=0;i<all.length;i++){all[i].className='';}
    if(btn){btn.className='on';}
  }
  function player(card){
    var wrap=card.querySelector('.player');
    var v=wrap.querySelector('video');
    if(!v){v=document.createElement('video');v.controls=true;v.preload='none';wrap.appendChild(v);}
    return {wrap:wrap,v:v};
  }
  function load(p,src,poster,cls){
    p.wrap.className='player'+(cls||'');
    if(p.v.getAttribute('src')!==src){
      p.v.setAttribute('poster',poster||'');
      p.v.setAttribute('src',src);
      p.v.load();
    }
    return p.v;
  }
  box.onclick=function(e){
    var t=e.target||e.window.event;
    if(t.tagName!=='BUTTON') return;
    // 1) bouton Version longue / Format court
    if(t.getAttribute('data-src')){
      var card=up(t,'card');
      if(!card) return;
      setOn(card,t);
      var p=player(card);
      load(p,t.getAttribute('data-src'),t.getAttribute('data-poster'),
           t.getAttribute('data-v')?' vshort':'');
      try{p.v.play();}catch(err){}
      return;
    }
    // 2) chapitre : charge la version longue si besoin, puis seek
    var ts=t.getAttribute('data-t');
    if(ts===null||ts==='') return;
    var card2=up(t,'card');
    if(!card2) return;
    var cb=card2.querySelector('.chapters');
    if(!cb) return;
    var p2=player(card2);
    var v2=load(p2,cb.getAttribute('data-src'),cb.getAttribute('data-poster'),'');
    setOn(card2,longBtn(card2));
    var seek=function(){
      try{v2.currentTime=parseFloat(ts)||0;v2.play();}catch(err){}
    };
    if(v2.readyState>=1){seek();}
    else if(v2.addEventListener){v2.addEventListener('loadedmetadata',seek);}
    else{v2.onloadedmetadata=seek;}
    var chs=cb.querySelectorAll('button.ch');
    for(var j=0;j<chs.length;j++){chs[j].className='ch';}
    t.className='ch on';
  };
})();
</script>
</body>
</html>"""

def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))

def fmt_size(n):
    try:
        n = float(n)
    except Exception:
        return ""
    if n >= 1048576:
        return "%.1f Mo" % (n / 1048576.0)
    return "%d Ko" % int(n / 1024)

def fmt_dur(s):
    try:
        s = int(round(float(s)))
    except Exception:
        return ""
    m, sec = divmod(s, 60)
    return "%d min %02d" % (m, sec) if m else "%d s" % sec

def render_chapters(jt, thumb):
    """Liste de chapitres cliquable sous le lecteur (version longue uniquement)."""
    chs = jt.get("chapters") or []
    if not chs:
        return ""
    rows = []
    for c in chs:
        rows.append('<button class="ch" data-t="%s"><span class="ct">%s</span>%s</button>'
                    % (esc(c.get("start", 0)), esc(c.get("time", "")), esc(c.get("label", ""))))
    txt = jt.get("chapters_txt")
    dl = ('<a class="chtxt" href="/media/%s" download>Chapitres .txt (à coller dans la description YouTube)</a>'
          % esc(txt)) if txt else ""
    return ('<div class="chapters" data-src="/media/%s" data-poster="/media/%s">'
            '<div class="ch-hd">Chapitres</div>%s%s</div>'
            % (esc(jt.get("web") or jt.get("file") or ""), thumb, "".join(rows), dl))


def render_cards(data):
    vids = data.get("videos") or []
    if not vids:
        return '<div class="empty">Aucune vidéo pour le moment. La première sera publiée après la prochaine production.</div>'
    out = []
    for v in vids:
        date = esc(v.get("date", ""))
        label = esc(v.get("label", date))
        thumb = esc(v.get("thumb", ""))
        jt = v.get("jt") or {}
        sh = v.get("short") or {}
        title = esc(v.get("title") or label)
        pieces = []
        if jt.get("web") or jt.get("file"):
            pieces.append('<button data-src="/media/%s" data-poster="/media/%s" data-v="">Version longue</button>'
                          % (esc(jt.get("web") or jt.get("file")), thumb))
        if sh.get("file"):
            pieces.append('<button data-src="/media/%s" data-poster="/media/%s" data-v="1">Format court</button>'
                          % (esc(sh.get("file")), thumb))
        dls = []
        if jt.get("file"):
            dls.append('<a href="/media/%s" download>1080p · %s</a>' % (esc(jt["file"]), fmt_size(jt.get("size"))))
        if sh.get("file"):
            dls.append('<a href="/media/%s" download>Short · %s</a>' % (esc(sh["file"]), fmt_size(sh.get("size"))))
        out.append(
            '<div class="card">'
            '<div class="date">%s</div>'
            '<h2>%s</h2>'
            '<div class="meta">Version longue %s · Format court %s</div>'
            '%s'
            '<div class="btns">%s%s</div>'
            '<div class="player"></div>'
            '%s'
            '</div>' % (
                date, title,
                fmt_dur(jt.get("duration")), fmt_dur(sh.get("duration")),
                ('<img class="thumb" src="/media/%s" alt="Miniature du %s" loading="lazy">' % (thumb, date)) if thumb else "",
                "".join(pieces), "".join(dls), render_chapters(jt, thumb)))
    return "\n".join(out)

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]  # Remove query string
        if path == "/api/data":
            self._serve_json()
        elif path == "/api/read-status":
            self._serve_read_status()
        elif path == "/api/videos":
            self._serve_videos_json()
        elif path == "/videos":
            self._serve_videos_page()
        elif path.startswith("/media/"):
            self._serve_media(path[len("/media/"):])
        elif path.startswith("/static/"):
            self._serve_static(path[len("/static/"):])
        else:
            self._serve_html()

    def do_POST(self):
        path = self.path.split("?")[0]
        if path == "/api/mark-read":
            self._serve_mark_read()
        else:
            self.send_response(404)
            self.end_headers()

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def _serve_json(self):
        fp = os.path.join(BASE, "latest.json")
        if not os.path.exists(fp):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error":"no edition"}')
            return
        with open(fp) as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(data.encode())

    def _serve_static(self, name):
        # Strict whitelist; never build the path from raw user input.
        if name not in STATIC_MIME:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not Found")
            return
        fp = os.path.join(STATIC_DIR, name)
        if not os.path.isfile(fp):
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not Found")
            return
        with open(fp, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", STATIC_MIME[name])
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _serve_videos_json(self):
        body = json.dumps(load_videos(), ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _serve_videos_page(self):
        prod = load_production()
        if prod:
            label = esc(prod.get("label", ""))
            bcls = "on"
            banner = ("<b>Production en cours</b> (démarrée à %s). "
                      "L'édition du jour s'ajoutera en haut de cette page dans quelques minutes — "
                      "elle se rafraîchit toute seule." % label)
        else:
            bcls = ""
            banner = ""
        html = (VIDEOS_PAGE
                .replace("__BANNER_CLASS__", bcls)
                .replace("__BANNER__", banner)
                .replace("__CARDS__", render_cards(load_videos())))
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def _media_abspath(self, rel):
        """Chemin absolu sur, ou None. Aucune entree utilisateur ne peut sortir de VIDEO_DIR."""
        if not MEDIA_RE.match(rel or ""):
            return None
        root = os.path.realpath(VIDEO_DIR)
        fp = os.path.realpath(os.path.join(root, rel))
        if not fp.startswith(root + os.sep):
            return None
        return fp if os.path.isfile(fp) else None

    def _serve_media(self, rel):
        fp = self._media_abspath(rel)
        if not fp:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Not Found")
            return
        ext = fp.rsplit(".", 1)[-1].lower()
        ctype = MEDIA_MIME.get(ext, "application/octet-stream")
        size = os.path.getsize(fp)
        # Support des requetes Range : indispensable pour le seek dans un <video>.
        start, end = 0, size - 1
        status = 200
        rng = self.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
            if m:
                if m.group(1):
                    start = int(m.group(1))
                    if m.group(2):
                        end = min(int(m.group(2)), size - 1)
                elif m.group(2):
                    start = max(0, size - int(m.group(2)))
                if start > end or start >= size:
                    self.send_response(416)
                    self.send_header("Content-Range", "bytes */%d" % size)
                    self.end_headers()
                    return
                status = 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(length))
        if status == 206:
            self.send_header("Content-Range", "bytes %d-%d/%d" % (start, end, size))
        # Pas de cache long : les fichiers sont remplaces chaque jour.
        self.send_header("Cache-Control", "public, max-age=300")
        self.end_headers()
        with open(fp, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(65536, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                remaining -= len(chunk)

    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(PAGE.encode())

    def _serve_read_status(self):
        self._json_response(load_read_status())

    def _serve_mark_read(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        ids = body.get("ids", [])
        if not isinstance(ids, list):
            self._json_response({"ok": False, "error": "ids must be a list"}, 400)
            return
        rs = load_read_status()
        from datetime import datetime
        for rid in ids:
            if isinstance(rid, str) and rid:
                rs[rid] = datetime.now().isoformat()
        save_read_status(rs)
        self._json_response({"ok": True})

    def log_message(self, *a): pass


if __name__ == "__main__":
    # Importable pour les tests : le serveur ne demarre qu'en execution directe.
    print("Journal sur http://localhost:{}".format(PORT))
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
