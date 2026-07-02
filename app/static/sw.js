const CACHE_NAME = 'anter-v1';
const OFFLINE_URL = '/offline.html';
const urlsToCache = [
  '/',
  '/static/css/style.css',
  '/static/js/main.js',
  '/static/uploads/default.png',
  '/static/icons/anter-icon-512.png',
  OFFLINE_URL
];

// تثبيت Service Worker
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Cache opened');
        return cache.addAll(urlsToCache);
      })
      .then(() => self.skipWaiting())
  );
});

// استرجاع الملفات (Cache First)
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        if (response) {
          return response;
        }
        return fetch(event.request)
          .catch(() => {
            return caches.match(OFFLINE_URL);
          });
      })
  );
});

// تنشيط وتنظيف الكاش القديم
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(name => name !== CACHE_NAME)
          .map(name => caches.delete(name))
      );
    }).then(() => self.clients.claim())
  );
});
