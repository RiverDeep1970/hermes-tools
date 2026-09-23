#!/usr/bin/env python3
"""Calendar notifications: Telegram alerts 24h before events."""
import json, os, sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~/.config/radicale"))
from radicale_helper import get_events
import icalendar
import re

BASE = os.path.expanduser("~/.hermes/editions")
LAST_FILE = os.path.join(BASE, "calendar_notified.json")

cal_paths = {
    "rc-lens-2026-2027": {"label": "Lens", "type": "sport"},
    "psg-2026-2027":     {"label": "PSG",  "type": "sport"},
    "losc-2026-2027":    {"label": "LOSC", "type": "sport"},
    "calendrier":        {"label": "Agenda", "type": "personal"},
}

def load_notified():
    if not os.path.exists(LAST_FILE):
        return set()
    try:
        with open(LAST_FILE) as f:
            return set(json.load(f))
    except:
        return set()

def save_notified(ids):
    with open(LAST_FILE, "w") as f:
        json.dump(list(ids), f)

def main():
    now = datetime.now()
    tomorrow = now + timedelta(days=1)
    day_after = now + timedelta(days=2)
    
    # Get events for tomorrow and the day after
    start = now
    end = day_after
    notified = load_notified()
    new_alerts = []
    
    for cal_dir, info in cal_paths.items():
        r = get_events("/HermesBot/{}/".format(cal_dir))
        if r.get("status") not in (200, 207):
            continue
        try:
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
                        if hasattr(dt, 'strftime'):
                            ev_date = dt
                        else:
                            ev_date = datetime(dt.year, dt.month, dt.day)
                        
                        # Alert if event is tomorrow
                        if ev_date.date() == tomorrow.date():
                            title = str(component.get("summary", ""))
                            ev_id = "{}-{}".format(cal_dir, title)
                            if ev_id not in notified:
                                time_str = ev_date.strftime(" %H:%M") if hasattr(dt, 'strftime') else ""
                                new_alerts.append({
                                    "calendar": info["label"],
                                    "type": info["type"],
                                    "title": title,
                                    "time": time_str,
                                    "date": tomorrow.strftime("%Y-%m-%d"),
                                })
                                notified.add(ev_id)
                except:
                    pass
        except:
            pass
    
    # Output alerts
    if new_alerts:
        for a in new_alerts:
            icon = "⚽" if a["type"] == "sport" else "📅"
            msg = "{} **{}** — {} {}\n  Match {} demain {}!".format(
                icon, a["calendar"], a["title"], a["time"], a["calendar"], a["date"])
            print(msg)
        
        save_notified(notified)
    else:
        print("Aucun evenement demain")

if __name__ == "__main__":
    main()