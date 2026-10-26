/* Service worker Mood Tracker — app shell + dernière réponse API en cache. */
var CACHE = 'mood-v2-3';
var SHELL = ['/', '/manifest.json', '/icon-192.png', '/icon-512.png', '/apple-touch-icon.png'];

self.addEventListener('install', function (e) {
  e.waitUntil(caches.open(CACHE).then(function (c) { return c.addAll(SHELL); }).then(function () { return self.skipWaiting(); }));
});

self.addEventListener('activate', function (e) {
  e.waitUntil(caches.keys().then(function (ks) {
    return Promise.all(ks.filter(function (k) { return k !== CACHE; }).map(function (k) { return caches.delete(k); }));
  }).then(function () { return self.clients.claim(); }));
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  var url = new URL(req.url);
  if (url.origin !== location.origin || req.method !== 'GET') return;

  var apiPath = (url.pathname === '/data' || url.pathname === '/stats' ||
                 url.pathname === '/calendar' || url.pathname === '/get-entry');
  // Le document HTML est TOUJOURS pris au réseau : on ne sert jamais une page périmée.
  if (req.mode === 'navigate' || url.pathname === '/') {
    e.respondWith(
      fetch(req).then(function (r) {
        var cl = r.clone();
        caches.open(CACHE).then(function (c) { c.put('/', cl); });
        return r;
      }).catch(function () {
        return caches.match('/').then(function (m) {
          return m || caches.match(req);
        });
      })
    );
    return;
  }
  if (apiPath) {
    // réseau d'abord, cache en secours (hors-ligne -> dernière réponse connue)
    e.respondWith(
      fetch(req).then(function (r) {
        var cl = r.clone();
        caches.open(CACHE).then(function (c) { c.put(req, cl); });
        return r;
      }).catch(function () {
        return caches.match(req).then(function (m) {
          return m || new Response('{"offline":true}', { headers: { 'Content-Type': 'application/json' } });
        });
      })
    );
    return;
  }
  // app shell : cache d'abord
  e.respondWith(caches.match(req).then(function (m) { return m || fetch(req); }));
});
