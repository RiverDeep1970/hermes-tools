#!/usr/bin/env python3
"""Migration Mood Tracker v1 -> v2 (données).

v1 : {"date","mood": "1".."8","mood_label","lecture","serie","activite","note"}
v2 : {"date","version":2,"humeur":1..5,"energie":1..5,"etats":[...],
      "activites":[...],"lecture","serie","notes","created_at","updated_at"}

Mapping v1 -> v2 :
  mood 1 -> humeur 1
  mood 2 -> humeur 2
  mood 3 -> humeur 3
  mood 4 -> humeur 5
  mood 5 (Fatigué) -> humeur 3 + etat "fatigue"
  mood 6 (Malade)  -> humeur 3 + etat "malade"
  mood 7 (Stressé) -> humeur 3 + etat "stresse"
  mood 8 (Motivé)  -> humeur 3 + etat "motif"

Chaque fichier migré est sauvegardé en .bak avant écriture.
Usage : migrate-mood-v2.py [--dry]
"""
import json
import os
import re
import sys

ENTRIES = os.path.expanduser(os.environ.get("MOOD_ENTRIES_DIR", "~/.hermes/life-tracker/entries"))

MOOD_TO_HUMEUR = {"1": 1, "2": 2, "3": 3, "4": 5, "5": 3, "6": 3, "7": 3, "8": 3}
MOOD_TO_ETAT = {"5": "fatigue", "6": "malade", "7": "stresse", "8": "motif"}
EMOJI_RE = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]+")


def clean_activite(raw):
    """« 📖 Lecture, 🏃 Sport » -> ['lecture', 'sport']"""
    if not raw or not isinstance(raw, str):
        return []
    out = []
    for part in raw.split(","):
        tag = EMOJI_RE.sub("", part).strip().lower()
        if tag and tag not in out:
            out.append(tag)
    return out


def migrate(entry):
    if entry.get("version") == 2 and "humeur" in entry:
        return None  # déjà migré
    mood = str(entry.get("mood", ""))
    humeur = MOOD_TO_HUMEUR.get(mood)
    if humeur is None:
        return None  # entrée illisible, on ne touche pas
    etats = [MOOD_TO_ETAT[mood]] if mood in MOOD_TO_ETAT else []
    date = entry.get("date", "")
    v2 = {
        "date": date,
        "version": 2,
        "humeur": humeur,
        "etats": etats,
        "activites": clean_activite(entry.get("activite", "")),
        "lecture": entry.get("lecture", "") or "",
        "serie": entry.get("serie", "") or "",
        "notes": entry.get("note", "") or "",
        "created_at": date,
        "updated_at": date,
    }
    if entry.get("energie"):
        v2["energie"] = entry["energie"]
    return v2


def main():
    dry = "--dry" in sys.argv
    files = sorted(f for f in os.listdir(ENTRIES) if f.endswith(".json") and not f.endswith(".bak"))
    migrated = skipped = errors = 0
    for fname in files:
        path = os.path.join(ENTRIES, fname)
        try:
            with open(path, encoding="utf-8") as f:
                entry = json.load(f)
        except (ValueError, OSError) as e:
            print(f"  ⚠️  {fname}: illisible ({e})")
            errors += 1
            continue
        v2 = migrate(entry)
        if v2 is None:
            print(f"  ⏭️  {fname}: déjà en v2 ou non migrable")
            skipped += 1
            continue
        if dry:
            print(f"  🔎 {fname}: mood {entry.get('mood')} → humeur {v2['humeur']}, etats={v2['etats']}, activites={v2['activites']}")
        else:
            with open(path + ".bak", "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(v2, f, ensure_ascii=False)
            print(f"  ✅ {fname}: migré")
        migrated += 1
    print(f"\n{'DRY RUN — ' if dry else ''}migrés={migrated} ignorés={skipped} erreurs={errors}")
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
