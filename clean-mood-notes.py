#!/usr/bin/env python3
"""Nettoie les notes dupliquées par l'ancien bug de concaténation.

L'ancien `_handle_save` concaténait la note existante : « a ; a ».
Ce script déduplique les segments d'une note séparés par « ; » en conservant l'ordre.

Usage : clean-mood-notes.py [--dry]
"""
import json
import os
import shutil
import sys

ENTRIES = os.path.expanduser(os.environ.get("MOOD_ENTRIES_DIR", "~/.hermes/life-tracker/entries"))
BACKUP = os.path.expanduser("~/.hermes/backups/mood-notes-cleanup")


def dedup_note(note):
    if not note or ";" not in note:
        return note
    parts = [p.strip() for p in note.split(";")]
    seen, out = set(), []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return "; ".join(out)


def main():
    dry = "--dry" in sys.argv
    if not dry:
        os.makedirs(BACKUP, exist_ok=True)
    changed = 0
    for fname in sorted(os.listdir(ENTRIES)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(ENTRIES, fname)
        try:
            with open(path, encoding="utf-8") as f:
                e = json.load(f)
        except (ValueError, OSError) as ex:
            print(f"  ⚠️  {fname}: illisible ({ex})")
            continue
        note = e.get("notes", "")
        fixed = dedup_note(note)
        if fixed != note:
            print(f"  {fname}:\n     avant : {note!r}\n     après : {fixed!r}")
            if not dry:
                shutil.copy2(path, os.path.join(BACKUP, fname + ".bak"))
                e["notes"] = fixed
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(e, f, ensure_ascii=False)
            changed += 1
    print(f"\n{'DRY RUN — ' if dry else ''}{changed} note(s) nettoyée(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
