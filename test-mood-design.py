#!/usr/bin/env python3
"""Tests de design (L1-L3) : tokens, dégradé émotionnel, titres, accessibilité.
Analyse statique du fichier — aucune dépendance à une instance en cours."""
import os
import re
import sys

SRC = os.path.expanduser(os.environ.get("MOOD_SERVER", "~/.hermes/scripts/mood-server.py"))
src = open(SRC, encoding="utf-8").read()
s = src.index('HTML = r"""')
html = src[s:src.index('"""', s + 12)]

ok = fail = 0


def check(name, cond, detail=""):
    global ok, fail
    if cond:
        ok += 1
        print(f"  ✅ {name}")
    else:
        fail += 1
        print(f"  ❌ {name} {detail}")


print("=== L1 · Tokens & palette ===")
check("color-scheme light + dark",
      "color-scheme:light" in html and "color-scheme:dark" in html)
check("accent Iris #6c5ce7 (clair)", "--accent:#6c5ce7" in html)
check("accent clair en sombre #9b8cff", "--accent:#9b8cff" in html)
check("plus aucun bleu iOS #007aff", "#007aff" not in html and "#0a84ff" not in html)
check("dark mode non noir pur", "--bg:#0f1115" in html and "--bg:#000" not in html)
check("échelle d'ombres --sh-1/--sh-2", "--sh-1:" in html and "--sh-2:" in html)
check("rayons tokenisés --r-lg", "--r-lg:20px" in html)
check("courbes d'animation tokenisées --ease-out", "--ease-out:cubic-bezier" in html)
check("cartes avec bordure + ombre tokenisée",
      "border-radius:var(--r-lg)" in html and "box-shadow:var(--sh-1)" in html)

print("=== Dégradé émotionnel (source unique) ===")
for i in range(1, 6):
    check(f"--mood{i} défini (clair et sombre)", html.count(f"--mood{i}:") >= 2, html.count(f"--mood{i}:"))
    check(f"--mood{i}-soft défini", f"--mood{i}-soft:" in html)
check("colorH() utilise les tokens (plus de hex en dur)",
      "function colorH(v){ return 'var(--mood'" in html)
check("pastilles teintées via --mood/--mood-soft",
      "--mood:var(--mood" in html and "--mood-soft:var(--mood" in html)
check("calendrier teinté par data-h",
      all(f'.cal-d[data-h="{i}"]' in html for i in range(1, 6)))

print("=== L2 · Sélecteur d'humeur ===")
check("pastille circulaire (border-radius:50%)", ".qt .e{width:52px;height:52px;border-radius:50%" in html)
check("anneau de sélection (box-shadow triple)", "0 0 0 3px var(--card),0 0 0 6px var(--mood)" in html)
check("animation moodPop", "@keyframes moodPop" in html)
check("vibration au tap", "navigator.vibrate(8)" in html)

print("=== L3 · Typo, titres, micro-interactions ===")
h2 = re.findall(r"<h2[^>]*>([^<]*)</h2>", html)
check("aucun émoji dans les titres h2",
      not any(re.search(r"[\U0001F300-\U0001FAFF\u2600-\u27BF\uFE0F]", t) for t in h2), h2)
check("h2 en majuscules espacées 13px", "font-size:13px" in html and "letter-spacing:.06em" in html)
check("animation fadeUp (plus de fadeIn orpheline)",
      "@keyframes fadeUp" in html and "animation:fadeIn" not in html)
check("cascade des cartes", ".card:nth-child(2){animation-delay:40ms}" in html)
check("toast animé", "@keyframes toast" in html)
check("spinner d'enregistrement", ".sb[data-busy]:after" in html and "@keyframes spin" in html)
check("respect de prefers-reduced-motion", "prefers-reduced-motion:reduce" in html)
check("plus de scale(.9) brut sur .qt", ".qt:active .e{transform:scale(.92)}" in html)

print("=== L4 · Calendrier ===")
check("cellules carrées (aspect-ratio)", "aspect-ratio:1/1" in html)
check("légende dégradé du calendrier",
      "cal-legend" in html and "linear-gradient(90deg,var(--mood1)" in html)
check("teintes par niveau conservées", all(f'.cal-d[data-h="{i}"]' in html for i in range(1, 6)))

print("=== L5 · Stats SVG ===")
check("anneau de progression (SVG + .ring-fg)", "ring-fg" in html and 'viewBox="0 0 36 36"' in html)
check("valeur au centre de l'anneau (.ring-mid)", "ring-mid" in html)
check("courbe de tendance (sparkline)", "spark-line" in html and "@keyframes draw" in html)
check("carte 30 derniers jours", 'id="stats-spark"' in html and "30 derniers jours" in html)
check("série journalière exposée par /stats", '"series": series' in src or '"series":series' in src)

print("=== Cohérence CSS ===")
used = set(re.findall(r"var\((--[a-z0-9-]+)", html))
defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", html))
# --mood et --mood-soft sont posées inline par buildPicker()
missing = sorted(used - defined - {"--mood", "--mood-soft"})
check("aucune variable CSS utilisée sans définition", not missing, missing)

print(f"\n=== RESULTAT DESIGN: {ok} OK, {fail} échec(s) ===")
sys.exit(1 if fail else 0)
