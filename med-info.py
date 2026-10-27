#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
med-info.py — Récupération et stockage des informations officielles sur les
médicaments (source : Base de Données Publique des Médicaments — ANSM).

Deux sources, toutes deux publiques et officielles :
  1. Fichiers open data (CIS_bdpm.txt, CIS_COMPO_bdpm.txt) : dénomination,
     forme, voie, statut AMM, titulaire, composition.
  2. Page « extrait » du médicament : contient le RCP complet (indications,
     posologie, contre-indications, conservation) ET la notice patient
     (pourquoi / comment le prendre). Une seule requête HTTP par médicament.

Stockage : table `med_info` dans ~/.hermes/med-tracker.db

Usage :
    python3 med-info.py search <nom>            # candidats CIS
    python3 med-info.py fetch <nom|CIS> [...]   # récupère + stocke
    python3 med-info.py show <nom|CIS>          # affiche ce qui est stocké
    python3 med-info.py list                    # tout ce qui est stocké
    python3 med-info.py refresh-od            # rafraîchit les fichiers open data
"""
import os
import re
import sys
import json
import html as _html
import sqlite3
import urllib.request
import urllib.parse
from datetime import datetime

DB_PATH = os.path.expanduser("~/.hermes/med-tracker.db")
CACHE_DIR = os.path.expanduser("~/.hermes/cache/medocs")
BASE = "https://base-donnees-publique.medicaments.gouv.fr"
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")

OD_FILES = {
    "CIS_bdpm.txt": "cis",
    "CIS_COMPO_bdpm.txt": "compo",
    "CIS_CIP_bdpm.txt": "cip",
    "CIS_HAS_SMR_bdpm.txt": "smr",
}

# ---------------------------------------------------------------- utilitaires

def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _txt(s):
    """HTML -> texte lisible, en conservant les sauts de paragraphe."""
    s = re.sub(r"<script.*?</script>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<(br|/p|/div|/li|/tr|/h[1-6])[^>]*>", "\n", s, flags=re.I)
    s = re.sub(r"<li[^>]*>", "\n- ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = _html.unescape(s)
    s = s.replace("\xa0", " ")
    lines = [re.sub(r"[ \t]+", " ", l).strip() for l in s.split("\n")]
    out = []
    for l in lines:
        if l:
            out.append(l)
        elif out and out[-1] != "":
            out.append("")
    return "\n".join(out).strip()


# ------------------------------------------------------------- open data ANSM

def refresh_od(force=False):
    os.makedirs(CACHE_DIR, exist_ok=True)
    for fn in OD_FILES:
        path = os.path.join(CACHE_DIR, fn)
        if not force and os.path.exists(path) and \
           (datetime.now().timestamp() - os.path.getmtime(path)) < 15 * 86400:
            continue
        try:
            data = _get(f"{BASE}/download/file/{fn}", timeout=90)
            with open(path, "wb") as f:
                f.write(data)
        except Exception as e:
            print(f"! téléchargement {fn} : {e}", file=sys.stderr)


def _rows(fn):
    path = os.path.join(CACHE_DIR, fn)
    if not os.path.exists(path):
        return []
    raw = open(path, encoding="latin-1").read().lstrip("\ufeff").split("\n")
    for l in raw:
        if not l.strip():
            continue
        yield [c.strip() for c in l.split("\t")]


def search_cis(query, limit=25, only_active=True, _fuzzy=True):
    """Recherche par nom : renvoie une liste de dicts (CIS, dénomination, ...)."""
    q = query.upper().strip()
    res = []
    for f in _rows("CIS_bdpm.txt"):
        if len(f) < 7:
            continue
        if q not in f[1].upper():
            continue
        if only_active and f[4] != "Autorisation active":
            continue
        res.append({
            "cis": f[0], "name": f[1], "forme": f[2], "voie": f[3],
            "statut": f[4], "procedure": f[5], "commercialise": f[6],
            "date_amm": f[7] if len(f) > 7 else "",
            "titulaire": f[-2] if len(f) > 10 else "",
        })
    # nom le plus proche d'abord (préfixe / exact)
    res.sort(key=lambda x: (abs(len(x["name"]) - len(q)),
                            0 if x["name"].upper().startswith(q) else 1,
                            x["name"]))
    if res or not _fuzzy:
        return res[:limit]

    # --- repli tolérant aux fautes de frappe (« Alopurinol » → ALLOPURINOL) ---
    import difflib
    words = set()
    for f in _rows("CIS_bdpm.txt"):
        if len(f) >= 5 and (not only_active or f[4] == "Autorisation active"):
            for w in re.split(r"[^A-ZÀ-Ü0-9]+", f[1].upper()):
                if len(w) >= 5:
                    words.add(w)
    for w in difflib.get_close_matches(q, sorted(words), n=4, cutoff=0.72):
        res.extend(search_cis(w, limit=limit, only_active=only_active, _fuzzy=False))
    seen, out = set(), []
    for c in res:
        if c["cis"] not in seen:
            seen.add(c["cis"])
            out.append(c)
    return out[:limit]


def by_cis(cis):
    """Fiche d'identité d'un médicament à partir de son code CIS (exact)."""
    for f in _rows("CIS_bdpm.txt"):
        if f and f[0] == str(cis):
            return {
                "cis": f[0], "name": f[1] if len(f) > 1 else "",
                "forme": f[2] if len(f) > 2 else "", "voie": f[3] if len(f) > 3 else "",
                "statut": f[4] if len(f) > 4 else "",
                "titulaire": f[-2] if len(f) > 10 else "",
            }
    return None


def composition(cis):
    out = []
    for f in _rows("CIS_COMPO_bdpm.txt"):
        if len(f) >= 4 and f[0] == str(cis):
            out.append({"substance": f[3], "dosage": f[4] if len(f) > 4 else "",
                        "nature": f[2] if len(f) > 2 else "",
                        "ref": f[1] if len(f) > 1 else ""})
    return out


# ---------------------------------------------------------- page extrait BDPM

# Bornes de découpage : TOUTES les ancres connues de la page, dans l'ordre du
# document. Sert à arrêter proprement chaque section extraite.
BOUNDS = [
    "RcpDenomination", "RcpCompoQualiQuanti", "RcpFormePharm",
    "RcpDonneesCliniques", "RcpIndicTherap", "RcpPosoAdmin",
    "RcpContreindications", "RcpMisesEnGarde", "RcpInteractionsMed",
    "RcpFertGrossAllait", "RcpConduite", "RcpEffetsIndesirables",
    "RcpSurdosage", "RcpPropPharmacologiques", "RcpDonneesPharmaceutiques",
    "RcpListeExcipients", "RcpIncompatibilites", "RcpDureeConservation",
    "RcpPrecConservation", "RcpEmballage", "RcpPrecEmpl", "RcpTitulaireAmm",
    "RcpNumAutor", "RcpPremiereAutorisation", "RcpDateRevision",
    "RcpCondPrescription", "RcpDosimetrie", "RcpInstPrepRadioph",
    "Ann3bDenomination", "Ann3bEncadre", "Ann3bSomm", "Ann3bQuestceque",
    "Ann3bInfoNecessaires", "Ann3bCommentPrendre", "Ann3bEffetsIndesirables",
    "Ann3bConservation", "Ann3bEmballage", "Ann3bContenu", "Ann3bTituAMM",
    "Ann3bExploitAMM", "Ann3bFab", "Ann3bNomsMediEEE", "Ann3bAutres",
]

# Sections conservées : ancre -> clé. Le contenu va de l'ancre jusqu'à la
# PROCHAINE ancre connue (BOUNDS), donc pas de débordement sur la rubrique 6.5.
SECTIONS = {
    "indications":        "RcpIndicTherap",
    "posologie":          "RcpPosoAdmin",
    "contre_indications": "RcpContreindications",
    "mises_en_garde":     "RcpMisesEnGarde",
    "effets_indesirables": "RcpEffetsIndesirables",
    "conservation":       "RcpDureeConservation",
    "conservation_prec":  "RcpPrecConservation",
    "cond_prescription":  "RcpCondPrescription",
    # notice patient (annexe)
    "notice_pourquoi":     "Ann3bQuestceque",
    "notice_comment_prendre": "Ann3bCommentPrendre",
    "notice_effets_indesirables": "Ann3bEffetsIndesirables",
    "notice_conservation": "Ann3bConservation",
}

_BOILER = (
    "Redirection vers le haut de page", "Lien de redirection",
    "Cliquez ici pour accéder au glossaire", "Aller au glossaire",
)


def parse_extrait(html):
    """Découpe la page extrait en sections à partir des ancres <a name=...>."""
    # positions de TOUTES les ancres connues -> bornes de découpage
    bounds = []
    for anchor in BOUNDS:
        m = re.search(r'<a\s+name="%s"' % re.escape(anchor), html)
        if m:
            bounds.append((m.start(), anchor))
    bounds.sort()
    where = {a: i for i, (_, a) in enumerate(bounds)}

    sec = {}
    for key, anchor in SECTIONS.items():
        if anchor not in where:
            sec[key] = ""
            continue
        i = where[anchor]
        start = bounds[i][0]
        end = bounds[i + 1][0] if i + 1 < len(bounds) else len(html)
        t = _txt(html[start:end])
        lines = []
        for l in t.split("\n"):
            ls = l.strip()
            if not ls or ls in _BOILER:
                continue
            # retire le titre de rubrique répété (ex. « 4.1. Indications thérapeutiques »)
            if re.match(r"^\d+(\.\d+)*\.?\s+\S", ls) and len(ls) < 90 and not lines:
                continue
            if re.match(r"^(Résumé des caractéristiques|Annexe|Notice patient|"
                        r"Sommaire de la notice|Fiche info)$", ls, re.I):
                break
            lines.append(ls)
        sec[key] = "\n".join(lines).strip()
    return sec


def parse_meta(html):
    meta = {}
    m = re.search(r"<title>([^<]*)</title>", html)
    t = _txt(html)
    m2 = re.search(r"Date de l'autorisation\s*:\s*([0-9/]+)", t)
    meta["date_amm"] = m2.group(1) if m2 else ""
    m3 = re.search(r"Titulaire de l'autorisation\s*:\s*([^\n]+)", t)
    meta["titulaire"] = m3.group(1).strip() if m3 else ""
    for tag in ("remboursable", "sur ordonnance uniquement", "générique",
                "hospitalier", "non remboursable"):
        if re.search(r">\s*%s\s*<" % re.escape(tag), html, re.I):
            meta.setdefault("tags", []).append(tag)
    return meta


def fetch_medicament(cis):
    """Récupère et parse un médicament par son code CIS."""
    htmlbytes = _get(f"{BASE}/medicament/{cis}/extrait")
    try:
        html = htmlbytes.decode("utf-8")
    except UnicodeDecodeError:
        html = htmlbytes.decode("latin-1")
    sec = parse_extrait(html)
    if not any(sec.values()):
        raise RuntimeError(f"CIS {cis} : aucune section extraite (page vide ou invalide ?)")
    return {
        "cis": str(cis),
        "meta": parse_meta(html),
        "sections": sec,
        "source": f"{BASE}/medicament/{cis}/extrait",
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


# ------------------------------------------------------------------- stockage

def ensure_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS med_info (
        cis TEXT PRIMARY KEY,
        denomination TEXT,
        forme TEXT, voie TEXT, statut TEXT, titulaire TEXT, date_amm TEXT,
        substances TEXT,
        indications TEXT, posologie TEXT, contre_indications TEXT,
        conservation TEXT, cond_prescription TEXT,
        notice_pourquoi TEXT, notice_comment_prendre TEXT,
        resume TEXT,
        source TEXT, fetched_at TEXT
    )""")
    conn.commit()


def store(cis, data, name=None, forme="", voie="", statut="", resume=None):
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    s = data["sections"]
    meta = data.get("meta", {})
    subs = composition(cis)
    substances = json.dumps(subs, ensure_ascii=False)
    conn.execute("""INSERT INTO med_info (cis, denomination, forme, voie, statut,
        titulaire, date_amm, substances, indications, posologie, contre_indications,
        conservation, cond_prescription, notice_pourquoi, notice_comment_prendre,
        resume, source, fetched_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(cis) DO UPDATE SET
          denomination=excluded.denomination, forme=excluded.forme, voie=excluded.voie,
          statut=excluded.statut, titulaire=excluded.titulaire, date_amm=excluded.date_amm,
          substances=excluded.substances, indications=excluded.indications,
          posologie=excluded.posologie, contre_indications=excluded.contre_indications,
          conservation=excluded.conservation, cond_prescription=excluded.cond_prescription,
          notice_pourquoi=excluded.notice_pourquoi,
          notice_comment_prendre=excluded.notice_comment_prendre,
          resume=COALESCE(excluded.resume, med_info.resume),
          source=excluded.source, fetched_at=excluded.fetched_at""",
        (cis, name or "", forme, voie, statut,
         meta.get("titulaire", ""), meta.get("date_amm", ""), substances,
         s.get("indications", ""), s.get("posologie", ""),
         s.get("contre_indications", ""),
         (s.get("conservation", "") + ("\n" + s.get("conservation_prec", "") if s.get("conservation_prec") else "")).strip(),
         s.get("cond_prescription", ""),
         s.get("notice_pourquoi", ""), s.get("notice_comment_prendre", ""),
         resume, data["source"], data["fetched_at"]))
    conn.commit()
    conn.close()


def get_stored(cis):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    r = conn.execute("SELECT * FROM med_info WHERE cis=?", (str(cis),)).fetchone()
    conn.close()
    return dict(r) if r else None


def list_stored():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_schema(conn)
    rows = [dict(r) for r in conn.execute(
        "SELECT cis, denomination, fetched_at, length(COALESCE(resume,'')) AS lr FROM med_info ORDER BY denomination")]
    conn.close()
    return rows


# --------------------------------------------------------------------- CLI

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    cmd = args[0]
    if cmd == "refresh-od":
        refresh_od(force="--force" in args)
        print("open data à jour :", ", ".join(sorted(os.listdir(CACHE_DIR))))
    elif cmd == "search":
        refresh_od()
        for c in search_cis(" ".join(args[1:])):
            print(f"{c['cis']}  {c['name']}  [{c['forme']} / {c['voie']}] {c['statut']}")
    elif cmd == "fetch":
        refresh_od()
        for q in args[1:]:
            target = None
            if re.fullmatch(r"\d{8}", q):
                target = {"cis": q, "name": q, "forme": "", "voie": "", "statut": ""}
            else:
                cands = search_cis(q, limit=5)
                if not cands:
                    print(f"?? aucun candidat pour {q!r}")
                    continue
                target = cands[0]
                if len(cands) > 1:
                    print(f"→ {q!r} : {len(cands)} candidats, pris le 1er "
                          f"({target['name']}) ; autres : "
                          + " ; ".join(c["name"] for c in cands[1:4]))
            data = fetch_medicament(target["cis"])
            store(target["cis"], data, name=target["name"],
                  forme=target.get("forme", ""), voie=target.get("voie", ""),
                  statut=target.get("statut", ""))
            s = data["sections"]
            print(f"OK  {target['cis']}  {target['name']}")
            for k in ("indications", "posologie", "contre_indications",
                      "notice_pourquoi", "notice_comment_prendre"):
                print(f"    {k}: {len(s.get(k,''))} car.")
    elif cmd == "show":
        rec = get_stored(args[1]) if re.fullmatch(r"\d{8}", args[1]) else None
        if rec is None:
            refresh_od()
            c = search_cis(" ".join(args[1:]), limit=1)
            rec = get_stored(c[0]["cis"]) if c else None
        print(json.dumps(rec, ensure_ascii=False, indent=1) if rec else "non trouvé")
    elif cmd == "list":
        for r in list_stored():
            print(f"{r['cis']}  {r['denomination']}  resume={r['lr']}c  {r['fetched_at']}")
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
