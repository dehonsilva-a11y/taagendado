self.addEventListener('install', (e) => {
    console.log('[Service Worker] Instalado com sucesso.');
});

self.addEventListener('fetch', (e) => {
    // Escuta as requisições para o Android reconhecer como um PWA válido
});