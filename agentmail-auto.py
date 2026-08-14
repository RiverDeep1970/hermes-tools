#!/usr/bin/env python3
"""AgentMail - détection, résumé et envoi automatique des newsletters."""
import json, urllib.request, urllib.error, urllib.parse, os, re, sys, base64
from datetime import datetime

BASE = "https://api.agentmail.to/v0"
INBOX = "alexis-bot@agentmail.to"
PROCESSED = os.path.expanduser("~/.hermes/agentmail-processed.txt")

def key():
    t = os.environ.get("AGENTMAIL_API_KEY")
    if t: return t
    with open(os.path.expanduser("~/.hermes/config.yaml")) as f:
        m = re.search(r'AGENTMAIL_API_KEY:\s*([^\s]+)', f.read())
    return m.group(1).strip('"') if m else None

def tgtoken():
    t = os.environ.get("TELEGRAM_BOT_TOKEN")
    if t: return t
    try:
        with open(os.path.expanduser("~/.hermes/.env")) as f:
            for line in f:
                line = line.strip()
                if "TELEGRAM_BOT_TOKEN=" in line and not line.startswith("#"):
                    val = line.split("=", 1)[1]
                    for q in ["'", '"']:
                        if val.startswith(q) and val.endswith(q): val = val[1:-1]
                    return val
    except: pass
    return None

def saved():
    if not os.path.exists(PROCESSED): return set()
    with open(PROCESSED) as f: return set(l.strip() for l in f if l.strip())

def mark(mid):
    with open(PROCESSED, "a") as f: f.write(f"{mid}\n")

def api(method, path, data=None):
    k = key()
    h = {"Authorization": f"Bearer {k}", "Content-Type": "application/json"}
    b = json.dumps(data).encode() if data else None
    r = urllib.request.Request(f"{BASE}{path}", data=b, headers=h, method=method)
    try:
        resp = urllib.request.urlopen(r)
        body = resp.read()
        return json.loads(body) if body else {"ok": True}
    except urllib.error.HTTPError as e:
        return {"e": e.code, "b": e.read().decode()}

def tg(msg):
    t = tgtoken()
    if not t: return
    d = json.dumps({"chat_id": "8126578200", "text": msg}).encode()
    try: urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{t}/sendMessage", data=d, headers={"Content-Type":"application/json"}))
    except: pass

def trash_thread(thread_id):
    """Move thread to trash."""
    result = api("DELETE", f"/inboxes/{INBOX}/threads/{thread_id}")
    if "e" not in result:
        return True
    return False

def ack(mail, subj):
    """Send generic acknowledgment."""
    api("POST", f"/inboxes/{INBOX}/messages/send", {
        "to": [mail], "subject": f"Re: {subj[:80]}",
        "text": f"Bonjour,\n\nJ'ai bien reçu votre message.\n\nCordialement,\nAlexis Bot"
    })

def is_nl(subj, txt):
    s = (subj + " " + (txt or "")[:200]).lower()
    for k in ["newsletter","digest","daily","quotidien","hebdo","fw:","fwd:","transfere","bdm","reporterre","tao daily","journal du coin"]:
        if k in s: return True
    return False

def is_known_sender(from_addr):
    """Check if it's a known newsletter sender (direct subscription)."""
    fr = from_addr.lower()
    for s in ["newsletter@blogdumoderateur.com", "contact@journalducoin.com", "contact@m.journalducoin.com",
              "planete@reporterre.net", "mail@motionwebbuilder.com"]:
        if s in fr: return True
    return False

def extract_articles(text, source):
    """Extract article titles, descriptions and URLs from newsletter text."""
    articles = []
    seen = set()

    # ── TAO format: [UPPERCASE TITLE] then [URL] then description ──
    tao_pat = re.compile(
        r'\n([A-Z0-9][A-Z0-9 ,:’\'\-]{20,140})\n\[?(https?://taodaily\.io/[^\])\s]+)\]?\n([^\[]\S[^\n]{20,400})',
        re.IGNORECASE
    )
    import urllib.parse as _up
    for title, url, desc in tao_pat.findall(text):
        if title.strip() in seen or len(seen) >= 8: continue
        # Ignorer les lignes footer/pied de page
        low = title.lower()
        if any(x in low for x in ["you're receiving", "because you subscribed", "unsubscribe", "follow us", "share", "view this"]):
            continue
        # Extraire l'URL réelle d'article depuis le paramètre url=
        real_url = url
        if "url=" in url:
            try:
                real_url = _up.parse_qs(_up.urlparse(url).query).get("url", [url])[0]
            except: pass
        seen.add(title.strip())
        articles.append((title.strip(), desc.strip()[:300], real_url, source))

    # ── BDM format: blocks separated by tracking URLs ──
    if not articles and ("blogdumoderateur" in text.lower() or "go.blogdumoderateur" in text.lower()):
        raw_lines = text.split("\n")
        # Ignorer tout ce qui précède "Message transféré" (le forward d'en-tête)
        start = 0
        for i, l in enumerate(raw_lines):
            if "message transféré" in l.lower() or "message transfer" in l.lower():
                start = i
                break

        seg_lines = raw_lines[start:]
        # Détecter les lignes qui contiennent du contenu tab-indenté
        # (le forward préfixe d'un espace : ' \t\t')
        comp = []
        for l in seg_lines:
            # Une ligne de composant BDM contient \t\t (après espaces)
            if "\t\t" in l:
                comp.append(l)

        cats = ["OpenAI","Anthropic","Guide du moment","Vidéo","Interviews","News",
                "Actualité","BDM","Sommaire","Community management","E-commerce","Futur"]

        # Reconstruire titre + description : chaque composant est titre ou description
        # D'après structure: titre(tab) puis description(tab). Categories aussi (tab)
        comp_clean = []
        for c in comp:
            t = c.replace("\t","").strip()
            if t and not t.startswith("http") and not t.startswith("[") and not t.startswith("]"):
                comp_clean.append(t)

        i = 0
        count = 0
        while i < len(comp_clean) and count < 8:
            title = comp_clean[i]
            if title in cats or len(title) < 15:
                i += 1; continue
            desc = ""
            if i+1 < len(comp_clean):
                nxt = comp_clean[i+1]
                if nxt not in cats and len(nxt) > 15:
                    desc = nxt
            articles.append((title[:120], desc.strip()[:300], "", source))
            seen.add(title)
            count += 1
            i += 2 if desc else 1

    # Si pas d'articles, fallback URLs
    if not articles:
        bdm_urls = []
        for part in text.split("?"):
            if "aHR0c" in part:
                try:
                    b64 = re.search(r'aHR0c[^\s?&]+', part)
                    if b64:
                        decoded = base64.b64decode(b64.group()).decode()
                        cu = decoded.split("?")[0]
                        if "blogdumoderateur" in cu and "/tools/" not in cu and "/service/" not in cu and cu not in bdm_urls:
                            bdm_urls.append(cu)
                except: pass
        for i, url in enumerate(bdm_urls[:8]):
            title = url.split("/")[-1].replace("-"," ").title()
            articles.append((title, "", url, source))

    # Dernier recours
    if not articles:
        for line in text.split("\n"):
            line = line.strip()
            if line and not line.startswith("http") and not line.startswith("[") and len(line) > 30 and not line.startswith("Envoy") and not line.startswith("De :") and not line.startswith("Date") and not line.startswith("Objet") and ":" not in line[:8]:
                articles.append((line[:100], "", "", source))
                if len(articles) >= 8: break

    return articles[:8]

def build_html_summary(articles, date_str, source_name):
    """Build HTML email with article summaries and clickable links."""
    html = ['<html><body style="font-family:sans-serif;padding:20px;max-width:650px">']
    html.append(f'<h2>📰 Résumé — {source_name}</h2>')
    html.append(f'<p>Reçu le {date_str} — {len(articles)} articles</p><hr>')
    
    for i, (title, desc, url, src) in enumerate(articles, 1):
        t = title[:100] if len(title) > 100 else title
        html.append(f'<h3>{i}. {t}</h3>')
        if desc: html.append(f'<p>{desc}</p>')
        if url: html.append(f'<p><a href="{url}">🔗 Lire l\'article →</a></p>')
        html.append('<hr>')
    
    html.append(f'<p><i>Résumé automatique — Alexis Bot 🤖</i></p></body></html>')
    return "\n".join(html)

def send_summary(articles, date_str, source_name, to_email, subject):
    """Send the summary email with HTML formatting."""
    html = build_html_summary(articles, date_str, source_name)
    
    text_lines = [f"📰 Résumé: {source_name}", f"Reçu le {date_str}\n"]
    for i, (title, desc, url, src) in enumerate(articles, 1):
        text_lines.append(f"{i}. {title[:80]}")
        if url: text_lines.append(f"   🔗 {url}")
        text_lines.append("")
    
    data = json.dumps({
        "to": [to_email],
        "subject": f"📰 Résumé: {source_name} — {date_str}",
        "text": "\n".join(text_lines),
        "html": html,
    }).encode()
    
    h = {"Authorization": f"Bearer {key()}", "Content-Type": "application/json"}
    try:
        urllib.request.urlopen(urllib.request.Request(
            f"{BASE}/inboxes/{INBOX}/messages/send", data=data, headers=h, method="POST"))
        return True
    except: return False

def main():
    k = key()
    if not k: print("No key"); return
    done = saved()
    r = api("GET", f"/inboxes/{INBOX}/messages")
    if "e" in r: print(f"API error: {r}"); return
    count = 0
    
    for m in r.get("messages", []):
        mid = m.get("message_id","")
        if mid in done or "received" not in m.get("labels",[]): continue
        if "river.deep@ik.me" not in (m.get("from","")).lower() and not is_known_sender(m.get("from","")):
            mark(mid); continue
        
        eid = urllib.parse.quote(mid, safe="")
        f = api("GET", f"/inboxes/{INBOX}/messages/{eid}")
        if "e" in f: mark(mid); continue
        
        txt = f.get("text") or f.get("preview","")
        html_full = f.get("html") or ""
        # Si le texte est vide mais que du HTML est présent, extraire le texte du HTML
        if not txt and html_full:
            txt = re.sub(r'<[^>]+>', ' ', html_full)
            txt = html_full and re.sub(r'<style[\s\S]*?</style>', ' ', txt)
            txt = re.sub(r'\s+', ' ', txt) if txt else ""
        subj = m.get("subject","Sans objet")
        fr = m.get("from","")
        em = (re.search(r'<([^>]+)>', fr) or [None, fr]).group(1)
        ts = datetime.now().strftime("%d/%m/%Y")
        
        if is_nl(subj, txt):
            # Save to file
            safe = re.sub(r'[^a-zA-Z0-9_-]+', '_', subj)[:60]
            ts_file = datetime.now().strftime("%Y%m%d_%H%M%S")
            fp = os.path.expanduser(f"~/.hermes/newsletters/{ts_file}_{safe}.txt")
            os.makedirs(os.path.dirname(fp), exist_ok=True)
            with open(fp,"w") as f: f.write(f"From: {fr}\nSubject: {subj}\n\n{txt}")
            
            # Extract source name
            src = "Newsletter"
            for s in ["TAO Daily", "BDM", "Reporterre", "Journal du Coin"]:
                if s.lower() in subj.lower() or s.lower() in txt.lower():
                    src = s; break
            
            # Extract articles and send summary
            articles = extract_articles(txt, src)
            if articles:
                if send_summary(articles, ts, src, em, subj):
                    print(f"✅ Résumé envoyé: {subj[:50]}")
                    # Also notify on Telegram
                    tg(f"📬 *{src}* traitée !\n{len(articles)} articles résumés et envoyés par email. ✅")
                else:
                    print(f"❌ Erreur envoi résumé: {subj[:50]}")
                    ack(em, subj)  # fallback: generic ack
            else:
                ack(em, subj)
                print(f"⚠️ Aucun article extrait: {subj[:50]}")
        else:
            p = txt[:250].replace("\n"," ").strip()
            tg(f"📬 *Email perso de River Deep*\n*Sujet:* {subj[:80]}\n{p}\n\nDis-moi si tu veux que je le traite !")
            print(f"Perso: {subj[:50]}")
        
        # Delete the thread after processing
        thread_id = m.get("thread_id", "")
        if thread_id:
            trash_thread(thread_id)
        
        mark(mid); count += 1
    
    print(f"Ok: {count} traite(s)")

if __name__ == "__main__":
    main()