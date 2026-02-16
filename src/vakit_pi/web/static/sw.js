// Vakit-Pi Service Worker
// Network-first strategy: always fetch fresh content, cache as fallback

const CACHE_NAME = "vakit-pi-v1";

// Install event - precache shell
self.addEventListener("install", (event) => {
  console.log("Service Worker: Installing...");
  // Skip waiting to activate immediately
  self.skipWaiting();
});

// Activate event - clean old caches
self.addEventListener("activate", (event) => {
  console.log("Service Worker: Activating...");
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => {
            console.log("Service Worker: Deleting old cache:", name);
            return caches.delete(name);
          })
      );
    }).then(() => self.clients.claim())
  );
});

// Fetch event - network first, cache fallback
self.addEventListener("fetch", (event) => {
  const request = event.request;

  // Only cache GET requests
  if (request.method !== "GET") {
    return;
  }

  // Skip API calls and external resources from caching
  const url = new URL(request.url);
  if (url.pathname.startsWith("/api/") || url.origin !== self.location.origin) {
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        // Clone and cache successful responses
        if (response.ok) {
          const responseClone = response.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseClone);
          });
        }
        return response;
      })
      .catch(() => {
        // Network failed, try cache
        return caches.match(request);
      })
  );
});
