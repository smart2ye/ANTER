const CACHE_NAME = 'anter-v2';
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
      .then(cache => cache.addAll(urlsToCache))
      .then(() => self.skipWaiting())
  );
});

// استرجاع الملفات
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request).catch(() => caches.match(OFFLINE_URL)))
  );
});

// تفعيل
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

// ==============================
// الإشعارات الخارجية (Web Push)
// ==============================
self.addEventListener('push', event => {
  let data = {};
  try {
    data = event.data.json();
  } catch {
    data = { title: 'ANTER', body: 'لديك إشعار جديد' };
  }

  const options = {
    body: data.body || 'لديك إشعار جديد',
    icon: data.icon || '/static/icons/anter-icon-512.png',
    badge: '/static/uploads/default.png',
    vibrate: [100, 50, 100],
    data: {
      url: data.url || '/'
    }
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'ANTER', options)
  );
});

// عند النقر على الإشعار
self.addEventListener('notificationclick', event => {
  event.notification.close();
  const url = event.notification.data?.url || '/';
  event.waitUntil(
    clients.matchAll({ type: 'window' }).then(windowClients => {
      for (let client of windowClients) {
        if (client.url === url && 'focus' in client) {
          return client.focus();
        }
      }
      if (clients.openWindow) {
        return clients.openWindow(url);
      }
    })
  );
});
