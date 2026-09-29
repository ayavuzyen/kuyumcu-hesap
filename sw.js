/* Uygulama kabuğunu önbelleğe alır: internet yokken de hesap çalışır.
 * Önce ağ: yeni sürüm yayınlanınca bir sonraki açılışta gelir.
 * Fiyat dosyalarına dokunmaz; onları sayfa kendisi doğrulayıp saklar. */
importScripts("hesap.js");                       // sürüm tek kaynaktan
const SURUM = "altin-takas-" + self.Hesap.SURUM;
const KABUK = ["./", "index.html", "hesap.js", "manifest.webmanifest", "ikon-192.png", "ikon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(SURUM).then((c) => c.addAll(KABUK)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== SURUM).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.origin !== location.origin || u.pathname.endsWith("fiyatlar.json")) return;
  e.respondWith(
    fetch(e.request).then((r) => {
      if (r.ok) { const k = r.clone(); caches.open(SURUM).then((c) => c.put(e.request, k)); }
      return r;
    }).catch(() => caches.match(e.request, { ignoreSearch: true }).then((r) => r || caches.match("index.html")))
  );
});
