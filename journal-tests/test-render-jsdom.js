// Test rendu journal avec jsdom (simulation navigateur complet sans browser)
// Verifie que les 8 onglets generent du contenu et que les clics activent les panes
// Necessite : serveur journal actif sur http://localhost:8090
// Necessite : jsdom (dispo via ~/.hermes/hermes-agent/node_modules/jsdom)
// Usage: node ~/.hermes/skills/software-development/journal/scripts/test-render-jsdom.js

const { JSDOM } = require('/home/ubuntu/.hermes/hermes-agent/node_modules/jsdom');
const http = require('http');

function fetch(url) {
  return new Promise((resolve, reject) => {
    http.get(url, (res) => {
      let data = '';
      res.on('data', (c) => data += c);
      res.on('end', () => resolve(data));
    }).on('error', reject);
  });
}

(async () => {
  const html = await fetch('http://localhost:8090/');
  const edition = JSON.parse(await fetch('http://localhost:8090/api/data'));
  console.log('Page + API chargees');

  // Creer DOM + mocker XHR AVANT execution des scripts de la page
  const dom = new JSDOM(html, {
    url: 'http://localhost:8090/',
    runScripts: 'dangerously',
    resources: 'usable',
    pretendToBeVisual: true,
    beforeParse(window) {
      class MockXHR {
        open(method, url) { this.url = url; }
        setRequestHeader() {}
        send() {
          const self = this;
          setTimeout(() => {
            this.status = 200;
            this.responseText = this.url.includes('/api/data')
              ? JSON.stringify(edition) : '{}';
            if (self.onload) self.onload();
          }, 10);
        }
      }
      window.XMLHttpRequest = MockXHR;
      window.__render_errors = [];
      window.addEventListener('error', (e) =>
        window.__render_errors.push(e.message || String(e)));
    }
  });

  const doc = dom.window.document;

  // Attendre que le JS de la page charge et execute render()
  await new Promise(r => setTimeout(r, 1000));

  // 1. Verifier que les 8 panes existent et ont du contenu
  const panes = doc.querySelectorAll('.pane');
  console.log('\nPanes creees:', panes.length);
  let failures = 0;

  for (let i = 0; i < panes.length; i++) {
    const pane = panes[i];
    const contentLen = pane.innerHTML.length;
    const ok = contentLen > 0;
    if (!ok) failures++;
    console.log(`${ok ? 'PASS' : 'FAIL'} ${pane.id}: ${contentLen} chars`);
  }

  // 2. Simuler un clic sur chaque onglet → verifier que la pane devient active
  const TAB_NAMES = ['une', 'newsletters', 'youtube',
    'echecs', 'techno', 'crypto', 'immobilier', 'agenda', 'reddit'];

  for (const tabName of TAB_NAMES) {
    const tab = doc.querySelector(`[data-tab="${tabName}"]`);
    if (!tab) {
      console.log(`FAIL Onglet ${tabName}: introuvable`);
      failures++;
      continue;
    }
    tab.click();
    await new Promise(r => setTimeout(r, 50));

    const pane = doc.getElementById(`pane-${tabName}`);
    const isActive = pane && pane.classList.contains('active');
    const hasContent = pane && pane.innerHTML.length > 0;

    if (!isActive) { console.log(`FAIL clic ${tabName}: pane pas active`); failures++; }
    else if (!hasContent) { console.log(`FAIL clic ${tabName}: pane active mais vide`); failures++; }
    else { console.log(`PASS clic ${tabName}: active + contenu`); }
  }

  // 3. Afficher les erreurs JS capturees
  if (dom.window.__render_errors.length) {
    console.log('\nERREURS JS:');
    dom.window.__render_errors.forEach(e => console.log('  ' + e));
    process.exit(1);
  }

  console.log(`\n=== ${failures ? 'ECHEC: ' + failures + ' defaut(s)' : 'TOUT OK'} ===`);
  process.exit(failures ? 1 : 0);
})().catch(e => {
  console.error('ERREUR:', e.message);
  process.exit(1);
});