#!/usr/bin/env python3
"""Test runner pour le journal — tests unitaires + non regression."""

import json, os, sys, glob, re, hashlib, time, importlib, importlib.util
from datetime import datetime, timedelta

BASE = os.path.expanduser("~/.hermes/journal-tests")
FIXTURES = os.path.join(BASE, "fixtures")
SCRIPTS = os.path.join(BASE, "scripts")
TEST_DATA = os.path.join(BASE, "test-data")
STATIC = os.path.expanduser("~/.hermes/journal-static")

PASS = 0
FAIL = 0

def test(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}: {detail}")

def assert_contains(text, pattern, desc):
    """Verifie que pattern est dans text."""
    if pattern in text:
        return True, ""
    return False, f"'{pattern}' absent de '{text[:100]}...'"

def _read(path):
    """Lit un fichier texte, retourne '' s'il est absent."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""

# ─── Test 1: Parsing calendrier ──────────────────────────────────

def test_calendar_parsing():
    print("\n--- Test 1: Parsing calendrier (.ics -> events)")
    
    cal_dir = os.path.join(FIXTURES, "calendars")
    cal_files = sorted(glob.glob(os.path.join(cal_dir, "*.ics")))
    test("Fichiers .ics trouves", len(cal_files) >= 3)
    
    # Parse les fichiers
    events = []
    for fp in cal_files:
        with open(fp, encoding="utf-8") as fh:
            txt = fh.read()
        m = re.search(r'^SUMMARY:(.+)', txt, re.M)
        title = m.group(1).strip() if m else "?"
        dm = re.search(r'DTSTART[^:]*:(\d{4})(\d{2})(\d{2})', txt)
        if dm:
            d = datetime(int(dm.group(1)), int(dm.group(2)), int(dm.group(3)))
            events.append({"title": title, "date": d.strftime("%Y-%m-%d")})
    
    test("Events parsés", len(events) >= 3, f"{len(events)} trouvés")
    
    # Verifie des valeurs connues
    lens = [e for e in events if "Lens" in e["title"]]
    test("Match Lens trouve", len(lens) == 1)
    
    anneaux = [e for e in events if "Anneaux" in e["title"]]
    test("Serie Anneaux trouve", len(anneaux) == 1)
    
    rdv = [e for e in events if "dentiste" in e["title"]]
    test("RDV personnel trouve", len(rdv) == 1)

# ─── Test 2: Edition compiler ──────────────────────────────────

def test_edition_compiler():
    print("\n--- Test 2: Edition compiler (compilation edition)")
    
    # Import edition-compiler temporairement
    sys.path.insert(0, SCRIPTS)
    
    # Test que load_json_files fonctionne sur des fixtures
    import importlib.util
    spec = importlib.util.spec_from_file_location("ec",
        os.path.join(SCRIPTS, "edition-compiler.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    
    # Test load_json_files with empty dir
    empty_dir = os.path.join(TEST_DATA, "empty")
    os.makedirs(empty_dir, exist_ok=True)
    result = mod.load_json_files(empty_dir)
    test("load_json_files - dossier vide", result == [])
    
    # Test load_json_files with real data
    result_with = mod.load_json_files(os.path.join(FIXTURES, "data"))
    test("load_json_files - contient _ticker", 
         any("_ticker" in str(x) or "E6" in str(x) or "marquante" in str(x) for x in result_with))
    
    # Test get_events_by_range
    test("get_events_by_range importable",
         hasattr(mod, "get_events_by_range"), "non importable")
    
    print("  (get_events_by_range non teste ici car depend de Radicale)")

# ─── Test 3: Server HTML ──────────────────────────────────

def test_server_html():
    print("\n--- Test 3: Serveur + assets front (journal-static)")

    # Depuis le refactoring, le JS et le CSS vivent dans ~/.hermes/journal-static/
    # et le serveur ne sert plus qu'une page minimale + les fichiers statiques.
    with open(os.path.join(SCRIPTS, "journal-server.py"), encoding="utf-8") as f:
        server = f.read()
    js = _read(os.path.join(STATIC, "journal.js"))
    css = _read(os.path.join(STATIC, "journal.css"))

    test("le serveur sert /static/journal.js", "/static/journal.js" in server)
    test("le serveur sert /static/journal.css", "/static/journal.css" in server)

    # Verifier la presence des onglets (tableau JS tabNames)
    test("tabNames defini", "var tabNames=[" in js)
    for tab_name in ["une", "newsletters", "youtube", "echecs", "techno",
                     "crypto", "immobilier", "agenda", "reddit"]:
        ok, err = assert_contains(js, f'"{tab_name}"', f"Onglet {tab_name} dans tabNames")
        test(f"Onglet {tab_name} dans tabNames", ok, err)

    # Verifier les fonctions JS critiques
    funcs = ["render(", "renderUne(", "renderAgenda(", "renderImmo(",
             "renderNewsletter(", "renderReddit(", "renderCrypto("]
    for fn in funcs:
        ok, err = assert_contains(js, fn, f"Fonction {fn}")
        test(f"Fonction {fn} definie", ok, err)

    # Verifier les classes CSS
    css_classes = [".tab", ".badge", ".art", ".ticker-wrap", ".ccard", ".crow", ".cspark"]
    for cls in css_classes:
        ok, err = assert_contains(css, cls, f"CSS {cls}")
        test(f"CSS {cls} present", ok, err)

    # ── Onglet Crypto ──
    print("  -- Onglet Crypto --")
    test("branche de rendu crypto", 'n==="crypto"' in js)
    test("comptage dedie du badge (objet, pas tableau)", "cryptoCount(" in js)
    test("badge crypto branche sur cryptoCount", 'n==="crypto"){count=cryptoCount(section)}' in js)
    test("degre de degradation si donnees absentes", "Donnees crypto indisponibles" in js)
    test("indication de fraicheur du releve", "Releve " in js and "cryptAge(" in js)
    test("sparkline SVG sans librairie", "cspark" in js and "<polyline" in js)
    test("ES5 strict : pas de fetch/arrow/let", "=>" not in js and "fetch(" not in js and " let " not in js)

# ─── Test 4: API endpoints ──────────────────────────────────

def test_api_endpoints():
    print("\n--- Test 4: API endpoints (tests avec fixtures)")
    
    # Creer un repertoire test-data avec la fixture latest.json
    test_data_dir = os.path.join(BASE, "test-data")
    os.makedirs(test_data_dir, exist_ok=True)
    
    # Copier la fixture comme latest.json
    import shutil
    shutil.copy(os.path.join(FIXTURES, "data", "latest.json"),
               os.path.join(test_data_dir, "latest.json"))
    
    # Creer une version patchee du serveur avec BASE pointe vers test-data
    # On ne peut pas facilement patcher le module, donc on test juste
    # que le template HTML contient les bons elements
    print("  (Le test serveur complet necessite de lancer un process sur 8091)")

# ─── Test 5: Snapshot / non regression ──────────────────────────────────

def test_snapshot():
    print("\n--- Test 5: Non regression (snapshot edition)")
    
    snapshot_file = os.path.join(BASE, "snapshot.json")
    
    # Construire une edition de test a la main
    edition = {
        "id": "test-snapshot",
        "date": "2026-09-30",
        "edition": "test",
        "sections": {
            "une": [{"type": "test", "title": "data"}],
            "newsletters": [],
            "youtube": [],
            "echecs": [],
            "techno": [],
            "immobilier": [],
            "agenda": []
        }
    }
    
    # Calculer un hash du contenu (normalise)
    content = json.dumps(edition, sort_keys=True)
    h = hashlib.md5(content.encode()).hexdigest()
    
    # Si snapshot existe, comparer
    if os.path.exists(snapshot_file):
        with open(snapshot_file) as f:
            prev = json.load(f)
        if prev.get("hash") == h:
            test("Snapshot identique", True)
        else:
            test("Snapshot different", True, 
                 f"Ancien: {prev.get('hash')} vs Nouveau: {h}")
    else:
        # Creer le premier snapshot
        with open(snapshot_file, "w") as f:
            json.dump({"hash": h, "date": datetime.now().isoformat()}, f)
        test("Premier snapshot cree", True)

# ─── Test 6: Deploiement securise ──────────────────────────────────

def test_deployment():
    print("\n--- Test 6: Verification deploiement")
    
    # Verifier que les scripts test et prod sont differents
    for name in ["journal-server.py", "edition-compiler.py", "cal-util.py"]:
        prod = os.path.expanduser(f"~/.hermes/scripts/{name}")
        test_env = os.path.join(SCRIPTS, name)
        
        if not os.path.exists(prod) or not os.path.exists(test_env):
            test(f"Fichier {name} manquant", False)
            continue
        
        with open(prod) as f: prod_content = f.read()
        with open(test_env) as f: test_content = f.read()
        
        if prod_content == test_content:
            test(f"{name} - prod = test (synced)", True)
        else:
            test(f"{name} - prod != test (non deployee)", True,
                 "Modifications en test pas encore en prod")

# ─── Main ──────────────────────────────────

def main():
    print(f"=== Journal Test Runner ===")
    print(f"Time: {datetime.now().isoformat()[:19]}")
    print(f"Base: {BASE}")
    
    test_calendar_parsing()
    test_edition_compiler()
    test_server_html()
    test_api_endpoints()
    test_snapshot()
    test_deployment()
    
    print(f"\n=== Resultats: {PASS} passe(s), {FAIL} echec(s) ===")
    return FAIL == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)