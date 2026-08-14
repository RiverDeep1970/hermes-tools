#!/usr/bin/env python3
"""Backup quotidien des bases de données (médicaments + mood)."""
import shutil
import os
import sys
from datetime import datetime, timedelta

DBS = [
    os.path.expanduser("~/.hermes/med-tracker.db"),
    os.path.expanduser("~/.hermes/life-tracker/entries"),
]

BACKUP_DIR = os.path.expanduser("~/.hermes/backups/medoc")
os.makedirs(BACKUP_DIR, exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")
keep_days = 14

def backup_file(src, dest):
    if not os.path.exists(src):
        return False
    shutil.copy2(src, dest)
    return True

backed_up = []

# Backup DB files
med_db = os.path.join(BACKUP_DIR, f"med-tracker-{today}.db")
if backup_file(os.path.expanduser("~/.hermes/med-tracker.db"), med_db):
    backed_up.append("med-tracker.db")

# Backup mood entries as tar.gz
import tarfile
mood_tar = os.path.join(BACKUP_DIR, f"mood-entries-{today}.tar.gz")
if os.path.isdir(os.path.expanduser("~/.hermes/life-tracker/entries")):
    with tarfile.open(mood_tar, "w:gz") as tar:
        tar.add(os.path.expanduser("~/.hermes/life-tracker/entries"), arcname="entries")
    backed_up.append("mood-entries")

# Clean up old backups (keep 14 days)
cleaned = 0
for f in os.listdir(BACKUP_DIR):
    fp = os.path.join(BACKUP_DIR, f)
    if os.path.isfile(fp):
        mtime = os.path.getmtime(fp)
        age_days = (datetime.now().timestamp() - mtime) / 86400
        if age_days > keep_days:
            os.remove(fp)
            cleaned += 1

if backed_up:
    print(f"✅ Backup: {', '.join(backed_up)} ({cleaned} anciens supprimés)")
else:
    print("Aucune donnée à sauvegarder")