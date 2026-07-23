const CACHE_NAME = 'haroldsound-v1';
const AUDIO_CACHE = 'haroldsound-audio-v1';
const urlsToCache = [
  '/',
  '/static/index.html',
  '/static/style.css',
  '/static/app.js',
  '/static/manifest.json'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME && cacheName !== AUDIO_CACHE) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  // Manejar peticiones de audio MP3 (/descargas/)
  if (event.request.url.includes('/descargas/') && event.request.url.endsWith('.mp3')) {
    event.respondWith(
      caches.open(AUDIO_CACHE).then(cache => {
        return cache.match(event.request).then(response => {
          // Si está en caché (Offline), lo devuelve
          if (response) {
            return response;
          }
          // Si no, lo descarga y lo guarda en caché
          return fetch(event.request).then(networkResponse => {
            if(networkResponse && networkResponse.status === 200) {
              cache.put(event.request, networkResponse.clone());
            }
            return networkResponse;
          });
        });
      })
    );
  } else if (event.request.method === 'GET' && !event.request.url.includes('/api/') && !event.request.url.includes('/buscar')) {
    // App Shell caching (Network first, then Cache)
    event.respondWith(
      fetch(event.request).catch(() => caches.match(event.request))
    );
  } else {
    // API calls bypass cache
    event.respondWith(fetch(event.request));
  }
});
