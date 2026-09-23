#!/usr/bin/env python3
"""Journal web server - sert l'edition courante."""
import json, os, re
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8090
BASE = os.path.expanduser("~/.hermes/editions")
READ_STATUS_FILE = os.path.join(BASE, "read_status.json")

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

# Journal HTML template
PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Le Journal</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Georgia,'Times New Roman',serif;background:#f5f3ef;color:#1a1a1a;padding:0}
.hd{background:#1a1a2e;color:#e8d5b7;padding:14px 16px;text-align:center;position:sticky;top:0;z-index:10}
.hd h1{font-size:28px;letter-spacing:3px;font-weight:400}
.hd .ed{font-size:12px;color:#a09070;margin-top:2px}
.tabs{display:flex;background:#2a2a3e;overflow-x:auto;position:sticky;top:52px;z-index:9}
.tab{padding:10px 16px;color:#a09070;cursor:pointer;white-space:nowrap;font-size:14px;border-bottom:2px solid transparent;transition:all .2s}
.tab:hover{color:#e8d5b7;background:rgba(255,255,255,.05)}
.tab.active{color:#e8d5b7;border-bottom-color:#c9a84c;font-weight:700}
.tab .badge{display:none;background:#c9a84c;color:#1a1a2e;font-size:10px;padding:1px 6px;border-radius:8px;margin-left:6px;font-weight:700}
.tab .badge.show{display:inline}
.wp{padding:12px;max-width:800px;margin:0 auto}
.pane{display:none}
.pane.active{display:block}
.art{border-bottom:1px solid #ddd;padding:14px 0}
.art:last-child{border:0}
.art .src{font-size:11px;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px}
.art .src .tag{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;margin-left:6px}
.tag-newsletter{background:#e8f0fe;color:#1967d2}
.tag-youtube{background:#fce8e6;color:#c5221f}
.tag-reddit{background:#e8f5e9;color:#1b8a3d}
.tag-echecs{background:#e8f5e9;color:#1b8a3d;font-weight:700}
.tag-crypto{background:#fff3e0;color:#e65100}
.tag-agenda{background:#f3e8fd;color:#7c3aed}
.tag-event-sport{background:#fce8e6;color:#c5221f;font-weight:700}
.tag-event-personal{background:#e8f0fe;color:#1967d2}
.tag-marquante{background:#fef3c7;color:#92400e;font-weight:700}
.art h3{font-size:17px;margin-bottom:4px;line-height:1.3}
.art h3 a{color:#1a1a2e;text-decoration:none}
.art h3 a:hover{color:#c9a84c}
.art p{font-size:14px;color:#444;line-height:1.5;margin-bottom:4px}
.art .meta{font-size:11px;color:#999;margin-top:2px}
.art .pts{padding-left:16px;margin:6px 0}
.art .pts li{font-size:13px;color:#555;margin:2px 0}
.unread{border-left:3px solid #c9a84c;padding-left:10px}
.crypto-grid{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:8px 0}
.crypto-item{border:1px solid #e0d5c0;border-radius:6px;padding:8px;text-align:center;background:#faf8f5}
.crypto-item .sym{font-weight:700;font-size:14px}
.crypto-item .pr{font-size:15px;margin:2px 0}
.crypto-item .ch{font-size:12px}
.crypto-item .up{color:#1b8a3d}
.crypto-item .down{color:#c5221f}
.agenda-item{padding:6px 0;border-bottom:1px solid #eee;font-size:14px}
.agenda-item:last-child{border:0}
/* Ticker crypto */
.ticker-wrap{background:#1a1a2e;border-top:1px solid #2a2a3e;border-bottom:1px solid #2a2a3e;overflow:hidden;position:sticky;top:88px;z-index:8;height:28px;line-height:28px}
.ticker{display:inline-flex;white-space:nowrap;animation:scroll 40s linear infinite}
.ticker:hover{animation-play-state:paused}
.ticker-item{display:inline-flex;align-items:center;gap:4px;padding:0 14px;font-size:12px;flex-shrink:0}
.ticker-item .sym{font-weight:700;color:#c9a84c}
.ticker-item .pr{color:#ddd}
.ticker-item .ch{font-size:11px}
.ticker-item .ch.up{color:#34d399}
.ticker-item .ch.down{color:#f87171}
.ticker-item .sep{color:#3a3a5e}
@keyframes scroll{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}
@media(max-width:480px){.hd h1{font-size:22px}.tab{padding:8px 12px;font-size:12px}.crypto-grid{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<div class="hd"><h1>Le Journal</h1><div class="ed" id="edition"></div></div>
<div class="tabs" id="tabs"></div>
<div class="ticker-wrap"><div class="ticker" id="ticker"></div></div>
<div class="wp" id="content">Chargement...</div>
<script>
(function(){
var C=document.getElementById("content");
var T=document.getElementById("tabs");
var E=document.getElementById("edition");
var tabNames=["une","newsletters","youtube","reddit","echecs","immobilier","agenda"];
var tabLabels=["A la une","Newsletters","YouTube","Reddit","Échecs","Immobilier","Agenda"];
var readItems={};
// Load read status from server
function loadReadStatus(){
  var x=new XMLHttpRequest();
  x.open("GET","/api/read-status?_="+Date.now(),true);
  x.onload=function(){
    if(x.status===200){
      try{readItems=JSON.parse(x.responseText)||{}}catch(e){}
    }
  };
  x.send();
}
loadReadStatus();
function saveRead(){
  // Send unread IDs to server
  var ids=[];
  for(var k in readItems){if(readItems.hasOwnProperty(k)){ids.push(k)}}
  if(!ids.length)return;
  var x=new XMLHttpRequest();
  x.open("POST","/api/mark-read",true);
  x.setRequestHeader("Content-Type","application/json");
  x.send(JSON.stringify({ids:ids}));
}

function render(data){
  if(!data||!data.sections){C.innerHTML='<div style="padding:30px;text-align:center;color:#888">Aucune edition disponible</div>';return}
  E.textContent=(data.edition||"?")+" - "+data.date+" "+data.time;
  
  // Tabs
  var th="";
  for(var i=0;i<tabNames.length;i++){
    var n=tabNames[i],l=tabLabels[i];
    var section=data.sections[n]||[];
    var count=0;
    if(n==="une"){count=section.length}else if(n==="agenda"){count=section.length}else{count=typeof section != "undefined" && section !== null && section.length ? section.length : 0}
    th+='<div class="tab'+(i===0?" active":"")+'" data-tab="'+n+'">'+l+'<span class="badge'+(count>0?" show":"")+'">'+count+'</span></div>';
  }
  T.innerHTML=th;
  
  // Attach tab click listeners
  var tabEls=T.querySelectorAll(".tab");
  for(var ti=0;ti<tabEls.length;ti++){
    (function(el){tabEls[ti].onclick=function(){switchTab(el)}})(tabEls[ti]);
  }
  
  // Panes
  var html="";
  for(var i=0;i<tabNames.length;i++){
    var n=tabNames[i];
    html+='<div class="pane'+(i===0?" active":"")+'" id="pane-'+n+'">';
    if(n==="une"){html+=renderUne(data.sections[n]||[])}
    else if(n==="agenda"){html+=renderAgenda(data.sections[n]||[])}
    else if(n==="immobilier"){html+=renderImmo(data.sections[n]||[])}
    else{html+=renderList(data.sections[n]||[],n)}
    html+='</div>';
  }
  C.innerHTML=html;
  buildTicker(data);
  
  // Mark tab items as read
  var activeTab=document.querySelector(".tab.active");
  if(activeTab)markTabRead(activeTab.dataset.tab);
}

function renderUne(items){
  if(!items.length)return '<div style="padding:20px;text-align:center;color:#888">Aucun article a la une</div>';
  var h="";
  for(var i=0;i<items.length;i++){
    var it=items[i];
    var itemId=it.url||it.title||"item-"+i;
    var isRead=readItems[itemId];
    h+='<div class="art'+(isRead?"":" unread")+'">';
    var typeLabel=it.type;
    if(it.type==="event-sport"){typeLabel="\\u26BD Sport"}
    else if(it.type==="event-personal"){typeLabel="\\uD83D\\uDCC5 Agenda"}
    else if(it.type==="marquante"){typeLabel="\\uD83D\\uDCA1 Marquante"}
    h+='<div class="src">'+it.source+' <span class="tag tag-'+it.type+'">'+typeLabel+'</span></div>';
    if(it.type==="crypto-summary"&&it.data){
      // affichage uniquement dans le ticker
    }else{
      h+='<h3>'+(it.url?'<a href="'+it.url+'" target="_blank">':'')+it.title+(it.url?'</a>':'')+'</h3>';
      if(it.summary)h+='<p>'+it.summary+'</p>';
      if(it.key_points&&it.key_points.length){
        h+='<ul class="pts">';
        for(var p=0;p<it.key_points.length;p++){h+='<li>'+it.key_points[p]+'</li>'}
        h+='</ul>';
      }
    }
    h+='<div class="meta">'+it.date+(it.author?" | "+it.author:"")+'</div>';
    h+='</div>';
  }
  return h;
}

function renderList(items,tab){
  if(!items||!items.length)return '<div style="padding:20px;text-align:center;color:#888">Aucun element</div>';
  var h="";
  for(var i=0;i<items.length;i++){
    var it=items[i];
    var itemId=it.url||it.title||"item-"+tab+"-"+i;
    var isRead=readItems[itemId];
    h+='<div class="art'+(isRead?"":" unread")+'">';
    h+='<div class="src">'+it.source+'</div>';
    h+='<h3>'+(it.url?'<a href="'+it.url+'" target="_blank">':'')+it.title+(it.url?'</a>':'')+'</h3>';
    if(it.summary)h+='<p>'+it.summary+'</p>';
    if(it.key_points&&it.key_points.length){
      h+='<ul class="pts">';
      for(var p=0;p<it.key_points.length;p++){h+='<li>'+it.key_points[p]+'</li>'}
      h+='</ul>';
    }
    if(tab==="newsletters"&&it.articles){
      for(var a=0;a<it.articles.length;a++){
        var art=it.articles[a];
        h+='<div style="margin:6px 0 6px 12px;padding:6px 0;border-bottom:1px solid #f0ede8">';
        h+='<strong>'+(art.url?'<a href="'+art.url+'" target="_blank">':'')+art.title+(art.url?'</a>':'')+'</strong>';
        if(art.summary)h+='<p style="font-size:13px;color:#555;margin:2px 0">'+art.summary+'</p>';
        h+='</div>';
      }
    }
    h+='<div class="meta">'+it.date+(it.author?" | "+it.author:"")+'</div>';
    h+='</div>';
  }
  return h;
}

function renderAgenda(items){
  if(!items.length)return '<div style="padding:20px;text-align:center;color:#888">Aucun evenement</div>';
  var h="";
  for(var i=0;i<items.length;i++){
    var it=items[i];
    var timeStr=it.time?" "+it.time:"";
    var cal=it.calendar||"Agenda";
    var tagClass=(it.type||"personal")==="sport"?"tag-event-sport":"tag-event-personal";
    h+='<div class="agenda-item">';
    h+='<strong>'+it.date+'</strong>'+timeStr;
    h+=' <span class="tag '+tagClass+'">'+cal+'</span>';
    h+=' — '+it.title;
    h+='</div>';
  }
  return h;
}

function renderImmo(items){
  if(!items.length)return '<div style="padding:20px;text-align:center;color:#888">Aucune annonce</div>';
  var h="";
  for(var i=0;i<items.length;i++){
    var it=items[i];
    var itemId=it.url||it.title||"immo-"+i;
    var isRead=readItems[itemId];
    h+='<div class="art'+(isRead?"":" unread")+'">';
    h+='<div class="src">'+it.source+' <span class="tag tag-newsletter">Immo</span></div>';
    h+='<h3>'+(it.url?'<a href="'+it.url+'" target="_blank">':'')+it.title+(it.url?'</a>':'')+'</h3>';
    if(it.price||it.surface||it.rooms){
      h+='<p style="font-size:15px">';
      if(it.price)h+='<strong>'+Number(it.price).toLocaleString('fr-FR')+' \u20AC</strong> ';
      if(it.surface)h+=it.surface+' m² ';
      if(it.rooms)h+=it.rooms+' pièces ';
      h+='</p>';
    }
    if(it.features&&it.features.length){
      h+='<p style="font-size:12px;color:#666">';
      for(var f=0;f<it.features.length;f++){
        h+='<span style="display:inline-block;background:#e8f0fe;color:#1967d2;padding:1px 6px;border-radius:3px;margin:2px">'+it.features[f]+'</span> ';
      }
      h+='</p>';
    }
    h+='<div class="meta">'+it.date+'</div>';
    h+='</div>';
  }
  return h;
}

function buildTicker(data){
  var el=document.getElementById("ticker");
  if(!el)return;
  var coins=data&&data._ticker;
  if(!coins||!coins.length){el.textContent="";return}
  var h="";
  for(var i=0;i<coins.length;i++){
    var c=coins[i];
    var ch=c.change_24h;
    var hasCh=ch!==null&&ch!==undefined;
    var cls=hasCh&&ch>=0?"up":"down";
    var displayCh=hasCh?(ch>=0?"+":"")+ch.toFixed(2)+"%":"N/A";
    h+='<span class="ticker-item">';
    h+='<span class="sym">'+c.symbol+'</span>';
    h+='<span class="pr">$'+c.price.toFixed(2)+'</span>';
    h+='<span class="ch '+cls+'">'+displayCh+'</span>';
    h+='<span class="sep">|</span>';
    h+='</span>';
  }
  el.innerHTML=h+h;
}

function switchTab(el){
  var tabs=document.querySelectorAll(".tab");
  for(var t=0;t<tabs.length;t++){tabs[t].classList.remove("active")}
  var panes=document.querySelectorAll(".pane");
  for(var p=0;p<panes.length;p++){panes[p].classList.remove("active")}
  el.classList.add("active");
  var tabName=el.getAttribute("data-tab");
  document.getElementById("pane-"+tabName).classList.add("active");
  markTabRead(tabName);
}

function markTabRead(tab){
  var pane=document.getElementById("pane-"+tab);
  if(!pane)return;
  var items=pane.querySelectorAll(".art.unread");
  var changed=false;
  for(var j=0;j<items.length;j++){
    var item=items[j];
    var link=item.querySelector("h3 a");
    var id=link?link.getAttribute("href"):item.querySelector("h3")?item.querySelector("h3").textContent:"";
    if(id&&!readItems[id]){readItems[id]=true;changed=true}
  }
  if(changed)saveRead();
}

function refresh(){
  var x=new XMLHttpRequest();
  x.open("GET","/api/data?_="+Date.now(),true);
  x.timeout=10000;
  x.onload=function(){
    try{
      if(x.status!==200){
        C.innerHTML='<div style="padding:30px;text-align:center;color:#c5221f">Erreur HTTP '+x.status+'</div>';
        return
      }
      var d=JSON.parse(x.responseText);
      if(d.error){C.innerHTML='<div style="padding:30px;text-align:center;color:#888">'+d.error+'</div>';return}
      render(d);
    }catch(e){
      C.innerHTML='<div style="padding:30px;text-align:center;color:#c5221f">Erreur: '+e.message+'<br><small>'+x.responseText.substring(0,200)+'</small></div>'
    }
  };
  x.onerror=function(){C.innerHTML='<div style="padding:30px;text-align:center;color:#c5221f">Reseau</div>'};
  x.ontimeout=function(){C.innerHTML='<div style="padding:30px;text-align:center;color:#eab308">Timeout</div>'};
  x.send();
}
refresh();
setInterval(refresh,60000);
})();
</script>
</body>
</html>"""

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.split("?")[0]  # Remove query string
        if path == "/api/data":
            self._serve_json()
        elif path == "/api/read-status":
            self._serve_read_status()
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
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data.encode())
    
    def _serve_html(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
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

print("Journal sur http://localhost:{}".format(PORT))
HTTPServer(("0.0.0.0", PORT), H).serve_forever()