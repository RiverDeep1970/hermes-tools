#!/usr/bin/env python3
"""Compile edition data from all sources into latest.json."""
import json, os, glob, time, hashlib
from datetime import datetime, timedelta

BASE = os.path.expanduser("~/.hermes/editions")
DATA = os.path.join(BASE, "data")

STATE_FILE = os.path.join(BASE, "edition_state.json")

CLEANUP_RULES = {
    "newsletters": {"hours": 168, "max": 20},   # 7 jours
    "reddit":      {"hours": 72,  "max": 50},    # 3 jours
    "youtube":     {"hours": 48,  "max": 15},    # 2 jours
    "immobilier":  {"hours": 336, "max": 20},    # 14 jours
    "chess":       {"hours": 168, "max": 30},    # 7 jours
    "techno":      {"hours": 168, "max": 30},    # 7 jours
}

def load_state():
    default = {"last_published_at": None, "seen_ids": []}
    if not os.path.exists(STATE_FILE):
        return default
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except:
        return default

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def extract_item_id(item):
    """Unique identifier for dedup: url > title hash."""
    if item.get("url"):
        return item["url"]
    if item.get("title"):
        return hashlib.md5(item["title"].encode()).hexdigest()
    return None

def cleanup_data():
    """Supprime les fichiers sources au-dela de la retention."""
    for name, rules in CLEANUP_RULES.items():
        dirpath = os.path.join(DATA, name)
        if not os.path.isdir(dirpath):
            continue
        now = time.time()
        files = sorted(glob.glob(os.path.join(dirpath, "*.json")),
                       key=os.path.getmtime, reverse=True)
        removed = 0
        for f in files:
            age = (now - os.path.getmtime(f)) / 3600
            idx = files.index(f)
            if age > rules["hours"] or idx >= rules["max"]:
                os.remove(f)
                removed += 1
        if removed:
            print(f"  Nettoyage {name}: {removed} fichiers supprimes")

# Symboles suivis en priorite dans l'onglet Crypto (le reste en lignes compactes)
CRYPTO_WATCH = ["TAO", "BTC", "ETH", "AAVE", "ZEC"]


def build_crypto_section(crypto, history):
    """Construit la section 'crypto' pour l'onglet du journal.

    crypto  : dict {source, date, coins:[{symbol, price, change_24h}]}
    history : dict {SYMBOL: [{date, price}]}  (1 point par jour)
    """
    coins = crypto.get("coins", []) or []
    by_sym = {}
    for c in coins:
        sym = c.get("symbol")
        if sym:
            by_sym[sym] = c

    def series(sym):
        return [p.get("price") for p in (history.get(sym) or []) if p.get("price")]

    def change_7d(sym):
        s = series(sym)
        if len(s) < 2 or not s[0]:
            return None
        return round((s[-1] - s[0]) / s[0] * 100, 2)

    watch = []
    for sym in CRYPTO_WATCH:
        c = by_sym.get(sym)
        if not c:
            continue
        watch.append({
            "symbol": sym,
            "price": c.get("price", 0),
            "change_24h": c.get("change_24h", 0),
            "change_7d": change_7d(sym),
            "spark": series(sym)[-14:],
        })

    others = [{"symbol": s, "price": c.get("price", 0), "change_24h": c.get("change_24h", 0)}
              for s, c in by_sym.items() if s not in CRYPTO_WATCH]
    others.sort(key=lambda x: x.get("change_24h", 0), reverse=True)

    ranked = sorted(by_sym.values(), key=lambda c: c.get("change_24h", 0))
    up = [{"symbol": c["symbol"], "change_24h": c.get("change_24h", 0)} for c in ranked[-2:][::-1]]
    down = [{"symbol": c["symbol"], "change_24h": c.get("change_24h", 0)} for c in ranked[:2]]

    days = max([len(v) for v in history.values()] or [0])
    return {
        "updated": crypto.get("date"),
        "watchlist": watch,
        "others": others,
        "movers": {"up": up, "down": down},
        "history_days": days,
    }


def load_json_files(dirpath):
    """Load all JSON files from a directory. Adds _collected_at from file mtime."""
    results = []
    if not os.path.isdir(dirpath):
        return results
    for f in sorted(glob.glob(os.path.join(dirpath, "*.json")), reverse=True)[:20]:
        try:
            mtime = datetime.fromtimestamp(os.path.getmtime(f)).isoformat()
            with open(f) as fh:
                data = json.load(fh)
                if isinstance(data, list):
                    for item in data:
                        item["_collected_at"] = mtime
                    results.extend(data)
                else:
                    data["_collected_at"] = mtime
                    results.append(data)
        except:
            pass
    return results

def get_events_by_range(days_from, days_to):
    """Get calendar events with icalendar parsing + categorisation."""
    import sys
    sys.path.insert(0, os.path.expanduser("~/.config/radicale"))
    from datetime import datetime, timedelta
    from radicale_helper import get_events
    import icalendar
    import re
    
    cal_paths = {
        "rc-lens-2026-2027": {"label": "Lens", "type": "sport"},
        "psg-2026-2027":     {"label": "PSG",  "type": "sport"},
        "losc-2026-2027":    {"label": "LOSC", "type": "sport"},
        "calendrier":        {"label": "Agenda", "type": "personal"},
    }
    now = datetime.now()
    start = now + timedelta(days=days_from)
    end = now + timedelta(days=days_to)
    events = []
    
    for cal_dir, info in cal_paths.items():
        r = get_events("/HermesBot/{}/".format(cal_dir))
        if r.get("status") not in (200, 207):
            continue
        try:
            # Extract each VCALENDAR block from multistatus XML
            for m in re.finditer(r'BEGIN:VCALENDAR.*?END:VCALENDAR', r["body"], re.DOTALL):
                try:
                    cal = icalendar.Calendar.from_ical(m.group(0))
                    for component in cal.walk():
                        if component.name != "VEVENT":
                            continue
                        dtstart = component.get("dtstart")
                        if dtstart is None:
                            continue
                        dt = dtstart.dt
                        if hasattr(dt, 'hour'):
                            # datetime avec heure
                            d = dt
                            date_str = d.strftime("%Y-%m-%d")
                            time_str = d.strftime("%H:%M")
                        else:
                            # date seule (VALUE=DATE)
                            d = datetime(dt.year, dt.month, dt.day)
                            date_str = d.strftime("%Y-%m-%d")
                            time_str = ""
                        if start <= d <= end:
                            events.append({
                                "title": str(component.get("summary", "")),
                                "date": date_str,
                                "time": time_str,
                                "calendar": info["label"],
                                "type": info["type"],
                            })
                except:
                    pass
        except Exception as e:
            print("ERR calendar {}: {}".format(cal_dir, e), file=sys.stderr)
    
    events.sort(key=lambda e: (e["date"], e["time"]))
    return events

def build_edition():
    """Build the current edition."""
    now = datetime.now()
    hour = now.hour
    
    # Step 1: Nettoyage des vieux fichiers
    print("Nettoyage des donnees...")
    cleanup_data()
    
    if hour < 8:
        edition = "matin"
    elif hour < 14:
        edition = "midi"
    else:
        edition = "soir"
    
    edition_id = "{}-{}".format(now.strftime("%Y-%m-%d"), edition)
    
    # Load data from all sources
    newsletters = load_json_files(os.path.join(DATA, "newsletters"))
    youtube = load_json_files(os.path.join(DATA, "youtube"))
    reddit = load_json_files(os.path.join(DATA, "reddit"))
    chess_raw = load_json_files(os.path.join(DATA, "chess"))
    techno = load_json_files(os.path.join(DATA, "techno"))
    # Ne garder que les snapshots de prix (history.json n'a pas de cle "coins")
    crypto_raw = [x for x in load_json_files(os.path.join(DATA, "crypto")) if "coins" in x]
    try:
        with open(os.path.join(DATA, "crypto", "history.json")) as fh:
            crypto_history = json.load(fh)
    except Exception:
        crypto_history = {}
    immobilier = load_json_files(os.path.join(DATA, "immobilier"))
    calendar_month = get_events_by_range(0, 30)
    calendar_today = [e for e in calendar_month if e["date"] == now.strftime("%Y-%m-%d")]
    week_end = (now + timedelta(days=7)).strftime("%Y-%m-%d")
    calendar_week = [e for e in calendar_month if e["date"] > now.strftime("%Y-%m-%d") and e["date"] <= week_end]
    
    # Pick crypto data
    crypto = crypto_raw[0] if crypto_raw else {"coins": [], "date": now.isoformat()}
    
    # Load edition state (cutoff + seen_ids)
    state = load_state()
    cutoff = state.get("last_published_at")
    seen_ids = set(state.get("seen_ids", []))
    
    FRESH_HOURS = 48

    def is_fresh(item):
        """Element collecte dans la fenetre recente (FRESH_HOURS heures).

        Avant, la fraicheur signifiait « collecte depuis la derniere
        compilation ». Comme les collectes (newsletters 4h/9h/15h, YouTube 16h)
        ne coincident pas avec les trois compilations de la journee, l'edition
        de midi et celle du soir ne trouvaient plus aucun element « frais » :
        la une se reduisait alors aux evenements du calendrier (0 ou 1 element).
        """
        collected = item.get("_collected_at") or item.get("date") or ""
        if not collected:
            return False
        try:
            quand = datetime.fromisoformat(str(collected).replace("Z", "+00:00"))
        except ValueError:
            return False
        if quand.tzinfo is not None:
            quand = quand.astimezone().replace(tzinfo=None)
        try:
            return (now - quand) <= timedelta(hours=FRESH_HOURS)
        except TypeError:
            return False
    
    def item_id(item):
        """Extract dedup id from an item dict."""
        if item.get("url"):
            return item["url"]
        if item.get("title"):
            return hashlib.md5(item["title"].encode()).hexdigest()
        return None
    
    def is_seen(item):
        """Check if item was already shown in a previous edition."""
        iid = item_id(item)
        return iid is not None and iid in seen_ids
    
    # Filter fresh items for "une"
    fresh_newsletters = [nl for nl in newsletters if is_fresh(nl)]
    fresh_youtube = [yt for yt in youtube if is_fresh(yt)]
    fresh_reddit = [rd for rd in reddit if is_fresh(rd)]
    
    # Build "a la une" from best items across all sources
    une = []
    
    # 3 informations marquantes piochées dans newsletters/youtube/reddit
    highlights = []
    
    # YouTube key_points (faits marquants) — UN seul point par video, pris sur
    # les videos les plus recentes : sinon les trois marquantes pouvaient venir
    # du meme sujet (cas observe : 3 points de la meme video Les Echos).
    for yt in fresh_youtube[:6]:
        if len(highlights) >= 3:
            break
        kps = yt.get("key_points") or []
        if not kps:
            continue
        highlights.append({
            "source": yt.get("source", "YouTube"),
            "type": "marquante",
            "title": kps[0][:90],
            "summary": yt.get("title", ""),
            "url": yt.get("url", ""),
            "date": yt.get("date", "")
        })
    
    # Newsletter résumés — un seul article par newsletter, pour la diversité
    for nl in fresh_newsletters[:3]:
        if isinstance(nl, dict) and nl.get("articles"):
            for art in nl["articles"][:1]:
                if len(highlights) >= 3: break
                txt = art.get("summary", "") or art.get("title", "")
                if len(txt) > 20:
                    highlights.append({
                        "source": nl.get("source", "Newsletter"),
                        "type": "marquante",
                        "title": txt[:90],
                        "summary": art.get("title", ""),
                        "url": art.get("url", ""),
                        "date": nl.get("date", "")
                    })
        if len(highlights) >= 3: break
    
    # Reddit posts
    for rd in fresh_reddit[:3]:
        if len(highlights) >= 3: break
        if rd.get("title"):
            highlights.append({
                "source": rd.get("source", "Reddit"),
                "type": "marquante",
                "title": rd["title"][:90],
                "url": rd.get("url", ""),
                "author": rd.get("author", ""),
                "date": rd.get("date", "")
            })
    
    # Shuffle + take 3 unseen, sinon fallback sur les 3 premières
    import random
    random.shuffle(highlights)
    marquantes = []
    for h in highlights:
        if not is_seen(h):
            marquantes.append(h)
            if len(marquantes) >= 3: break
    if not marquantes:
        marquantes = highlights[:3]
    
    une.extend(marquantes[:3])
    
    # Add today's calendar events (max 1)
    for ev in calendar_today[:1]:
        time_str = " {}".format(ev["time"]) if ev.get("time") else ""
        une.append({
            "source": ev.get("calendar", "Agenda"),
            "type": "event-" + ev.get("type", "personal"),
            "title": ev["title"],
            "summary": "Aujourd hui" + time_str,
            "date": ev["date"]
        })
    # Add this week's events (max 1)
    for ev in calendar_week[:1]:
        time_str = " {}".format(ev["time"]) if ev.get("time") else ""
        une.append({
            "source": ev.get("calendar", "Agenda"),
            "type": "event-" + ev.get("type", "personal"),
            "title": ev["title"],
            "summary": "Cette semaine" + time_str,
            "date": ev["date"]
        })
    # Add top newsletters (skip if seen)
    for nl in fresh_newsletters[:3]:
        if isinstance(nl, dict) and "articles" in nl:
            for art in nl["articles"][:2]:
                if is_seen(art):
                    continue
                une.append({
                    "source": nl.get("source", "Newsletter"),
                    "type": "article",
                    "title": art.get("title", ""),
                    "summary": art.get("summary", ""),
                    "url": art.get("url", ""),
                    "date": nl.get("date", "")
                })
    # Add top YouTube (skip if seen)
    for yt in fresh_youtube[:2]:
        if is_seen(yt):
            continue
        une.append({
            "source": yt.get("source", "YouTube"),
            "type": "video",
            "title": yt.get("title", ""),
            "summary": yt.get("summary", ""),
            "key_points": yt.get("key_points", []),
            "url": yt.get("url", ""),
            "date": yt.get("date", "")
        })
    # Add top Reddit (skip if seen)
    for rd in fresh_reddit[:3]:
        if is_seen(rd):
            continue
        une.append({
            "source": rd.get("source", "Reddit"),
            "type": "post",
            "title": rd.get("title", ""),
            "url": rd.get("url", ""),
            "author": rd.get("author", ""),
            "date": rd.get("date", "")
        })

    # Filet de securite : la une ne doit JAMAIS etre vide alors que des donnees
    # existent, et elle doit rester substantielle au fil de la journee (chaque
    # compilation consomme des identifiants « vus »). On complete donc jusqu'a
    # UNE_MIN elements avec les plus recents, en evitant les doublons.
    UNE_MIN = 5
    if len(une) < UNE_MIN:
        deja = set()
        for it in une:
            iid = item_id(it)
            if iid:
                deja.add(iid)
        complements = []
        for yt in youtube[:4]:
            complements.append({
                "source": yt.get("source", "YouTube"),
                "type": "video",
                "title": yt.get("title", ""),
                "summary": yt.get("summary", ""),
                "key_points": yt.get("key_points", []),
                "url": yt.get("url", ""),
                "date": yt.get("date", "")
            })
        for nl in newsletters[:4]:
            if not isinstance(nl, dict):
                continue
            for art in (nl.get("articles") or [])[:2]:
                complements.append({
                    "source": nl.get("source", "Newsletter"),
                    "type": "article",
                    "title": art.get("title", ""),
                    "summary": art.get("summary", ""),
                    "url": art.get("url", ""),
                    "date": nl.get("date", "")
                })
        for rd in reddit[:4]:
            complements.append({
                "source": rd.get("source", "Reddit"),
                "type": "post",
                "title": rd.get("title", ""),
                "url": rd.get("url", ""),
                "author": rd.get("author", ""),
                "date": rd.get("date", "")
            })
        for it in complements:
            if len(une) >= UNE_MIN:
                break
            iid = item_id(it)
            if iid and iid in deja:
                continue
            une.append(it)
            if iid:
                deja.add(iid)

    edition_data = {
        "id": edition_id,
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M"),
        "edition": edition,
        "_ticker": crypto.get("coins", []),
        "sections": {
            "une": une[:8],
            "newsletters": newsletters[:8],
            "youtube": youtube[:6],
            "reddit": reddit[:10],
            "echecs": chess_raw[:10],
            "techno": techno[:10],
            "immobilier": immobilier[:10],
            "crypto": build_crypto_section(crypto, crypto_history),
            "agenda": calendar_month
        }
    }
    
    with open(os.path.join(BASE, "latest.json"), "w") as f:
        json.dump(edition_data, f, indent=2, ensure_ascii=False)
    
    # Log warning for empty sections
    for name, items in edition_data["sections"].items():
        if not items:
            print("  AVERTISSEMENT: section '{}' est vide".format(name))
    
    # Update state: record seen IDs from "une" + update cutoff
    new_ids = set()
    for item in une:
        iid = item_id(item)
        if iid:
            new_ids.add(iid)
    # Also add newsletter article URLs that were skipped (they were seen)
    for nl in newsletters:
        if isinstance(nl, dict) and "articles" in nl:
            for art in nl.get("articles", []):
                if art.get("url") and not is_seen(art):
                    pass  # unseen articles are kept available
    state["seen_ids"] = list(seen_ids | new_ids)[-200:]  # keep last 200
    state["last_published_at"] = now.isoformat()
    save_state(state)
    
    print("Edition {} compilee: {} articles ({} seen_ids)".format(
        edition_id, len(une), len(state["seen_ids"])))

if __name__ == "__main__":
    build_edition()