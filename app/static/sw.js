const CACHE_NAME = "lello-pwa-cache-v1";

self.addEventListener('install', (e) => self.skipWaiting());
self.addEventListener('activate', (e) => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', (e) => {
    // Escuta a rede sem interferir no seu sistema
});