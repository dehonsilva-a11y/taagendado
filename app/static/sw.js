const CACHE_NAME = "lello-pwa-cache-v1";

// 1. Instalação: O navegador reconhece o app
self.addEventListener("install", (e) => {
  self.skipWaiting(); // Força a atualização imediata
});

// 2. Ativação: Limpa caches velhos
self.addEventListener("activate", (e) => {
  e.waitUntil(self.clients.claim());
});

// 3. O SEGREDO DO CHROME: É obrigatório ter o evento 'fetch' real para liberar a instalação
self.addEventListener("fetch", (e) => {
  e.respondWith(
    fetch(e.request).catch(() => {
      // Se a pessoa estiver sem internet, ele retorna algo vazio em vez de erro fatal
      return new Response("Você está offline.");
    }),
  );
});
