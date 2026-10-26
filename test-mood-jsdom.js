#!/usr/bin/env node
/**
 * Test runtime du JS de Mood Tracker v2 via jsdom.
 * Charge la vraie page, mocke fetch, exécute tout le JS, puis :
 *  - vérifie le rendu (5 humeurs, streak, tendance, onglets)
 *  - simule un tap sur une humeur -> doit émettre un POST /save {humeur:N}
 *  - ouvre le calendrier et les stats
 * Usage : node ~/.hermes/scripts/test-mood-jsdom.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM, VirtualConsole } = require('jsdom');

const SERVER = process.env.MOOD_SERVER || '/home/ubuntu/.hermes/scripts/mood-server.py';

// --- extraire la chaîne HTML du serveur ---
const src = fs.readFileSync(SERVER, 'utf8');
const start = src.indexOf('HTML = r"""') + 'HTML = r"""'.length;
const end = src.indexOf('"""', start);
const html = src.slice(start, end);

let ok = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { ok++; console.log('  ✅ ' + name); }
  else { fail++; console.log('  ❌ ' + name + (detail ? '  ' + detail : '')); }
}

// --- données mockées ---
const DATA = {
  entries: [{ date: '2026-10-25', humeur: 4, text: '🎯 Sport — 📚 Dune', note: 'belle journée' }],
  trend: [
    { d: '2026-10-20', h: 3 }, { d: '2026-10-21', h: null }, { d: '2026-10-22', h: 5 },
    { d: '2026-10-23', h: 2 }, { d: '2026-10-24', h: 4 }, { d: '2026-10-25', h: 4 },
    { d: '2026-10-26', h: null },
  ],
  today: { date: '2026-10-26', version: 2, humeur: 3, energie: 2, etats: ['fatigue'],
           activites: ['lecture'], lecture: 'Hawkmoon', serie: '', notes: '' },
  streak: 4, record: 7,
  meta: {
    moods: [{v:1,e:'😞',l:'Très mal'},{v:2,e:'🙁',l:'Mal'},{v:3,e:'😐',l:'Neutre'},{v:4,e:'🙂',l:'Bien'},{v:5,e:'😄',l:'Très bien'}],
    etats: [{k:'fatigue',l:'Fatigué',e:'😴'},{k:'malade',l:'Malade',e:'🤒'}],
    activites: [{k:'lecture',l:'Lecture',e:'📖'},{k:'sport',l:'Sport',e:'🏃'}],
  },
};
const STATS = { total: 9, avg: 3.11, median: 3, best: 5, worst: 2, streak: 4, record: 7, m7: 3.4, delta: 0.8,
  dist: [{v:2,c:3,l:'Mal'},{v:3,c:4,l:'Neutre'},{v:5,c:2,l:'Très bien'}],
  monthly: [{label:'2026-09',avg:3.5},{label:'2026-10',avg:3.2}],
  corr: [{label:'Sport',avg:4.5,n:2},{label:'Lecture',avg:3.0,n:1}] };
const CAL = { year: 2026, month: 9, month_name: 'Octobre', offset: 3,
  days: Array.from({length: 31}, (_, i) => ({ day: i + 1, wd: 0, humeur: i === 25 ? 3 : null })) };

const SEARCH = { q: 'silo', count: 1, results: [{ date: '2026-07-28', humeur: 2, etats: [], activites: [], lecture: '', serie: 'Silo S3E2', notes: 'épisode final' }] };

const calls = [];
function mockFetch(url, opts) {
  calls.push({ url, opts });
  let body = {};
  if (url.indexOf('/data') === 0) body = DATA;
  else if (url.indexOf('/stats') === 0) body = STATS;
  else if (url.indexOf('/calendar') === 0) body = CAL;
  else if (url.indexOf('/search') === 0) body = SEARCH;
  else if (url.indexOf('/get-entry') === 0) body = { found: true, entry: DATA.today };
  else if (url.indexOf('/save') === 0) body = { ok: true };
  else if (url.indexOf('/update') === 0) body = { ok: true };
  else if (url.indexOf('/delete') === 0) body = { ok: true };
  return Promise.resolve({ ok: true, json: () => Promise.resolve(body), blob: () => Promise.resolve({}) });
}

const vc = new VirtualConsole();
vc.on('jsdomError', (e) => { console.log('  ⚠️  jsdomError:', e.message); });

const dom = new JSDOM(html, {
  runScripts: 'dangerously',
  pretendToBeVisual: true,
  virtualConsole: vc,
  url: 'http://127.0.0.1:8099/',
  beforeParse(window) {
    window.fetch = mockFetch;
    if (!window.matchMedia) {
      window.matchMedia = () => ({ matches: false, addEventListener() {}, addListener() {}, removeEventListener() {} });
    }
  },
});
dom.window.fetch = mockFetch;
dom.window.confirm = () => true;
dom.window.alert = () => {};

setTimeout(() => {
  const w = dom.window, doc = w.document;
  console.log('=== Rendu initial ===');
  check('5 boutons d\'humeur rendus', doc.querySelectorAll('#q1t .qt').length === 5,
        doc.querySelectorAll('#q1t .qt').length);
  const labels = Array.from(doc.querySelectorAll('#q1t .qt .l')).map(e => e.textContent);
  check('libellés humeur corrects', labels.join('|') === 'Très mal|Mal|Neutre|Bien|Très bien', labels.join('|'));
  check('5 boutons énergie', doc.querySelectorAll('#energy .eb').length === 5);
  check('tags états rendus', doc.querySelectorAll('#etats .chip').length === 2);
  check('tags activités + « Ajouter »', doc.querySelectorAll('#activites .chip').length === 3);
  check('streak affiché', /🔥 4 j/.test(doc.getElementById('streak').textContent), doc.getElementById('streak').textContent);
  check('tendance 7 jours rendue', doc.querySelectorAll('#trend .hd').length === 7);
  check('historique rendu', doc.querySelectorAll('#hist .hp').length >= 1);
  check('humeur du jour présélectionnée (3)', doc.querySelectorAll('#q1t .qt.sel').length === 1
        && doc.querySelector('#q1t .qt.sel').dataset.v === '3');
  check('énergie du jour présélectionnée (2)', doc.querySelector('#energy .eb.sel') &&
        doc.querySelector('#energy .eb.sel').dataset.v === '2');
  check('lecture préremplie', doc.getElementById('lecture').value === 'Hawkmoon');
  check('3 onglets + recherche = 4', doc.querySelectorAll('.tab').length === 4, doc.querySelectorAll('.tab').length);
  check('panes cohérentes (4)', doc.querySelectorAll('.tab-c').length === 4, doc.querySelectorAll('.tab-c').length);

  console.log('=== 1-tap : clic sur « Bien » (4) ===');
  const before = calls.length;
  const target = Array.from(doc.querySelectorAll('#q1t .qt')).find(e => e.dataset.v === '4');
  target.dispatchEvent(new w.MouseEvent('click', { bubbles: true }));
  setTimeout(() => {
    const saveCalls = calls.slice(before).filter(c => c.url.indexOf('/save') === 0);
    check('un POST /save émis', saveCalls.length >= 1, saveCalls.length);
    let payload = null;
    if (saveCalls.length) payload = JSON.parse(saveCalls[0].opts.body);
    check('payload = {humeur:4} (aucun autre champ écrasé)', payload && payload.humeur === 4
          && Object.keys(payload).length === 1, JSON.stringify(payload));

    console.log('=== Calendrier ===');
    w.swTab('cal');
    setTimeout(() => {
      check('titre du mois = Octobre 2026', doc.getElementById('cal-title').textContent === 'Octobre 2026',
            doc.getElementById('cal-title').textContent);
      check('grille calendrier rendue (offset 3 + jours)', doc.querySelectorAll('#cal-grid .cal-d').length >= 28);

      console.log('=== Stats ===');
      w.swTab('stats');
      setTimeout(() => {
        const sum = doc.getElementById('stats-summary').textContent;
        check('moyenne affichée', /3\.1/.test(sum), sum.slice(0, 80));
        check('record affiché', /7/.test(sum));
        check('répartition rendue', doc.querySelectorAll('#stats-dist .stat-leg > span').length === 3,
              'spans=' + doc.querySelectorAll('#stats-dist .stat-leg > span').length);
        check('corrélation rendue', doc.querySelectorAll('#stats-corr .corr-row').length === 2);
        const trendTxt = doc.getElementById('stats-trend').textContent;
        check('libellés de tendance lisibles (mois abrégés)',
              /sept\. 26/.test(trendTxt) && /oct\. 26/.test(trendTxt), trendTxt);
        check('meilleure/pire avec libellé texte',
              /Meilleure/.test(sum + doc.getElementById('stats-summary').innerHTML)
              && /Très bien/.test(doc.getElementById('stats-summary').innerHTML),
              doc.getElementById('stats-summary').textContent);

        console.log('=== Recherche ===');
        doc.getElementById('q').value = 'silo';
        w.doSearch();
        setTimeout(() => {
          const sr = doc.getElementById('search-results');
          check('résultats de recherche rendus', doc.querySelectorAll('#search-results .hp').length === 1,
                sr.textContent.slice(0, 60));
          check('résultat cliquable (openEdit)', /openEdit\(/.test(sr.innerHTML));

          console.log('\n=== RESULTAT JS: ' + ok + ' OK, ' + fail + ' échec(s) ===');
          process.exit(fail ? 1 : 0);
        }, 200);
      }, 150);
    }, 150);
  }, 150);
}, 400);
