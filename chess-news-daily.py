#!/usr/bin/env python3
"""Veille Échecs — résumé avec descriptions, liens, et déduplication + sauvegarde journal."""
import json
import urllib.request
import os
import re
import html
import hashlib
import sys
from datetime import datetime

FEEDS = [
    ("Chess.com FR", "https://www.chess.com/fr/rss/news"),
    ("Chess.com FR", "https://www.chess.com/fr/rss/articles"),
    ("Europe Échecs", "https://www.europe-echecs.com/rss/rss_97.xml"),
]

SAVE_DIR = os.path.expanduser("~/.hermes/editions/data/chess")
CHAT_ID = "8126578200"
SEEN_FILE = os.path.expanduser("~/.hermes/chess-seen-articles.txt")
MAX_ARTICLES = 12

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin",
        "juillet", "août", "septembre", "octobre", "novembre", "décembre"]


def get_token():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token:
        return token
    env_path = os.path.expanduser("~/.hermes/.env")
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip("'\"").strip()
    return None


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()
    with open(SEEN_FILE) as f:
        return set(line.strip() for line in f if line.strip())


def mark_seen(article_id):
    with open(SEEN_FILE, "a") as f:
        f.write(f"{article_id}\n")


def fetch_rss(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  Erreur {url}: {e}", file=sys.stderr)
        return None


def unescape(text):
    """Double unescape pour les flux RSS au format XML (entités doublement encodées)."""
    return html.unescape(html.unescape(text))

def parse_articles(data, source_name):
    """Returns list of (title, description, link, article_id) for new articles."""
    if not data:
        return []
    data = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", data)

    items = re.findall(r"<item>(.*?)</item>", data, re.DOTALL)
    results = []

    for item in items:
        title_m = re.search(r"<title>(.*?)</title>", item, re.DOTALL)
        link_m = re.search(r"<link>(.*?)</link>", item, re.DOTALL)
        desc_m = re.search(r"<description>(.*?)</description>", item, re.DOTALL)
        guid_m = re.search(r"<guid.*?>(.*?)</guid>", item, re.DOTALL)

        if not title_m:
            continue
        title = unescape(title_m.group(1).strip())
        if len(title) < 10:
            continue

        link = unescape(link_m.group(1).strip()) if link_m else ""
        guid = unescape(guid_m.group(1).strip()) if guid_m else link

        # Get description
        desc = ""
        if desc_m:
            desc = unescape(desc_m.group(1).strip())
            desc = re.sub(r"<[^>]+>", " ", desc)  # Strip HTML
            desc = re.sub(r"\s+", " ", desc).strip()
            # Truncate to ~150 chars for a concise summary
            if len(desc) > 150:
                desc = desc[:147] + "..."

        # Create unique ID: hash of GUID + title
        article_id = hashlib.md5(f"{guid}|{title}".encode()).hexdigest()

        results.append((title, desc, link, article_id, source_name))
        if len(results) >= MAX_ARTICLES:
            break

    return results


def send_telegram(text):
    token = get_token()
    if not token:
        print("ERREUR: Token non trouvé", file=sys.stderr)
        return False

    data = json.dumps({"chat_id": CHAT_ID, "text": text}).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        resp = urllib.request.urlopen(req)
        result = json.loads(resp.read())
        return result.get("ok", False)
    except Exception as e:
        print(f"Telegram API error: {e}", file=sys.stderr)
        return False


def send_email(articles, date_fr, subject):
    """Send the full report via AgentMail with HTML formatting."""
    key = None
    with open(os.path.expanduser("~/.hermes/config.yaml")) as f:
        m = re.search(r'AGENTMAIL_API_KEY:\s*"([^"]+)"', f.read())
        if m:
            key = m.group(1)
    if not key:
        print("  Pas de clé AgentMail", file=sys.stderr)
        return False

    # Build HTML
    html_parts = ['<html><body style="font-family:sans-serif;padding:20px;max-width:650px">']
    html_parts.append(f'<h2>♟️ Veille Échecs — {date_fr}</h2>')
    html_parts.append(f'<p><b>{len(articles)} articles</b> aujourd\'hui</p><hr>')

    for i, (title, desc, link, art_id, source) in enumerate(articles, 1):
        html_parts.append(f'<h3>{i}. {title}</h3>')
        html_parts.append(f'<p><small>📰 {source}</small></p>')
        if desc:
            html_parts.append(f'<p>{desc}</p>')
        if link:
            html_parts.append(f'<p><a href="{link}">🔗 Lire l\'article →</a></p>')
        html_parts.append('<hr>')

    html_parts.append(f'<p><i>Rapport quotidien automatique — {len(articles)} articles — {date_fr}</i></p>')
    html_parts.append('</body></html>')
    html_content = '\n'.join(html_parts)

    # Build plain text
    text_lines = [f"♟️ Veille Échecs — {date_fr}", f"{len(articles)} articles\n"]
    for i, (title, desc, link, art_id, source) in enumerate(articles, 1):
        text_lines.append(f"{i}. {title} [{source}]")
        if desc:
            text_lines.append(f"   {desc}")
        if link:
            text_lines.append(f"   🔗 {link}")
        text_lines.append("")
    text_lines.append(f"--- {len(articles)} articles — {date_fr} ---")
    text_content = '\n'.join(text_lines)

    # Send via AgentMail
    data = json.dumps({
        "to": ["river.deep@ik.me"],
        "subject": subject,
        "text": text_content,
        "html": html_content,
    }).encode()
    h = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        r = urllib.request.Request(
            "https://api.agentmail.to/v0/inboxes/alexis-bot@agentmail.to/messages/send",
            data=data, headers=h, method="POST"
        )
        resp = urllib.request.urlopen(r)
        return True
    except Exception as e:
        print(f"  Erreur email: {e}", file=sys.stderr)
        return False


def main():
    now = datetime.now()
    date_fr = f"{JOURS[now.weekday()]} {now.day} {MOIS[now.month-1]} {now.year}"

    seen = load_seen()
    new_articles = []

    for name, url in FEEDS:
        raw = fetch_rss(url)
        articles = parse_articles(raw, name)
        for art in articles:
            title, desc, link, art_id, source = art
            if art_id not in seen:
                new_articles.append(art)
                mark_seen(art_id)
            else:
                print(f"  Déjà vu: {title[:50]}...")

    if not new_articles:
        msg = f"♟️ Veille Échecs — {date_fr}\n\nAucun nouvel article aujourd'hui. ✅"
        if send_telegram(msg):
            print("✅ Rien de nouveau — message envoyé")
        return

    # Build message without Markdown
    msg = f"♟️ Veille Échecs — {date_fr}\n\n"
    msg += f"📬 {len(new_articles)} nouveaux articles\n\n"

    for i, (title, desc, link, art_id, source) in enumerate(new_articles, 1):
        if len(title) > 70:
            title = title[:67] + "..."
        msg += f"{i}. {title} [{source}]\n"
        if desc:
            # Truncate description to 100 chars
            short_desc = desc[:100] + ("..." if len(desc) > 100 else "")
            msg += f"   {short_desc}\n"
        if link:
            msg += f"   🔗 {link}\n"
        msg += "\n"

        # If message is getting too long, stop adding articles
        if len(msg) > 3500:
            remaining = len(new_articles) - i
            if remaining > 0:
                msg += f"... et {remaining} autre(s) article(s) — {date_fr}"
            break
    else:
        msg += f"{len(new_articles)} article(s) — {date_fr}"

    if send_telegram(msg):
        print(f"✅ Veille Échecs Telegram ({len(new_articles)} articles)")
    else:
        print("❌ Échec envoi Telegram")

    # Also send full report by email
    email_subject = f"♟️ Veille Échecs — {date_fr} ({len(new_articles)} articles)"
    if send_email(new_articles, date_fr, email_subject):
        print(f"✅ Veille Échecs email envoyé")
    else:
        print("❌ Échec envoi email")
    
    # Save to journal data
    save_to_journal(new_articles, now)


def save_to_journal(articles, now):
    """Sauvegarde les articles échecs pour le journal."""
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR, exist_ok=True)
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    data = []
    for title, desc, link, art_id, source in articles:
        data.append({
            "source": source,
            "title": title,
            "summary": desc[:200] if desc else "",
            "url": link,
            "date": now.strftime("%Y-%m-%d"),
        })
    fp = os.path.join(SAVE_DIR, f"chess_{timestamp}.json")
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"✅ {len(articles)} articles sauvegardés pour le journal ({fp})")


if __name__ == "__main__":
    main()