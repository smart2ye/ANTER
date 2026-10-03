/* ============================================================
   ANTER Service Worker — v5
   - Cache-First للأصول الثابتة (CSS/JS/أيقونات/خطوط).
   - Network-First لصفحات HTML (يضمن رؤية آخر المنشورات).
   - يتجاهل تمامًا: /api/, /messages/, /notifications/, /sse/, /calls/, /media/.
   - يدعم الإشعارات الخارجية (Web Push).
   ============================================================ */

const CACHE_VERSION = 'anter-v5';
const OFFLINE_URL = '/static/offline.html';

// مسارات لن تُخزَّن أبدًا (بيانات حيّة أو حساسة).
const NEVER_CACHE = [
  '/api/',
  '/messages/',
  '/notifications/',
  '/sse/',
  '/media/',
  '/auth/',
  '/admin/',
  '/calls/',
];

const PRECACHE = [
  '/static/css/style.css',
  '/static/css/stories.css',
  '/static/js/main.js',
  '/static/js/stories.js',
  '/static/icons/icon-192.png',
  '/static/icons/icon-512.png',
  OFFLINE_URL,
];

// ============================================================
// Install — تخزين مسبق للأصول الأساسية
// ============================================================
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      .then((cache) => Promise.all(
        PRECACHE.map((url) => cache.add(url).catch(() => null))
      ))
      .then(() => self.skipWaiting())
  );
});

// ============================================================
// Activate — حذف الكاشات القديمة
// ============================================================
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys()
      .then((names) => Promise.all(
        names
          .filter((name) => name !== CACHE_VERSION)
          .map((name) => caches.delete(name))
      ))
      .then(() => self.clients.claim())
  );
});

// ============================================================
// Fetch — استراتيجيات حسب نوع الطلب
// ============================================================
self.addEventListener('fetch', (event) => {
  const req = event.request;

  // نتعامل فقط مع GET
  if (req.method !== 'GET') return;

  const url = new URL(req.url);

  // نفس الأصل فقط
  if (url.origin !== self.location.origin) return;

  // تجاهل المسارات الحيّة/الحساسة
  for (const prefix of NEVER_CACHE) {
    if (url.pathname.startsWith(prefix)) return;
  }

  // صفحات HTML: Network-First (نريد آخر نسخة)
  const accept = req.headers.get('accept') || '';
  if (accept.includes('text/html')) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          // نُخزّن نسخة احتياطية إن كان الرد سليمًا
          const copy = res.clone();
          caches.open(CACHE_VERSION).then((c) => c.put(req, copy)).catch(() => {});
          return res;
        })
        .catch(() => caches.match(req).then((r) => r || caches.match(OFFLINE_URL)))
    );
    return;
  }

  // الأصول الثابتة (CSS/JS/صور/خطوط): Cache-First
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then((cached) => {
        if (cached) return cached;
        return fetch(req).then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(CACHE_VERSION).then((c) => c.put(req, copy)).catch(() => {});
          }
          return res;
        }).catch(() => cached);
      })
    );
    return;
  }

  // أي شيء آخر: نُمرّره بدون تخزين
});

// ============================================================
// Web Push — استقبال الإشعارات
// ============================================================
self.addEventListener('push', (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = { title: 'ANTER', body: 'لديك إشعار جديد' };
  }

  const options = {
    body: data.body || 'لديك إشعار جديد',
    icon: data.icon || '/static/icons/icon-192.png',
    badge: '/static/icons/icon-192.png',
    dir: 'rtl',
    lang: 'ar',
    data: { url: data.url || '/' },
  };

  event.waitUntil(
    self.registration.showNotification(data.title || 'ANTER', options)
  );
});

// ============================================================
// notificationclick — فتح التطبيق عند النقر
// ============================================================
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = event.notification.data?.url || '/';

  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((list) => {
        for (const client of list) {
          if (client.url.includes(url) && 'focus' in client) return client.focus();
        }
        if (clients.openWindow) return clients.openWindow(url);
      })
  );
});


// ============================================================
// message — قبول أوامر من الصفحة (SKIP_WAITING)
// ============================================================
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});
