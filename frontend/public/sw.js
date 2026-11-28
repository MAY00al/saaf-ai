// خدمة عمل بسيطة: تخزّن هيكل التطبيق فقط (الصفحة والأيقونات) ليفتح التطبيق بسرعة.
// طلبات الخادم (/api والصور المحلّلة) لا تُخزَّن أبداً حتى لا تظهر بيانات قديمة.
const CACHE = 'saaf-shell-v1';
const SHELL = ['/', '/logo.png', '/icon-192.png', '/manifest.webmanifest'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  const url = new URL(req.url);
  // نتعامل فقط مع طلبات GET من نفس الموقع؛ كل ما عداها (الخادم، الخرائط) يمر مباشرة
  if (req.method !== 'GET' || url.origin !== self.location.origin) return;
  // التنقل: الشبكة أولاً، وإن لم تتوفر نعرض الصفحة المخزّنة
  if (req.mode === 'navigate') {
    e.respondWith(fetch(req).catch(() => caches.match('/')));
    return;
  }
  // الملفات الثابتة: المخزّن أولاً مع تحديث بالخلفية
  e.respondWith(
    caches.match(req).then((hit) => {
      const net = fetch(req).then((res) => {
        if (res.ok) caches.open(CACHE).then((c) => c.put(req, res.clone()));
        return res;
      }).catch(() => hit);
      return hit || net;
    })
  );
});
