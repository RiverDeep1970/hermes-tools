#!/usr/bin/env python3
"""Mood Tracker v3 — calendrier, stats, édition, dark mode, export CSV."""
import json, os, csv, io, urllib.parse
import calendar as calmod
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, date, timedelta
from collections import defaultdict

ENTRIES_DIR = os.path.expanduser("~/.hermes/life-tracker/entries")
os.makedirs(ENTRIES_DIR, exist_ok=True)

MOOD_LABELS = {"1":"Mal","2":"Bof","3":"Bien","4":"Super","5":"Fatigué","6":"Malade","7":"Stressé","8":"Motivé"}
EMOJI = {"1":"😞","2":"😐","3":"🙂","4":"😄","5":"😴","6":"🤒","7":"😰","8":"🚀"}
MOOD_COLORS = {"1":"#ff6b6b","2":"#ffa94d","3":"#74b816","4":"#2b8a3e","5":"#748ffc","6":"#da77f2","7":"#f06595","8":"#ffd43b"}

HTML = r"""<!DOCTYPE html>
<html lang="fr" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0,user-scalable=no">
<title>📓 Mood</title>
<style>
/* === RESET === */
*{margin:0;padding:0;box-sizing:border-box;-webkit-tap-highlight-color:transparent}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:var(--bg);color:var(--text);min-height:100dvh;padding-bottom:80px;transition:background .3s,color .3s}
/* === THEMES === */
:root{--bg:#f5f5f7;--card:#fff;--text:#1c1c1e;--text2:#666;--text3:#999;--border:#e8e8ed;--input-bg:#fafafa;--accent:#007aff;--accent-bg:#e8f0ff;--accent-text:#007aff;--good-bg:#e8ffe8;--good-text:#155724;--shadow:rgba(0,0,0,0.05);--danger:#ff3b30;--orange:#ff9500}
[data-theme=dark]{--bg:#000;--card:#1c1c1e;--text:#f5f5f7;--text2:#8e8e93;--text3:#636366;--border:#38383a;--input-bg:#2c2c2e;--accent:#0a84ff;--accent-bg:#1a2a4a;--accent-text:#0a84ff;--good-bg:#1a3a1a;--good-text:#34c759;--shadow:rgba(0,0,0,0.3);--danger:#ff453a;--orange:#ff9f0a}
/* === LAYOUT === */
.hdr{background:var(--card);padding:12px 16px;box-shadow:0 1px 4px var(--shadow);position:sticky;top:0;z-index:100;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border)}
.hdr h1{font-size:1.15em;color:var(--text)}
.hdr-r{display:flex;gap:10px;align-items:center}
.dm-btn{background:none;border:2px solid var(--border);border-radius:10px;font-size:1em;padding:4px 8px;cursor:pointer;color:var(--text2);transition:all .2s;line-height:1}
.dm-btn:active{transform:scale(.9)}
.c{padding:12px 12px;max-width:500px;margin:0 auto}
.card{background:var(--card);border-radius:16px;padding:16px;box-shadow:0 1px 6px var(--shadow);margin-bottom:12px;transition:background .3s}
h2{font-size:.8em;color:var(--text2);margin-bottom:10px;text-transform:uppercase;letter-spacing:.4px;display:flex;align-items:center;gap:6px}
/* === TABS === */
.tabs{display:flex;background:var(--card);border-bottom:1px solid var(--border);position:sticky;top:51px;z-index:99}
.tab{flex:1;text-align:center;padding:10px 6px;font-size:.85em;color:var(--text3);cursor:pointer;border-bottom:3px solid transparent;transition:all .2s;font-weight:500}
.tab:active{opacity:.7}
.tab.act{color:var(--accent);border-bottom-color:var(--accent)}
.tab-c{display:none;animation:fadeIn .25s ease}
.tab-c.act{display:block}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
/* === MOOD GRID === */
.moods{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:6px}
.mb{padding:10px 4px;border:2px solid var(--border);border-radius:12px;background:var(--input-bg);cursor:pointer;text-align:center;transition:all .15s ease}
.mb .e{font-size:1.5em;display:block;line-height:1.2}
.mb .l{font-size:.65em;color:var(--text2);display:block;margin-top:1px}
.mb:active{transform:scale(.92)}
.mb.sel{border-color:var(--accent);background:var(--accent-bg)}
.mb.sel .l{color:var(--accent-text);font-weight:600}
/* === FIELDS === */
.field{width:100%;padding:10px 12px;border:2px solid var(--border);border-radius:10px;font-size:.95em;margin-bottom:6px;background:var(--input-bg);color:var(--text);transition:border .2s,background .2s}
.field:focus{border-color:var(--accent);outline:none;background:var(--card)}
textarea.field{resize:vertical;min-height:44px;font-family:inherit}
::placeholder{color:var(--text3);opacity:1}
.quick{display:flex;gap:5px;flex-wrap:wrap;margin-bottom:8px}
.qb{padding:5px 12px;border:2px solid var(--border);border-radius:16px;background:var(--input-bg);font-size:.8em;cursor:pointer;color:var(--text);transition:all .15s}
.qb:active{transform:scale(.93)}
.qb.sel{border-color:#34c759;background:var(--good-bg);color:var(--good-text);font-weight:500}
/* === BUTTONS === */
.btn-row{display:flex;gap:8px}
.sb,.db{flex:1;padding:12px;border:none;border-radius:10px;font-size:1em;font-weight:600;cursor:pointer;transition:opacity .2s}
.sb{background:var(--accent);color:#fff}
.db{background:var(--danger);color:#fff}
.sb:active,.db:active{opacity:.7}
.sb:disabled{opacity:.4}
#st{text-align:center;padding:8px;border-radius:8px;display:none;font-size:.82em;margin-top:8px;transition:all .2s}
.succ{background:var(--good-bg);color:var(--good-text);display:block!important}
.err{background:#3a1a1a;color:#ff453a;display:block!important}
/* === TREND === */
.hw{display:flex;gap:5px;justify-content:center;padding:6px 0;flex-wrap:wrap}
.hd{width:32px;height:32px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:14px;flex-shrink:0;border:2px solid var(--border)}
.hl{font-size:8px;color:var(--text3);margin-top:1px;text-align:center;white-space:nowrap}
.hc{display:flex;flex-direction:column;align-items:center}
/* === HISTORY === */
.hp{padding:7px 0;border-bottom:1px solid var(--border);display:flex;gap:8px;align-items:flex-start;cursor:pointer;transition:background .15s;border-radius:6px;margin:0 -6px;padding:7px 6px}
.hp:hover{background:var(--input-bg)}
.hp:last-child{border:none}
.hp .d{font-size:.75em;color:var(--text3);min-width:32px;flex-shrink:0}
.hp .t{font-size:.85em;color:var(--text);flex:1}
.hp .t .s{color:var(--text2);font-size:.78em}
.hp .e-icon{font-size:1.2em;width:24px;text-align:center}
/* === CALENDAR === */
.cal-nav{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px}
.cal-nav button{background:var(--input-bg);border:2px solid var(--border);border-radius:10px;padding:6px 12px;font-size:.9em;cursor:pointer;color:var(--text);transition:all .15s}
.cal-nav button:active{transform:scale(.92)}
.cal-nav .m-title{font-weight:600;font-size:.95em;color:var(--text)}
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;text-align:center}
.cal-hd{padding:4px;font-size:.7em;color:var(--text3);font-weight:600}
.cal-d{padding:6px 0;font-size:.82em;cursor:pointer;transition:all .15s;border-radius:8px;color:var(--text);position:relative}
.cal-d:active{transform:scale(.9)}
.cal-d.other{color:var(--text3);opacity:.4}
.cal-d.today{font-weight:700}
.cal-d.today::after{content:'';position:absolute;bottom:2px;left:50%;transform:translateX(-50%);width:4px;height:4px;border-radius:50%;background:var(--accent)}
.cal-d .mood-dot{display:inline-block;width:28px;height:28px;border-radius:50%;line-height:28px;font-size:12px}
/* === STATS === */
.stat-row{display:flex;gap:8px;margin-bottom:10px}
.stat-box{flex:1;background:var(--input-bg);border-radius:12px;padding:10px;text-align:center;border:1px solid var(--border)}
.stat-box .val{font-size:1.3em;font-weight:700;color:var(--text)}
.stat-box .lbl{font-size:.65em;color:var(--text3);margin-top:2px;text-transform:uppercase}
.stat-bar{display:flex;height:20px;border-radius:10px;overflow:hidden;margin:8px 0}
.stat-bar div{transition:width .5s ease}
.stat-leg{display:flex;flex-wrap:wrap;gap:4px 12px;margin-top:6px}
.stat-leg span{font-size:.75em;color:var(--text2)}
.stat-leg .dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:3px}
/* === MODAL === */
.modal-over{position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.4);z-index:200;display:flex;align-items:flex-end;justify-content:center;opacity:0;pointer-events:none;transition:opacity .25s}
.modal-over.show{opacity:1;pointer-events:auto}
.modal{background:var(--card);border-radius:20px 20px 0 0;padding:20px;width:100%;max-width:500px;max-height:85vh;overflow-y:auto;transform:translateY(100%);transition:transform .25s ease}
.modal-over.show .modal{transform:translateY(0)}
.modal h3{font-size:1em;color:var(--text);margin-bottom:12px}
.modal .m-close{float:right;background:none;border:none;font-size:1.2em;color:var(--text3);cursor:pointer;padding:4px}
.modal .field{margin-bottom:6px}
/* === EMPTY === */
.empty{text-align:center;color:var(--text3);padding:20px;font-size:.85em}
/* === EXPORT === */
.export-btn{display:block;text-align:center;padding:10px;background:var(--input-bg);border:2px solid var(--border);border-radius:10px;color:var(--accent);font-size:.85em;font-weight:500;cursor:pointer;margin-top:6px;transition:all .15s}
.export-btn:active{transform:scale(.97)}
/* === RESPONSIVE SMALL === */
@media(max-width:380px){
  .moods{gap:5px}.mb{padding:8px 2px}.mb .e{font-size:1.2em}
  .cal-d{padding:4px 0;font-size:.75em}
  .stat-box .val{font-size:1.1em}
}
</style>
</head>
<body>
<div class="hdr">
  <h1>📓 Mood</h1>
  <div class="hdr-r">
    <button class="dm-btn" id="dm-btn" onclick="togDark()" title="Thème">🌙</button>
  </div>
</div>

<div class="tabs" id="tabs">
  <div class="tab act" data-tab="today" onclick="swTab('today')">📝 Aujourd'hui</div>
  <div class="tab" data-tab="cal" onclick="swTab('cal')">📅 Calendrier</div>
  <div class="tab" data-tab="stats" onclick="swTab('stats')">📊 Stats</div>
</div>

<div class="c">
<!-- TAB: TODAY -->
<div class="tab-c act" id="tab-today">
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
    <div class="btn-row">
      <button class="sb" id="sb" onclick="save()">💾 Enregistrer</button>
      <button class="db" id="db" onclick="delToday()" style="display:none">🗑️</button>
    </div>
    <div id="st"></div>
  </div>
  <div class="card">
    <h2>📅 7 derniers jours</h2>
    <div id="trend"></div>
    <div id="hist"></div>
  </div>
</div>

<!-- TAB: CALENDAR -->
<div class="tab-c" id="tab-cal">
  <div class="card">
    <div class="cal-nav">
      <button onclick="calMove(-1)">◀</button>
      <span class="m-title" id="cal-title"></span>
      <button onclick="calMove(1)">▶</button>
    </div>
    <div class="cal-grid" id="cal-grid"></div>
  </div>
  <div class="card" id="cal-detail-card">
    <h2 id="cal-day-title">Sélectionne un jour</h2>
    <div id="cal-detail"></div>
  </div>
</div>

<!-- TAB: STATS -->
<div class="tab-c" id="tab-stats">
  <div class="card">
    <h2>📊 Résumé du mois</h2>
    <div id="stats-summary"></div>
  </div>
  <div class="card">
    <h2>📈 Répartition</h2>
    <div id="stats-dist"></div>
  </div>
  <div class="card">
    <h2>🔥 Tendance</h2>
    <div id="stats-trend"></div>
  </div>
  <div class="card">
    <h2>💾 Données</h2>
    <div class="export-btn" onclick="expCSV()">⬇️ Exporter en CSV</div>
  </div>
</div>
</div>

<!-- MODAL -->
<div class="modal-over" id="modal">
  <div class="modal">
    <button class="m-close" onclick="closeMod()">✕</button>
    <h3 id="mod-title">Modifier</h3>
    <input type="hidden" id="mod-date">
    <div class="moods" id="mod-moods"></div>
    <input class="field" id="mod-lecture" placeholder="📚 Lecture">
    <input class="field" id="mod-serie" placeholder="📺 Série">
    <div class="quick" id="mod-quick"></div>
    <textarea class="field" id="mod-notes" placeholder="Notes libres..."></textarea>
    <div class="btn-row">
      <button class="sb" onclick="modSave()">💾 Enregistrer</button>
      <button class="db" onclick="modDel()">🗑️ Supprimer</button>
    </div>
    <div id="mod-st"></div>
  </div>
</div>

<script>
// === DATA ===
const ML=[
  {v:"1",e:"😞",l:"Mal"},{v:"2",e:"😐",l:"Bof"},{v:"3",e:"🙂",l:"Bien"},{v:"4",e:"😄",l:"Super"},
  {v:"5",e:"😴",l:"Fatigué"},{v:"6",e:"🤒",l:"Malade"},{v:"7",e:"😰",l:"Stressé"},{v:"8",e:"🚀",l:"Motivé"}
];
const ACT=["📖 Lecture","📺 Série","🏃 Sport","🎵 Musique","🍳 Cuisine","🌿 Promenade"];
const EM={1:"😞",2:"😐",3:"🙂",4:"😄",5:"😴",6:"🤒",7:"😰",8:"🚀"};
const MC={1:"#ff6b6b",2:"#ffa94d",3:"#74b816",4:"#2b8a3e",5:"#748ffc",6:"#da77f2",7:"#f06595",8:"#ffd43b"};
let sel=null, sact=[], msel=null, msact=[], calY, calM, editDate=null;

// === INIT ===
(function(){
  let h=''; for(const m of ML) h+='<div class="mb" data-v="'+m.v+'" onclick="pick(this)"><span class="e">'+m.e+'</span><span class="l">'+m.l+'</span></div>';
  document.getElementById('moods').innerHTML=h;
  let ha=''; for(const a of ACT) ha+='<div class="qb" onclick="togAct(this)">'+a+'</div>';
  document.getElementById('quick-act').innerHTML=ha;
  // Modal moods
  let hm=''; for(const m of ML) hm+='<div class="mb" data-v="'+m.v+'" onclick="modPick(this)"><span class="e">'+m.e+'</span><span class="l">'+m.l+'</span></div>';
  document.getElementById('mod-moods').innerHTML=hm;
  let hma=''; for(const a of ACT) hma+='<div class="qb" onclick="modTogAct(this)">'+a+'</div>';
  document.getElementById('mod-quick').innerHTML=hma;
})();

// === DARK MODE ===
(function(){
  const p=window.matchMedia('(prefers-color-scheme:dark)');
  const d=document.documentElement;
  const saved=localStorage.getItem('mood-theme');
  if(saved) d.dataset.theme=saved;
  else d.dataset.theme=p.matches?'dark':'light';
  document.getElementById('dm-btn').textContent=d.dataset.theme==='dark'?'☀️':'🌙';
  p.addEventListener('change',function(e){
    if(!localStorage.getItem('mood-theme')){
      d.dataset.theme=e.matches?'dark':'light';
      document.getElementById('dm-btn').textContent=e.matches?'☀️':'🌙';
    }
  });
})();
function togDark(){
  const d=document.documentElement;
  const t=d.dataset.theme==='dark'?'light':'dark';
  d.dataset.theme=t;
  localStorage.setItem('mood-theme',t);
  document.getElementById('dm-btn').textContent=t==='dark'?'☀️':'🌙';
}

// === TABS ===
function swTab(t){
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('act'));
  document.querySelectorAll('.tab-c').forEach(x=>x.classList.remove('act'));
  document.querySelector('.tab[data-tab="'+t+'"]').classList.add('act');
  document.getElementById('tab-'+t).classList.add('act');
  if(t==='cal') renderCal();
  if(t==='stats') loadStats();
}

// === PICK MOOD ===
function pick(el){
  document.querySelectorAll('#moods .mb').forEach(b=>b.classList.remove('sel'));
  el.classList.add('sel'); sel=el.dataset.v;
}
function togAct(el){
  el.classList.toggle('sel');
  const t=el.textContent.trim();
  sact=sact.includes(t)?sact.filter(x=>x!==t):[...sact,t];
}

// === SAVE ===
async function save(){
  if(!sel){showSt('err','Choisis une humeur !');return}
  document.getElementById('sb').disabled=true;
  const d={mood:sel,lecture:document.getElementById('lecture').value.trim(),serie:document.getElementById('serie').value.trim(),activite:sact.join(', '),notes:document.getElementById('notes').value.trim()};
  try{
    const r=await fetch('/save',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
    const j=await r.json();
    if(j.ok){showSt('succ','✅ Enregistré !');loadToday()}
    else throw Error();
  }catch(e){showSt('err','❌ Erreur')}
  setTimeout(()=>document.getElementById('st').className='st',3000);
  document.getElementById('sb').disabled=false;
}
function showSt(cls,msg){
  const el=document.getElementById('st');
  el.className=cls; el.textContent=msg;
}

// === DELETE TODAY ===
async function delToday(){
  if(!confirm('Supprimer l\'entrée d\'aujourd\'hui ?')) return;
  try{
    const r=await fetch('/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({date:new Date().toISOString().slice(0,10)})});
    const j=await r.json();
    if(j.ok){showSt('succ','🗑️ Supprimé !');loadToday();document.getElementById('db').style.display='none'}
    else throw Error();
  }catch(e){showSt('err','❌ Erreur')}
}

// === LOAD TODAY ===
async function loadToday(){
  const r=await fetch('/data'); const d=await r.json();
  // Trend
  let h='<div class="hw">';
  for(const day of d.trend){
    const em=day.m?EM[day.m]||'—':'—';
    const bg=day.m?MC[day.m]||'#ccc':'var(--border)';
    h+='<div class="hc"><div class="hd" style="background:'+bg+'">'+em+'</div><div class="hl">'+day.d.slice(5)+'</div></div>';
  }
  h+='</div>';
  document.getElementById('trend').innerHTML=h;
  // History
  let h2='';
  for(const e of d.entries){
    const ei=EM[e.m]||'—';
    h2+='<div class="hp" onclick="openEdit(\''+e.date+'\')"><div class="d">'+e.date.slice(5)+'</div><div class="t">'+ei+' '+e.text+(e.note?'<br><span class="s">'+e.note+'</span>':'')+'</div></div>';
  }
  document.getElementById('hist').innerHTML=h2||'<div class="empty">Aucune entrée</div>';
  // Prefill today
  sel=null; sact=[];
  document.querySelectorAll('#moods .mb').forEach(b=>b.classList.remove('sel'));
  document.getElementById('lecture').value=d.today?d.today.lecture||'':'';
  document.getElementById('serie').value=d.today?d.today.serie||'':'';
  document.getElementById('notes').value=d.today?d.today.notes||'':'';
  document.querySelectorAll('#quick-act .qb').forEach(b=>b.classList.remove('sel'));
  if(d.today){
    sel=d.today.m;
    document.querySelectorAll('#moods .mb').forEach(b=>{if(b.dataset.v===d.today.m)b.classList.add('sel')});
    if(d.today.activite){
      const acts=d.today.activite.split(', ').filter(x=>x);
      sact=acts;
      document.querySelectorAll('#quick-act .qb').forEach(b=>{
        if(acts.includes(b.textContent.trim())) b.classList.add('sel');
      });
    }
    document.getElementById('db').style.display='block';
  }
}
loadToday();

// === CALENDAR ===
(function(){
  const n=new Date(); calY=n.getFullYear(); calM=n.getMonth();
})();
function calMove(d){calM+=d;if(calM>11){calM=0;calY++}if(calM<0){calM=11;calY--}renderCal()}
async function renderCal(){
  const r=await fetch('/calendar?y='+calY+'&m='+calM); const d=await r.json();
  document.getElementById('cal-title').textContent=d.month+' '+d.year;
  let h='<div class="cal-hd">L</div><div class="cal-hd">M</div><div class="cal-hd">M</div><div class="cal-hd">J</div><div class="cal-hd">V</div><div class="cal-hd">S</div><div class="cal-hd">D</div>';
  const today=new Date().toISOString().slice(0,10);
  for(let i=0;i<d.offset;i++) h+='<div class="cal-d other"></div>';
  for(const day of d.days){
    const ds=d.year+'-'+String(d.month+1).padStart(2,'0')+'-'+String(day.day).padStart(2,'0');
    let cls='cal-d';
    if(ds===today) cls+=' today';
    if(day.mood){
      const c=MC[day.mood]||'var(--border)';
      h+='<div class="'+cls+'" onclick="calDay(\''+ds+'\')" style="background:'+c+'20"><span class="mood-dot">'+EM[day.mood]+'</span></div>';
    } else {
      h+='<div class="'+cls+'" onclick="calDay(\''+ds+'\')">'+day.day+'</div>';
    }
  }
  document.getElementById('cal-grid').innerHTML=h;
  // Show first day with entry
  const withEntry=d.days.find(x=>x.mood);
  if(withEntry){
    calDay(d.year+'-'+String(d.month+1).padStart(2,'0')+'-'+String(withEntry.day).padStart(2,'0'));
  }else{
    document.getElementById('cal-day-title').textContent=d.month+' '+d.year;
    document.getElementById('cal-detail').innerHTML='<div class="empty">Aucune entrée ce mois</div>';
  }
}

async function calDay(ds){
  document.getElementById('cal-day-title').textContent=ds;
  try{
    const r=await fetch('/get-entry?date='+ds); const j=await r.json();
    if(j.found){
      const e=j.entry; const ei=EM[e.mood]||'—';
      let html='<div class="hp"><div class="e-icon">'+ei+'</div><div class="t">';
      if(e.lecture) html+='📚 '+e.lecture+'<br>';
      if(e.serie) html+='📺 '+e.serie+'<br>';
      if(e.activite) html+='🏃 '+e.activite+'<br>';
      if(e.note) html+='<span class="s">'+e.note+'</span>';
      html+='</div></div>';
      html+='<div style="margin-top:8px"><button class="export-btn" onclick="openEdit(\''+ds+'\')">✏️ Modifier</button></div>';
      document.getElementById('cal-detail').innerHTML=html;
    }else{
      document.getElementById('cal-detail').innerHTML='<div class="empty">Aucune entrée — <button class="export-btn" style="display:inline;padding:4px 10px" onclick="swTab(\'today\')">Ajouter</button></div>';
    }
  }catch(e){
    document.getElementById('cal-detail').innerHTML='<div class="empty">Erreur</div>';
  }
}

// === STATS ===
async function loadStats(){
  try{
    const r=await fetch('/stats'); const d=await r.json();
    // Summary
    let sum='<div class="stat-row">';
    sum+='<div class="stat-box"><div class="val">'+(d.avg?d.avg.toFixed(1):'—')+'</div><div class="lbl">Moyenne</div></div>';
    sum+='<div class="stat-box"><div class="val">'+d.total+'</div><div class="lbl">Entrées</div></div>';
    sum+='<div class="stat-box"><div class="val">'+(d.best||'—')+'</div><div class="lbl">Meilleur</div></div>';
    sum+='<div class="stat-box"><div class="val">'+(d.worst||'—')+'</div><div class="lbl">Pire</div></div>';
    sum+='</div><div class="stat-row">';
    sum+='<div class="stat-box"><div class="val">'+d.streak+'</div><div class="lbl">🔥 Suite jours</div></div>';
    sum+='<div class="stat-box"><div class="val">'+d.m30_avg.toFixed(1)+'</div><div class="lbl">30j moy</div></div>';
    sum+='</div>';
    document.getElementById('stats-summary').innerHTML=sum;

    // Distribution bar
    if(d.dist&&d.dist.length){
      const maxV=Math.max(...d.dist.map(x=>x.c),1);
      let bar='<div class="stat-bar">';
      for(const item of d.dist){
        const pct=Math.round(item.c/maxV*100);
        bar+='<div style="flex:'+pct+';background:'+MC[item.v]+';height:20px" title="'+item.l+': '+item.c+'"></div>';
      }
      bar+='</div>';
      let leg='<div class="stat-leg">';
      for(const item of d.dist){
        leg+='<span><span class="dot" style="background:'+MC[item.v]+'"></span>'+item.l+' ('+item.c+')</span>';
      }
      leg+='</div>';
      document.getElementById('stats-dist').innerHTML=bar+leg;
    }else{
      document.getElementById('stats-dist').innerHTML='<div class="empty">Pas assez de données</div>';
    }

    // Trend chart (simple text version)
    if(d.monthly_trend&&d.monthly_trend.length){
      let th='<div class="hw">';
      for(const m of d.monthly_trend.slice(-14)){
        const em=m.avg?EM[Math.round(m.avg)]||'—':'—';
        const bg=m.avg?MC[Math.round(m.avg)]||'var(--border)':'var(--border)';
        th+='<div class="hc"><div class="hd" style="background:'+bg+'">'+em+'</div><div class="hl">'+m.label.slice(0,5)+'</div></div>';
      }
      th+='</div>';
      document.getElementById('stats-trend').innerHTML=th;
    }else{
      document.getElementById('stats-trend').innerHTML='<div class="empty">Pas assez de données</div>';
    }
  }catch(e){
    document.getElementById('stats-summary').innerHTML='<div class="empty">Erreur de chargement</div>';
  }
}

// === EXPORT CSV ===
async function expCSV(){
  try{
    const r=await fetch('/export'); const blob=await r.blob();
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download='mood-export-'+new Date().toISOString().slice(0,10)+'.csv';
    a.click();
    URL.revokeObjectURL(a.href);
  }catch(e){alert('Erreur export')}
}

// === MODAL (editing) ===
async function openEdit(dateStr){
  editDate=dateStr;
  document.getElementById('mod-date').value=dateStr;
  document.getElementById('mod-title').textContent='✏️ '+dateStr;
  // Reset
  msel=null; msact=[];
  document.querySelectorAll('#mod-moods .mb').forEach(b=>b.classList.remove('sel'));
  document.querySelectorAll('#mod-quick .qb').forEach(b=>b.classList.remove('sel'));
  document.getElementById('mod-lecture').value='';
  document.getElementById('mod-serie').value='';
  document.getElementById('mod-notes').value='';
  document.getElementById('mod-st').className='st';

  try{
    const r=await fetch('/get-entry?date='+dateStr);
    const j=await r.json();
    if(j.found){
      const e=j.entry;
      msel=e.mood; msact=(e.activite||'').split(', ').filter(x=>x);
      document.getElementById('mod-lecture').value=e.lecture||'';
      document.getElementById('mod-serie').value=e.serie||'';
      document.getElementById('mod-notes').value=e.note||'';
      document.querySelectorAll('#mod-moods .mb').forEach(b=>{if(b.dataset.v===e.mood)b.classList.add('sel')});
      document.querySelectorAll('#mod-quick .qb').forEach(b=>{
        if(msact.includes(b.textContent.trim())) b.classList.add('sel');
      });
    }
  }catch(e){}
  document.getElementById('modal').classList.add('show');
}
function modPick(el){
  document.querySelectorAll('#mod-moods .mb').forEach(b=>b.classList.remove('sel'));
  el.classList.add('sel'); msel=el.dataset.v;
}
function modTogAct(el){
  el.classList.toggle('sel');
  const t=el.textContent.trim();
  msact=msact.includes(t)?msact.filter(x=>x!==t):[...msact,t];
}
async function modSave(){
  if(!msel){document.getElementById('mod-st').className='err';document.getElementById('mod-st').textContent='Choisis une humeur !';return}
  const d={date:editDate,mood:msel,lecture:document.getElementById('mod-lecture').value.trim(),serie:document.getElementById('mod-serie').value.trim(),activite:msact.join(', '),notes:document.getElementById('mod-notes').value.trim()};
  try{
    const r=await fetch('/update',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(d)});
    const j=await r.json();
    if(j.ok){
      document.getElementById('mod-st').className='succ';document.getElementById('mod-st').textContent='✅ Modifié !';
      closeMod(); loadToday(); renderCal();
    }else throw Error();
  }catch(e){document.getElementById('mod-st').className='err';document.getElementById('mod-st').textContent='❌ Erreur'}
}
async function modDel(){
  if(!confirm('Supprimer cette entrée ?')) return;
  try{
    const r=await fetch('/delete',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({date:editDate})});
    const j=await r.json();
    if(j.ok){closeMod(); loadToday(); renderCal();}
    else throw Error();
  }catch(e){alert('Erreur')}
}
function closeMod(){document.getElementById('modal').classList.remove('show');editDate=null}
</script>
</body></html>
"""

class Handler(BaseHTTPRequestHandler):
    def _load_entry(self, date_str):
        fpath = os.path.join(ENTRIES_DIR, f"{date_str}.json")
        if not os.path.exists(fpath): return None
        try:
            with open(fpath) as f: return json.load(f)
        except: return None

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)

        if parsed.path == '/data':
            self._handle_data()
        elif parsed.path == '/calendar':
            y = int(params.get('y', [date.today().year])[0])
            m = int(params.get('m', [date.today().month - 1])[0])
            self._handle_calendar(y, m)
        elif parsed.path == '/get-entry':
            ds = params.get('date', [''])[0]
            self._handle_get_entry(ds)
        elif parsed.path == '/stats':
            self._handle_stats()
        elif parsed.path == '/export':
            self._handle_export()
        else:
            self._html(HTML)

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        path = urllib.parse.urlparse(self.path).path

        if path == '/save':
            self._handle_save(body)
        elif path == '/delete':
            self._handle_delete(body)
        else:
            self._json({"ok": False, "error": "unknown"})

    def do_PUT(self):
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length)) if length else {}
        if urllib.parse.urlparse(self.path).path == '/update':
            self._handle_update(body)
        else:
            self._json({"ok": False})

    # ---- HANDLERS ----

    def _handle_data(self):
        entries = []
        trend = []
        today = date.today()
        today_data = None
        for i in range(6, -1, -1):
            d = today - timedelta(days=i)
            ds = d.isoformat()
            fpath = os.path.join(ENTRIES_DIR, f"{ds}.json")
            day_info = {"d": ds, "m": None}
            if os.path.exists(fpath):
                try:
                    with open(fpath) as f:
                        e = json.load(f)
                    m = e.get("mood", "")
                    day_info["m"] = int(m) if m else None
                    parts = []
                    if e.get("lecture"): parts.append("📚 " + e["lecture"])
                    if e.get("serie"): parts.append("📺 " + e["serie"])
                    if e.get("activite"): parts.append("🏃 " + e["activite"])
                    text = " — ".join(parts) if parts else ""
                    entries.append({"date": ds, "m": int(m) if m else 0, "text": text, "note": e.get("note","")})
                    if d == today:
                        today_data = {"m": int(m) if m else 0, "lecture": e.get("lecture",""), "serie": e.get("serie",""), "activite": e.get("activite",""), "notes": e.get("note","")}
                except: pass
            trend.append(day_info)
        self._json({"entries": entries[:7], "trend": trend, "today": today_data})

    def _handle_save(self, body):
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        fpath = os.path.join(ENTRIES_DIR, f"{date_str}.json")
        entry = {"date": date_str, "mood": body.get("mood",""), "mood_label": MOOD_LABELS.get(body.get("mood",""),"")}
        for k in ["lecture","serie","activite"]:
            if body.get(k): entry[k] = body[k]
        notes = body.get("notes","") or ""
        if os.path.exists(fpath):
            with open(fpath) as f:
                existing = json.load(f)
            for k in ["lecture","serie","activite"]:
                if not body.get(k) and existing.get(k): entry[k] = existing[k]
            if existing.get("note"):
                notes = existing["note"] + ("; " + notes if notes else "")
        entry["note"] = notes
        with open(fpath, "w") as f:
            json.dump(entry, f, ensure_ascii=False)
        self._json({"ok": True})

    def _handle_update(self, body):
        date_str = body.get("date", "")
        if not date_str:
            self._json({"ok": False, "error": "no date"})
            return
        fpath = os.path.join(ENTRIES_DIR, f"{date_str}.json")
        entry = {"date": date_str, "mood": body.get("mood",""), "mood_label": MOOD_LABELS.get(body.get("mood",""),"")}
        for k in ["lecture","serie","activite"]:
            if body.get(k): entry[k] = body[k]
        entry["note"] = body.get("notes","") or ""
        with open(fpath, "w") as f:
            json.dump(entry, f, ensure_ascii=False)
        self._json({"ok": True})

    def _handle_delete(self, body):
        date_str = body.get("date", "")
        fpath = os.path.join(ENTRIES_DIR, f"{date_str}.json")
        if os.path.exists(fpath):
            os.remove(fpath)
            self._json({"ok": True})
        else:
            self._json({"ok": False, "error": "not found"})

    def _handle_get_entry(self, date_str):
        e = self._load_entry(date_str)
        if e:
            self._json({"found": True, "entry": {
                "mood": e.get("mood",""), "lecture": e.get("lecture",""),
                "serie": e.get("serie",""), "activite": e.get("activite",""),
                "note": e.get("note","")
            }})
        else:
            self._json({"found": False})

    def _handle_calendar(self, y, m):
        month_names = ["Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre"]
        cal = calmod.Calendar()
        month_days = cal.monthdays2calendar(y, m + 1)
        offset = month_days[0][0][1] if month_days else 0  # weekday of first day
        days = []
        for week in month_days:
            for day_num, wd in week:
                if day_num == 0: continue
                ds = f"{y:04d}-{m+1:02d}-{day_num:02d}"
                e = self._load_entry(ds)
                days.append({"day": day_num, "wd": wd, "mood": int(e["mood"]) if e and e.get("mood") else None})
        self._json({"year": y, "month": m, "month_name": month_names[m], "offset": offset, "days": days})

    def _handle_stats(self):
        today = date.today()
        entries = []
        # Scan all files
        for fname in os.listdir(ENTRIES_DIR):
            if not fname.endswith(".json"): continue
            ds = fname[:-5]
            try:
                d = date.fromisoformat(ds)
            except: continue
            with open(os.path.join(ENTRIES_DIR, fname)) as f:
                try:
                    e = json.load(f)
                    m = e.get("mood","")
                    if m: entries.append({"date": ds, "mood": int(m), "d": d})
                except: pass
        entries.sort(key=lambda x: x["date"])

        total = len(entries)
        if total == 0:
            self._json({"total":0,"avg":None,"best":None,"worst":None,"streak":0,"m30_avg":0,"dist":[],"monthly_trend":[]})
            return

        vals = [e["mood"] for e in entries]
        avg30 = [e["mood"] for e in entries if (today - e["d"]).days <= 30]
        m30_avg = sum(avg30)/len(avg30) if avg30 else 0

        # Distribution
        dist = {}
        for v in vals:
            dist[v] = dist.get(v, 0) + 1
        dist_list = [{"v": str(k), "c": v, "l": MOOD_LABELS.get(str(k),"")} for k,v in sorted(dist.items(), key=lambda x: -x[1])]

        # Best/worst (most frequent)
        best_lbl = MOOD_LABELS.get(str(max(dist, key=dist.get)),"") if dist else "—"
        worst_lbl = MOOD_LABELS.get(str(min(dist, key=dist.get)),"") if dist else "—"

        # Streak (consecutive days)
        dates_set = set(e["date"] for e in entries)
        streak = 0
        d = today
        while d.isoformat() in dates_set:
            streak += 1
            d -= timedelta(days=1)

        # Monthly trend (last 12 months)
        monthly = {}
        for e in entries:
            ym = e["date"][:7]
            if ym not in monthly: monthly[ym] = []
            monthly[ym].append(e["mood"])
        monthly_list = []
        for ym, moods in sorted(monthly.items()):
            monthly_list.append({"label": ym, "avg": sum(moods)/len(moods)})

        avg = sum(vals)/len(vals) if vals else 0
        self._json({
            "total": total,
            "avg": round(avg, 1),
            "best": best_lbl,
            "worst": worst_lbl,
            "streak": streak,
            "m30_avg": round(m30_avg, 1),
            "dist": dist_list,
            "monthly_trend": monthly_list
        })

    def _handle_export(self):
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["date","mood","mood_label","lecture","serie","activite","note"])
        for fname in sorted(os.listdir(ENTRIES_DIR)):
            if not fname.endswith(".json"): continue
            fpath = os.path.join(ENTRIES_DIR, fname)
            try:
                with open(fpath) as f:
                    e = json.load(f)
                w.writerow([
                    e.get("date",""), e.get("mood",""), e.get("mood_label",""),
                    e.get("lecture",""), e.get("serie",""), e.get("activite",""),
                    e.get("note","")
                ])
            except: pass
        csv_data = buf.getvalue().encode("utf-8-sig")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", "attachment; filename=mood-export.csv")
        self.send_header("Content-Length", str(len(csv_data)))
        self.end_headers()
        self.wfile.write(csv_data)

    def _json(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())

    def _html(self, h):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(h.encode())

    def log_message(self, *a): pass

if __name__ == "__main__":
    PORT = 8080
    print(f"🌐 Mood Tracker v3: http://localhost:{PORT}")
    HTTPServer(("0.0.0.0", PORT), Handler).serve_forever()