// Test de l'onglet Crypto du journal — rendu reel + cas limites.
// Necessite : serveur journal actif sur http://localhost:8090 et jsdom.
// Le JS de la page est encapsule dans un IIFE : on teste donc via le DOM,
// en injectant une edition reelle ou synthetique dans le XHR mocke.
// Chaque instance JSDOM est fermee apres usage (plusieurs simultanees se genent).
// Usage: node ~/.hermes/journal-tests/test-crypto-jsdom.js

const { JSDOM } = require('/home/ubuntu/.hermes/hermes-agent/node_modules/jsdom');
const http = require('http');

let ok = 0, ko = 0;
function check(name, cond, detail) {
  if (cond) { ok++; console.log('PASS ' + name); }
  else { ko++; console.log('FAIL ' + name + (detail ? ' -> ' + detail : '')); }
}

function fetch(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => { let d = ''; res.on('data', c => d += c); res.on('end', () => resolve(d)); })
      .on('error', reject);
  });
}

async function mount(html, edition) {
  const dom = new JSDOM(html, {
    url: 'http://localhost:8090/',
    runScripts: 'dangerously',
    resources: 'usable',
    pretendToBeVisual: true,
    beforeParse(window) {
      class MockXHR {
        open(m, u) { this.url = u; }
        setRequestHeader() {}
        send() {
          const self = this;
          setTimeout(() => {
            this.status = 200;
            this.responseText = this.url.indexOf('/api/data') >= 0
              ? JSON.stringify(edition) : '{}';
            if (self.onload) self.onload();
          }, 10);
        }
      }
      window.XMLHttpRequest = MockXHR;
      window.__errs = [];
      window.addEventListener('error', e => window.__errs.push(e.message || String(e)));
    }
  });
  await new Promise(r => setTimeout(r, 1200));
  return { doc: dom.window.document, win: dom.window, dom };
}

(async () => {
  const html = await fetch('http://localhost:8090/');
  const edition = JSON.parse(await fetch('http://localhost:8090/api/data'));
  const sec = edition.sections.crypto || {};

  // ── Phase 1 : edition reelle ──────────────────────────────────────────────
  console.log('=== Onglet Crypto : edition reelle ===');
  let m1 = await mount(html, edition);
  let doc = m1.doc;

  const tab = doc.querySelector('[data-tab="crypto"]');
  check('onglet Crypto present', !!tab);
  check('libelle "Crypto"', !!tab && /Crypto/.test(tab.textContent));

  const expected = (sec.watchlist || []).length + (sec.others || []).length;
  const badge = tab ? tab.querySelector('.badge') : null;
  check('badge = nombre de cryptos suivies (' + expected + ')',
        !!badge && badge.classList.contains('show') && badge.textContent === String(expected),
        badge ? badge.textContent : 'absent');

  const pane = doc.getElementById('pane-crypto');
  check('pane crypto presente et non vide', !!pane && pane.innerHTML.length > 100,
        pane ? pane.innerHTML.length + ' chars' : 'absente');

  const txt = pane ? pane.textContent : '';
  check('releve date affiche', /Releve/.test(txt), txt.slice(0, 80));
  check('cartes watchlist rendues (' + (sec.watchlist || []).length + ')',
        !!pane && pane.querySelectorAll('.ccard').length === (sec.watchlist || []).length,
        pane ? String(pane.querySelectorAll('.ccard').length) : '0');
  check('TAO en tete de la watchlist',
        !!pane && /TAO/.test((pane.querySelector('.ccard') || {}).textContent || ''));
  check('prix formate en $', /\$/.test(txt));
  check('variations affichees (>= 5 chips)', !!pane && pane.querySelectorAll('.cdelta').length >= 5,
        pane ? String(pane.querySelectorAll('.cdelta').length) : '0');
  check('bloc "Mouvements du jour"', /Mouvements du jour/.test(txt));
  check('chips mouvements (4 attendus)',
        !!pane && pane.querySelectorAll('.cmover').length === 4,
        pane ? String(pane.querySelectorAll('.cmover').length) : '0');
  check('bloc "Autres cryptos"', /Autres cryptos/.test(txt));
  check('lignes compactes des autres cryptos (' + (sec.others || []).length + ')',
        !!pane && pane.querySelectorAll('.crow').length === (sec.others || []).length,
        pane ? String(pane.querySelectorAll('.crow').length) : '0');
  check('pas de courbe tant que l\'historique est insuffisant',
        sec.history_days >= 7 ? true : /courbe en construction/.test(txt));
  check('chip de periode masque quand la variation est inconnue',
        sec.history_days >= 7 ? true : !/n\/d/.test(txt));
  check('note sur l\'historique en construction',
        sec.history_days >= 7 ? true : /Historique :/.test(txt));

  // Valeurs de non-regression capturees avant fermeture
  const tabsTotal = doc.querySelectorAll('.tab').length;
  const panesTotal = doc.querySelectorAll('.pane').length;
  const tickerItems = doc.querySelectorAll('#ticker .ticker-item').length;
  const errs1 = m1.win.__errs.slice();
  m1.dom.window.close();
  m1 = null;

  // ── Phase 2 : avec historique (donnees synthetiques) ──────────────────────
  console.log('=== Onglet Crypto : avec historique (donnees synthetiques) ===');
  const synth = JSON.parse(JSON.stringify(edition));
  synth.sections.crypto = {
    updated: sec.updated, history_days: 9,
    watchlist: [
      { symbol: 'TAO', price: 245.88, change_24h: -2.28, change_7d: 4.1,
        spark: [230, 235, 232, 240, 238, 244, 241, 246, 245] },
      { symbol: 'BTC', price: 79585, change_24h: -1.09, change_7d: -3.4,
        spark: [82000, 81500, 81200, 80800, 80400, 80100, 79900, 79700, 79585] }
    ],
    others: [{ symbol: 'SKY', price: 0.06, change_24h: 0.06 }],
    movers: { up: [{ symbol: 'SKY', change_24h: 0.06 }], down: [{ symbol: 'AAVE', change_24h: -4.16 }] }
  };
  const m2 = await mount(html, synth);
  const p2 = m2.doc.getElementById('pane-crypto');
  const t2 = p2 ? p2.textContent : '';
  check('sparklines SVG rendues (2 attendues)',
        !!p2 && p2.querySelectorAll('svg.cspark polyline').length === 2,
        p2 ? String(p2.querySelectorAll('svg.cspark polyline').length) : '0');
  check('etiquette "7 j" quand historique >= 7 jours', /7 j/.test(t2));
  check('variation 7 j chiffree', /7 j [+-]?\d/.test(t2),
        t2.match(/7 j [^\s]*/g) ? t2.match(/7 j [^\s]*/g).join(',') : '');
  check('plus de mention "courbe en construction"', !/courbe en construction/.test(t2));
  check('badge = 3 (2 watchlist + 1 autre)',
        (m2.doc.querySelector('[data-tab="crypto"] .badge') || {}).textContent === '3');
  check('aucune erreur JS avec historique', m2.win.__errs.length === 0, m2.win.__errs.join(' | '));
  m2.dom.window.close();

  // ── Phase 3 : degradation ────────────────────────────────────────────────
  console.log('=== Onglet Crypto : degradation ===');
  const empty = JSON.parse(JSON.stringify(edition));
  delete empty.sections.crypto;
  const m3 = await mount(html, empty);
  const pane3 = m3.doc.getElementById('pane-crypto');
  const t3 = pane3 ? pane3.textContent : '';
  check('section absente -> message explicite', /Donnees crypto indisponibles/.test(t3), t3.slice(0, 60));
  const badge3 = m3.doc.querySelector('[data-tab="crypto"] .badge');
  check('badge masque quand aucune donnee',
        !!badge3 && !badge3.classList.contains('show'),
        badge3 ? badge3.className : 'badge absent');
  check('aucune erreur JS sans section crypto', m3.win.__errs.length === 0, m3.win.__errs.join(' | '));
  m3.dom.window.close();

  // ── Non-regression ───────────────────────────────────────────────────────
  console.log('=== Non-regression ===');
  check('les 9 onglets sont presents', tabsTotal === 9, String(tabsTotal));
  check('les 9 panes existent', panesTotal === 9, String(panesTotal));
  check('le ticker crypto est conserve', tickerItems > 0, String(tickerItems));
  check('aucune erreur JS (edition reelle)', errs1.length === 0, errs1.join(' | '));

  console.log('\n=== RESULTAT CRYPTO: ' + ok + ' OK, ' + ko + ' echec(s) ===');
  process.exit(ko ? 1 : 0);
})().catch(e => { console.error('ERREUR:', e.message); process.exit(1); });
