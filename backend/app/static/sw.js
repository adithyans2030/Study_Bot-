// StudyBot service worker: makes the app installable and lets its page open even when the server is
// unreachable (so the phone can say "your computer is off" instead of showing a browser error).
//
// It caches only the app's own static files. Nothing under /api/ is ever cached or answered here:
// answers, documents and sign-in state always come live from the server, so a stale or shared copy
// of somebody's private data can never be shown.
const CACHE = 'studybot-shell-v2';
const SHELL = ['/', '/static/app.js', '/static/rich.js', '/static/style.css', '/manifest.webmanifest',
  '/static/icons/icon-192.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);
  if (request.method !== 'GET' || url.origin !== self.location.origin || url.pathname.startsWith('/api/')) return;

  // Network first, so updates arrive immediately; the cached copy is only the offline fallback.
  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      })
      .catch(() => caches.match(request).then((hit) => hit || (request.mode === 'navigate' ? caches.match('/') : Response.error()))));
});
