const VERSION = "noh-guide-v2";
self.addEventListener("install", event => {
  event.waitUntil(Promise.resolve());
  self.skipWaiting();
});
self.addEventListener("activate", event => {
  event.waitUntil(Promise.all([
    caches.keys().then(keys => Promise.all(keys.map(key => caches.delete(key)))),
    self.clients.claim()
  ]));
});
// No offline cache: every page and data request must pass through Cloudflare Access.
