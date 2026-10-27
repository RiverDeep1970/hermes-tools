(function(){
var C=document.getElementById("content");
var T=document.getElementById("tabs");
var E=document.getElementById("edition");
var tabNames=["une","newsletters","youtube","echecs","techno","crypto","immobilier","agenda","reddit"];
var tabLabels=["A la une","Newsletters","YouTube","Échecs","Techno","Crypto","Immo","Agenda","Reddit"];
var readItems={};
var currentTab="une";
/* Vue Agenda (liste par defaut, semaine memorisee) */
var agendaView="liste";
try{var _av=window.localStorage.getItem("journalAgendaView");if(_av==="semaine"||_av==="liste")agendaView=_av}catch(e){}
var AGENDA_ITEMS=null;
var weekStart=null;
var weekDayIndex=0;
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
    if(n==="une"){count=section.length}else if(n==="agenda"){count=section.length}else if(n==="newsletters"){count=newsletterArticleCount(section)}else if(n==="reddit"){count=redditGroupCount(section)}else if(n==="crypto"){count=cryptoCount(section)}else{count=typeof section != "undefined" && section !== null && section.length ? section.length : 0}
    th+='<div class="tab'+(n===currentTab?" active":"")+'" data-tab="'+n+'">'+l+'<span class="badge'+(count>0?" show":"")+'">'+count+'</span></div>';
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
    html+='<div class="pane'+(n===currentTab?" active":"")+'" id="pane-'+n+'">';
    if(n==="une"){html+=renderUne(data.sections[n]||[])}
    else if(n==="newsletters"){html+=renderNewsletter(data.sections[n]||[])}
    else if(n==="agenda"){html+=renderAgenda(data.sections[n]||[])}
    else if(n==="immobilier"){html+=renderImmo(data.sections[n]||[])}
    else if(n==="reddit"){html+=renderReddit(data.sections[n]||[])}
    else if(n==="crypto"){html+=renderCrypto(data.sections[n])}
    else{html+=renderList(data.sections[n]||[],n)}
    html+='</div>';
  }
  C.innerHTML=html;
  buildTicker(data);
  updateStickyTop();
  
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
    if(it.type==="event-sport"){typeLabel="\u26BD Sport"}
    else if(it.type==="event-personal"){typeLabel="\uD83D\uDCC5 Agenda"}
    else if(it.type==="marquante"){typeLabel="\uD83D\uDCA1 Marquante"}
    else if(it.type==="video"){typeLabel="\uD83C\uDFAC Vid\u00E9o"}
    else if(it.type==="article"){typeLabel="\uD83D\uDCF0 Article"}
    else if(it.type==="post"){typeLabel="\uD83D\uDCAC Reddit"}
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

/* ===== Onglet Reddit — rendu dedie (regroupe par subreddit) ===== */

function redditSub(it){
  var s=(it&&it.subreddit)?it.subreddit:"";
  if(!s&&it&&it.source)s=String(it.source).replace(/^r\//,"");
  return s||"reddit";
}

function rdChip(cls,txt){
  return '<span class="rd-chip rd-chip--'+cls+'">'+txt+'</span>';
}

function rdGroupHead(name,count,href){
  var url=href||("https://www.reddit.com/r/"+encodeURIComponent(name));
  return '<a class="rd-group__hd" href="'+esc(url)+'" target="_blank" rel="noopener">r/'+esc(name)+'<span class="rd-group__count">'+count+'</span></a>';
}

function rdPost(it){
  var itemId=it.url||it.title||"rd";
  var isRead=readItems[itemId];
  var h='<div class="art rd-post'+(isRead?"":" unread")+'">';
  h+='<h3>'+(it.url?'<a href="'+esc(it.url)+'" target="_blank" rel="noopener">':'')+esc(it.title)+(it.url?'</a>':'')+'</h3>';
  var score=Number(it.score||0);
  var com=Number(it.comments||0);
  var rang=Number(it.rang||0);
  h+='<div class="rd-meta">';
  if(rang>0&&rang<9999)h+=rdChip("rang","#"+rang);
  if(score>0)h+=rdChip("score","\u25B2 "+score);
  if(com>0)h+=rdChip("com","\uD83D\uDCAC "+com);
  if(it.author)h+='<span class="rd-author">'+esc(it.author)+'</span>';
  if(it.date)h+='<span class="rd-date">'+esc(it.date)+'</span>';
  h+='</div>';
  if(it.summary)h+='<details class="rd-sum"><summary>Extrait</summary><p class="rd-sum__txt">'+esc(it.summary)+'</p></details>';
  h+='</div>';
  return h;
}

/* Un fil du rapport : titre cliquable, score/commentaires/auteur, « pourquoi ». */
function rdFil(p){
  var h='<div class="art rd-fil">';
  h+='<h3>'+(p.url?'<a href="'+esc(p.url)+'" target="_blank" rel="noopener">':'')+esc(p.title)+(p.url?'</a>':'')+'</h3>';
  var score=Number(p.score||0);
  var com=Number(p.comments||0);
  h+='<div class="rd-meta">';
  if(score>0)h+=rdChip("score","\u25B2 "+score);
  if(com>0)h+=rdChip("com","\uD83D\uDCAC "+com);
  if(p.author)h+='<span class="rd-author">'+esc(p.author)+'</span>';
  h+='</div>';
  if(p.pourquoi)h+='<p class="rd-pourquoi">'+esc(p.pourquoi)+'</p>';
  h+='</div>';
  return h;
}

/* Rendu du rapport d'un subreddit : en-tete + synthese FR + points + fils. */
function rdSynthese(it){
  var name=redditSub(it);
  var posts=it.posts||[];
  var h='<div class="rd-group rd-group--synth">';
  h+=rdGroupHead(name,posts.length,it.url);
  if(it.date||it.posts_24h!=null){
    h+='<div class="rd-synth__meta">';
    if(it.date)h+='<span class="rd-date">'+esc(it.date)+'</span>';
    if(it.posts_24h!=null)h+='<span class="rd-synth__24h">'+Number(it.posts_24h)+' posts / 24 h</span>';
    h+='</div>';
  }
  if(it.synthese)h+='<p class="rd-synth__txt">'+esc(it.synthese)+'</p>';
  if(it.points&&it.points.length){
    h+='<div class="rd-points"><div class="rd-points__hd">Points cles</div><ul class="rd-points__list">';
    for(var i=0;i<it.points.length;i++){h+='<li>'+esc(it.points[i])+'</li>'}
    h+='</ul></div>';
  }
  if(posts.length){
    h+='<div class="rd-fils"><div class="rd-fils__hd">Fils</div>';
    for(var j=0;j<posts.length;j++){h+=rdFil(posts[j])}
    h+='</div>';
  }
  h+='</div>';
  return h;
}

/* Choisit l'item « synthese » le plus complet d'un groupe (le producteur
   enrichit url/posts_24h ; l'analyse brute, chargee par le compilateur, ne
   les a pas). Evite d'afficher une version appauvrie quand les deux existent. */
function meilleureSynthese(list){
  var best=null,bestScore=-1;
  for(var i=0;i<list.length;i++){
    var it=list[i];
    if(!it||it.type!=="synthese")continue;
    var sc=0;
    if(it.url)sc+=2;
    if(it.posts_24h!=null)sc+=1;
    if(it.synthese)sc+=1;
    if(sc>bestScore){bestScore=sc;best=it}
  }
  return best;
}

/* Nombre de subreddits distincts : le compilateur peut charger plusieurs
   fichiers (analyse brute + fichier fusionne) pour un meme subreddit ; le
   badge de l'onglet compte donc les groupes reellement affiches. */
function redditGroupCount(items){
  if(!items||!items.length)return 0;
  var vus={},n=0;
  for(var i=0;i<items.length;i++){
    var s=redditSub(items[i]);
    if(!vus[s]){vus[s]=1;n++}
  }
  return n;
}

function renderReddit(items){
  if(!items||!items.length)return '<div style="padding:20px;text-align:center;color:#888">Aucun post Reddit</div>';
  var order=[];
  var groups={};
  for(var i=0;i<items.length;i++){
    var sub=redditSub(items[i]);
    if(!groups[sub]){groups[sub]=[];order.push(sub)}
    groups[sub].push(items[i]);
  }
  var h="";
  for(var g=0;g<order.length;g++){
    var name=order[g];
    var list=groups[name];
    var synth=meilleureSynthese(list);
    if(synth){h+=rdSynthese(synth);continue}
    h+='<div class="rd-group">';
    h+=rdGroupHead(name,list.length);
    for(var j=0;j<list.length;j++){h+=rdPost(list[j])}
    h+='</div>';
  }
  return h;
}

function syncAgendaBodyClass(){
  var cls=(document.body.className||"").replace(/\s*agenda-week/g,"");
  if(agendaView==="semaine")cls+=" agenda-week";
  document.body.className=cls.replace(/^\s+/,"");
}

function renderAgenda(items){
  AGENDA_ITEMS=items;
  syncAgendaBodyClass();
  if(!items||!items.length)return '<div style="padding:20px;text-align:center;color:#888">Aucun evenement</div>';
  var now=new Date();
  var list=[];
  for(var i=0;i<items.length;i++){
    var it=items[i];
    list.push({title:it.title,date:it.date,time:it.time||"",calendar:it.calendar||"Agenda",type:it.type||"personal",_dt:parseDate(it.date),_fam:classifyItem(it)});
  }
  list.sort(function(a,b){
    var da=a._dt?a._dt.getTime():8640000000000000;
    var db=b._dt?b._dt.getTime():8640000000000000;
    if(da!==db)return da-db;
    var ta=a.time||"99:99",tb=b.time||"99:99";
    return ta<tb?-1:(ta>tb?1:0);
  });
  var h="";
  h+=renderViewToggle();
  h+=renderNextEv(list,now);
  h+=renderLegende();
  if(agendaView==="semaine"){
    h+=renderWeek(list,now);
  }else{
    h+=renderAgendaList(list,now);
  }
  return h;
}

function renderAgendaList(list,now){
  var h="";
  var groups=[
    {label:"Aujourd'hui",test:function(d){return d===0}},
    {label:"Demain",test:function(d){return d===1}},
    {label:"Cette semaine",test:function(d){return d>=2&&d<=7}},
    {label:"Plus tard",test:function(d){return d>7}}
  ];
  for(var g=0;g<groups.length;g++){
    var gItems=[];
    for(var j=0;j<list.length;j++){
      var gi=groupIndex(groups,diffDays(now,list[j]._dt));
      if(gi===g)gItems.push(list[j]);
    }
    if(!gItems.length)continue;
    h+='<div class="ev-section">'+groups[g].label+'</div>';
    var lastKey=null;
    for(var m=0;m<gItems.length;m++){
      var itm=gItems[m];
      var key=itm._dt?dayKey(itm._dt):"0000-00-00";
      if(key!==lastKey){
        var cnt=0;
        for(var n=0;n<gItems.length;n++){
          var kk=gItems[n]._dt?dayKey(gItems[n]._dt):"0000-00-00";
          if(kk===key)cnt++;
        }
        var lbl=itm._dt?humanDate(itm._dt):itm.date;
        h+='<div class="day-hd" id="day-'+key+'"><span class="day-hd__label">'+lbl+'</span><span class="day-hd__count">'+cnt+'</span></div>';
        lastKey=key;
      }
      h+=evCard(itm,now);
    }
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
      if(it.surface)h+=it.surface+' m\u00B2 ';
      if(it.rooms)h+=it.rooms+' pi\u00E8ces ';
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

function renderNewsletter(items){
  if(!items||!items.length)return '<div style="padding:20px;text-align:center;color:#888">Aucune newsletter</div>';
  var h="";
  for(var i=0;i<items.length;i++){
    var nl=items[i]||{};
    var src=nl.source||"Newsletter";
    var date=nl.date||"";
    var arts=nl.articles||[];
    for(var a=0;a<arts.length;a++){
      var art=arts[a]||{};
      var itemId=art.url||art.title||("nl-"+i+"-"+a);
      var isRead=readItems[itemId];
      h+='<div class="art'+(isRead?"":" unread")+'">';
      h+='<div class="src">'+esc(src)+' <span class="tag tag-newsletter">Newsletter</span></div>';
      h+='<h3>'+(art.url?'<a href="'+esc(art.url)+'" target="_blank">':'')+esc(art.title||"")+(art.url?'</a>':'')+'</h3>';
      if(art.summary)h+='<p>'+esc(art.summary)+'</p>';
      h+='<div class="meta">'+esc(date)+'</div>';
      h+='</div>';
    }
  }
  return h;
}

function newsletterArticleCount(section){
  var total=0;
  if(!section||!section.length)return 0;
  for(var i=0;i<section.length;i++){
    var arts=section[i]&&section[i].articles;
    total+=arts?arts.length:0;
  }
  return total;
}

/* ===== Onglet Crypto — rendu dedie (watchlist + mouvements du jour) ===== */

function cryptoCount(sec){
  if(!sec)return 0;
  var n=0;
  if(sec.watchlist&&sec.watchlist.length)n+=sec.watchlist.length;
  if(sec.others&&sec.others.length)n+=sec.others.length;
  return n;
}

function cryptPrice(p){
  if(p===null||p===undefined||isNaN(p))return "n/d";
  p=Number(p);
  if(p>=1000)return "$"+Math.round(p).toString().replace(/\B(?=(\d{3})+(?!\d))/g," ");
  if(p>=1)return "$"+p.toFixed(2);
  if(p>=0.01)return "$"+p.toFixed(4);
  return "$"+p.toFixed(6);
}

function cryptAge(iso){
  var t=null;
  if(iso){
    var m=String(iso).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
    if(m)t=new Date(parseInt(m[1],10),parseInt(m[2],10)-1,parseInt(m[3],10),parseInt(m[4],10),parseInt(m[5],10));
    else t=parseDate(String(iso).substring(0,10));
  }
  if(!t||isNaN(t.getTime()))return {txt:"date inconnue",stale:true};
  var mins=Math.floor((new Date().getTime()-t.getTime())/60000);
  if(mins<0)mins=0;
  var txt;
  if(mins<2)txt="a l'instant";
  else if(mins<60)txt="il y a "+mins+" min";
  else if(mins<1440)txt="il y a "+Math.floor(mins/60)+" h";
  else txt="il y a "+Math.floor(mins/1440)+" j";
  return {txt:txt,stale:mins>1440};
}

function cryptSpark(arr,w,h){
  if(!arr||arr.length<2)return "";
  var mn=arr[0],mx=arr[0],i;
  for(i=1;i<arr.length;i++){if(arr[i]<mn)mn=arr[i];if(arr[i]>mx)mx=arr[i]}
  var rng=(mx-mn)||1;
  var pts="";
  for(i=0;i<arr.length;i++){
    var x=(i/(arr.length-1))*w;
    var y=h-((arr[i]-mn)/rng)*h;
    pts+=(i?" ":"")+x.toFixed(1)+","+y.toFixed(1);
  }
  return '<svg class="cspark" viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="none" aria-hidden="true"><polyline vector-effect="non-scaling-stroke" points="'+pts+'"/></svg>';
}

function cryptDelta(label,v){
  if(v===null||v===undefined||isNaN(v))return '<span class="cdelta cdelta--na">'+esc(label)+' n/d</span>';
  v=Number(v);
  return '<span class="cdelta cdelta--'+(v>=0?"up":"down")+'">'+esc(label)+' '+(v>=0?"+":"")+v.toFixed(2)+'%</span>';
}

function cryptCard(c,lbl7){
  var h='<div class="ccard">';
  h+='<div class="ccard__hd"><span class="ccard__sym">'+esc(c.symbol)+'</span><span class="ccard__pr">'+cryptPrice(c.price)+'</span></div>';
  h+='<div class="ccard__deltas">'+cryptDelta("24 h",c.change_24h)+cryptDelta(lbl7,c.change_7d)+'</div>';
  if(c.spark&&c.spark.length>1)h+='<div class="ccard__spark">'+cryptSpark(c.spark,80,26)+'</div>';
  else h+='<div class="ccard__spark ccard__spark--empty">Courbe bientot disponible</div>';
  h+='</div>';
  return h;
}

function cryptMover(m,dir){
  var ch=(m.change_24h===null||m.change_24h===undefined)?0:m.change_24h;
  return '<span class="cmover cmover--'+dir+'">'+(dir==="up"?"▲":"▼")+' '+esc(m.symbol)+' '+(ch>=0?"+":"")+ch.toFixed(2)+'%</span>';
}

function cryptRow(c){
  var ch=(c.change_24h===null||c.change_24h===undefined)?0:c.change_24h;
  return '<div class="crow"><span class="crow__sym">'+esc(c.symbol)+'</span><span class="crow__pr">'+cryptPrice(c.price)+'</span><span class="crow__ch '+(ch>=0?"up":"down")+'">'+(ch>=0?"+":"")+ch.toFixed(2)+'%</span></div>';
}

function renderCrypto(sec){
  if(!sec||(!sec.watchlist&&!sec.others))return '<div class="crypto-empty">Donnees crypto indisponibles</div>';
  var h="";
  var age=cryptAge(sec.updated);
  h+='<div class="crypto-upd'+(age.stale?" stale":"")+'">Releve '+esc(age.txt)+(age.stale?" — donnees possiblement obsoletes":"")+'</div>';
  var wl=sec.watchlist||[];
  var lbl7=(sec.history_days&&sec.history_days>=7)?"7 j":"depuis le debut";
  if(wl.length){
    h+='<div class="crypto-cards">';
    for(var i=0;i<wl.length;i++){h+=cryptCard(wl[i],lbl7)}
    h+='</div>';
  }
  var mv=sec.movers||{},up=mv.up||[],down=mv.down||[];
  if(up.length||down.length){
    h+='<h2 class="crypto-h">Mouvements du jour</h2><div class="crypto-movers">';
    for(var u=0;u<up.length;u++){h+=cryptMover(up[u],"up")}
    for(var d=0;d<down.length;d++){h+=cryptMover(down[d],"down")}
    h+='</div>';
  }
  var ot=sec.others||[];
  if(ot.length){
    h+='<h2 class="crypto-h">Autres cryptos</h2><div class="crypto-list">';
    for(var k=0;k<ot.length;k++){h+=cryptRow(ot[k])}
    h+='</div>';
  }
  if(sec.history_days!==undefined&&sec.history_days<7){
    h+='<div class="crypto-note">Historique : '+sec.history_days+' jour(s) de donnees — les courbes se construisent au fil des jours.</div>';
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
  currentTab=tabName;
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

/* ===== Agenda — pack visuel (etape B) ===== */

var JOURS=["dimanche","lundi","mardi","mercredi","jeudi","vendredi","samedi"];
var MOIS=["janvier","fevrier","mars","avril","mai","juin","juillet","aout","septembre","octobre","novembre","decembre"];

var ICONS={
  sport:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 2a15.3 15.3 0 0 0 0 20M2 12h20M12 2a15.3 15.3 0 0 1 0 20"/></svg>',
  serie:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 7l2-3h14l2 3M3 7v12a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V7M3 7h18M10 11l5 3-5 3z"/></svg>',
  jeu:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="7" width="20" height="11" rx="4"/><path d="M7 12h3M8.5 10.5v3M15.5 11.5h.01M17.5 13.5h.01"/></svg>',
  personal:'<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 3h12a1 1 0 0 1 1 1v17l-7-4-7 4V4a1 1 0 0 1 1-1z"/></svg>'
};

function pad2(n){return n<10?"0"+n:""+n}

function parseDate(str){
  var p=(str||"").split("-");
  if(p.length!==3)return null;
  var y=parseInt(p[0],10),m=parseInt(p[1],10),d=parseInt(p[2],10);
  if(isNaN(y)||isNaN(m)||isNaN(d))return null;
  return new Date(y,m-1,d);
}

function dayKey(dt){return dt.getFullYear()+"-"+pad2(dt.getMonth()+1)+"-"+pad2(dt.getDate())}

function startOfDay(dt){return new Date(dt.getFullYear(),dt.getMonth(),dt.getDate())}

function diffDays(a,b){
  if(!a||!b)return NaN;
  return Math.round((startOfDay(b)-startOfDay(a))/86400000);
}

function humanDate(dt){return JOURS[dt.getDay()]+" "+dt.getDate()+" "+MOIS[dt.getMonth()]}

function classifyItem(it){
  var t=(it&&it.title)?it.title:"";
  var low=t.toLowerCase();
  if(low.indexOf("ps5")>=0||low.indexOf("switch")>=0||low.indexOf("nintendo")>=0||low.indexOf("xbox")>=0||low.indexOf("pc (")>=0||low.indexOf("(ps5")>=0)return "jeu";
  if(low.indexOf("netflix")>=0||low.indexOf("disney+")>=0||low.indexOf("apple tv+")>=0||low.indexOf("hbo")>=0||low.indexOf("prime video")>=0||low.indexOf("canal+")>=0||low.indexOf("paramount+")>=0||/\bs\d+\b/i.test(t)||/s\d+ ?e\d+/i.test(t))return "serie";
  if(it&&it.type==="sport")return "sport";
  return "personal";
}

function groupIndex(groups,d){
  for(var i=0;i<groups.length;i++){if(groups[i].test(d))return i}
  return 0;
}

function countdownText(it,now){
  var dt=parseDate(it.date);
  if(!dt)return "";
  var delta=diffDays(now,dt);
  var time=it.time||"";
  if(delta===0)return time?"aujourd'hui \u00E0 "+time:"aujourd'hui";
  if(delta===1)return time?"demain \u00E0 "+time:"demain";
  if(delta>1&&delta<=7)return "dans "+delta+" jours";
  if(delta>7&&delta<=30){
    var w=Math.round(delta/7);
    return "dans "+w+(w>1?" semaines":" semaine");
  }
  if(delta>30){
    var mo=Math.round(delta/30);
    return "dans "+mo+" mois";
  }
  return "";
}

function esc(s){
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function evCard(it,now){
  var fam=it._fam;
  var isToday=it._dt&&diffDays(now,it._dt)===0;
  var cd=countdownText(it,now);
  var h='<div class="ev ev--'+fam+(isToday?" ev--today":"")+'" data-cal="'+esc(it.calendar)+'" data-date="'+esc(it.date)+'" data-type="'+esc(it.type)+'">';
  h+='<span class="ev__bar"></span>';
  h+='<div class="ev__main">';
  h+='<div class="ev__top"><span class="ev__icon">'+ICONS[fam]+'</span><span class="ev__title">'+esc(it.title)+'</span></div>';
  h+='<div class="ev__meta">';
  h+='<span class="ev__cal">'+esc(it.calendar)+'</span>';
  if(it.time)h+='<span class="ev__time">'+esc(it.time)+'</span>';
  if(cd)h+='<span class="ev__countdown">'+cd+'</span>';
  h+='</div></div></div>';
  return h;
}

function renderNextEv(list,now){
  var next=null;
  for(var i=0;i<list.length;i++){
    var dt=list[i]._dt;
    if(!dt)continue;
    if(diffDays(now,dt)<0)continue;
    next=list[i];
    break;
  }
  if(!next)return "";
  var dt=next._dt;
  var cd=countdownText(next,now);
  var h='<div class="next-ev">';
  h+='<div class="next-ev__label">Prochain evenement</div>';
  h+='<div class="next-ev__title">'+esc(next.title)+'</div>';
  h+='<div class="next-ev__meta">';
  h+='<span class="ev__cal">'+esc(next.calendar)+'</span>';
  if(dt)h+='<span>'+humanDate(dt)+'</span>';
  if(next.time)h+='<span class="ev__time">'+esc(next.time)+'</span>';
  if(cd)h+='<span class="next-ev__countdown">'+cd+'</span>';
  h+='</div></div>';
  return h;
}

function renderLegende(){
  return '<div class="legende">'
    +'<span class="legende__item"><span class="legende__dot legende__dot--sport"></span>Sport</span>'
    +'<span class="legende__item"><span class="legende__dot legende__dot--serie"></span>S\u00E9ries</span>'
    +'<span class="legende__item"><span class="legende__dot legende__dot--jeu"></span>Jeux</span>'
    +'<span class="legende__item"><span class="legende__dot legende__dot--personal"></span>Divers</span>'
    +'</div>';
}

function updateStickyTop(){
  var hd=document.querySelector(".hd");
  var tabs=document.querySelector(".tabs");
  var ticker=document.querySelector(".ticker-wrap");
  var top=0;
  if(hd)top+=hd.offsetHeight;
  if(tabs)top+=tabs.offsetHeight;
  if(ticker)top+=ticker.offsetHeight;
  document.documentElement.style.setProperty("--sticky-top",top+"px");
}
if(window.addEventListener){window.addEventListener("resize",updateStickyTop)}

/* ===== Agenda — vue Semaine (etape C) ===== */

var DOW_SHORT=["lun","mar","mer","jeu","ven","sam","dim"];

function isMobile(){var w=window.innerWidth||document.documentElement.clientWidth||0;return w<700}

function mondayOf(dt){
  var d=startOfDay(dt);
  var off=(d.getDay()+6)%7;
  return new Date(d.getFullYear(),d.getMonth(),d.getDate()-off);
}

function weekDays(start){
  var arr=[];
  for(var i=0;i<7;i++){arr.push(new Date(start.getFullYear(),start.getMonth(),start.getDate()+i))}
  return arr;
}

function ensureWeekInit(now){
  if(!weekStart){
    weekStart=mondayOf(now);
    var t=startOfDay(now);
    var diff=Math.round((t.getTime()-weekStart.getTime())/86400000);
    weekDayIndex=(diff>=0&&diff<7)?diff:0;
  }
}

function weekNavLabel(){
  if(isMobile()){
    var d=weekDays(weekStart)[weekDayIndex];
    return JOURS[d.getDay()]+" "+d.getDate()+" "+MOIS[d.getMonth()];
  }
  var dd=weekDays(weekStart);
  var a=dd[0],b=dd[6];
  return a.getDate()+" "+MOIS[a.getMonth()]+" \u2013 "+b.getDate()+" "+MOIS[b.getMonth()]+" "+b.getFullYear();
}

function renderViewToggle(){
  return '<div class="view-toggle" id="view-toggle">'
    +'<button type="button" class="view-toggle__btn'+(agendaView==="liste"?" active":"")+'" data-view="liste">Liste</button>'
    +'<button type="button" class="view-toggle__btn'+(agendaView==="semaine"?" active":"")+'" data-view="semaine">Semaine</button>'
    +'</div>';
}

function weekCard(it,now){
  var fam=it._fam;
  var isToday=it._dt&&diffDays(now,it._dt)===0;
  var h='<div class="ev ev--'+fam+(isToday?" ev--today":"")+'" data-cal="'+esc(it.calendar)+'" data-date="'+esc(it.date)+'" data-type="'+esc(it.type)+'">';
  h+='<span class="ev__bar"></span>';
  h+='<div class="ev__main">';
  h+='<div class="ev__top"><span class="ev__icon">'+ICONS[fam]+'</span><span class="ev__title">'+esc(it.title)+'</span></div>';
  h+='<div class="ev__meta">';
  if(it.time)h+='<span class="ev__time">'+esc(it.time)+'</span>';
  h+='<span class="ev__cal">'+esc(it.calendar)+'</span>';
  h+='</div></div></div>';
  return h;
}

function renderWeekCell(list,d,now){
  var k=dayKey(d);
  var timed=[],untimed=[];
  for(var i=0;i<list.length;i++){
    var it=list[i];
    if(!it._dt)continue;
    if(dayKey(it._dt)!==k)continue;
    if(it.time)timed.push(it);else untimed.push(it);
  }
  timed.sort(function(a,b){return a.time<b.time?-1:(a.time>b.time?1:0)});
  var h='<div class="week-cell">';
  if(!timed.length&&!untimed.length){h+='<div class="week-empty">Rien de pr\u00E9vu</div>';return h+'</div>'}
  for(var t=0;t<timed.length;t++){h+=weekCard(timed[t],now)}
  if(untimed.length){
    h+='<div class="week-cell__allday">Journ\u00E9e</div>';
    for(var u=0;u<untimed.length;u++){h+=weekCard(untimed[u],now)}
  }
  return h+'</div>';
}

function renderWeek(list,now){
  ensureWeekInit(now);
  var days=weekDays(weekStart);
  var todayKey=dayKey(now);
  var mob=isMobile();
  var h='<div class="week">';
  h+='<div class="week-nav">';
  h+='<button type="button" class="week-nav__btn" data-wk="prev" aria-label="Precedent">\u2039</button>';
  h+='<span class="week-nav__label" id="week-label">'+weekNavLabel()+'</span>';
  h+='<button type="button" class="week-nav__btn" data-wk="next" aria-label="Suivant">\u203A</button>';
  h+='</div>';
  h+='<div class="week-grid" id="week-grid" data-day-index="'+weekDayIndex+'" data-week-start="'+dayKey(weekStart)+'">';
  for(var i=0;i<7;i++){
    var d=days[i];
    var k=dayKey(d);
    var cls="week-col";
    if(mob){cls+=(i===weekDayIndex?" week-col--active":" week-col--hidden")}
    h+='<div class="'+cls+'" data-day="'+k+'" data-idx="'+i+'">';
    h+='<div class="week-col__hd'+(k===todayKey?" week-col__hd--today":"")+'"><span class="week-col__dow">'+DOW_SHORT[i]+'</span><span class="week-col__num">'+d.getDate()+'</span></div>';
    h+=renderWeekCell(list,d,now);
    h+='</div>';
  }
  h+='</div>';
  h+='</div>';
  return h;
}

function setAgendaView(v){
  if(v!=="liste"&&v!=="semaine")return;
  agendaView=v;
  try{window.localStorage.setItem("journalAgendaView",v)}catch(e){}
  rerenderAgenda();
}

function navigateWeek(dir){
  if(!weekStart)ensureWeekInit(new Date());
  if(isMobile()){
    weekDayIndex+=dir;
    if(weekDayIndex<0){weekDayIndex=6;weekStart=new Date(weekStart.getFullYear(),weekStart.getMonth(),weekStart.getDate()-7)}
    else if(weekDayIndex>6){weekDayIndex=0;weekStart=new Date(weekStart.getFullYear(),weekStart.getMonth(),weekStart.getDate()+7)}
  }else{
    weekStart=new Date(weekStart.getFullYear(),weekStart.getMonth(),weekStart.getDate()+dir*7);
  }
  rerenderAgenda();
}

function rerenderAgenda(){
  var pane=document.getElementById("pane-agenda");
  if(!pane)return;
  if(AGENDA_ITEMS)pane.innerHTML=renderAgenda(AGENDA_ITEMS);
  updateStickyTop();
}

C.addEventListener("click",function(e){
  var t=e.target;
  while(t&&t!==C){
    if(t.getAttribute){
      var v=t.getAttribute("data-view");
      if(v){setAgendaView(v);return}
      var w=t.getAttribute("data-wk");
      if(w){navigateWeek(w==="prev"?-1:1);return}
    }
    t=t.parentNode;
  }
},false);

var _touchX=null;
document.addEventListener("touchstart",function(e){
  if(e.touches&&e.touches.length){_touchX=e.touches[0].clientX}
},false);
document.addEventListener("touchend",function(e){
  if(_touchX===null)return;
  var endX=null;
  if(e.changedTouches&&e.changedTouches.length){endX=e.changedTouches[0].clientX}
  var sx=_touchX;_touchX=null;
  if(endX===null)return;
  if(agendaView!=="semaine"||!isMobile())return;
  var dx=endX-sx;
  if(dx<=-40){navigateWeek(1)}
  else if(dx>=40){navigateWeek(-1)}
},false);

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
