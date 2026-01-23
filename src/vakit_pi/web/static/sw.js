// Vakit-Pi Service Worker
// Minimal service worker for PWA compliance (no caching as per requirements)

// Install event - required for service worker
self.addEventListener('install', (event) => {
  console.log('Service Worker: Installing...');
  // Skip waiting to activate immediately
  self.skipWaiting();
});

// Activate event - required for service worker
self.addEventListener('activate', (event) => {
  console.log('Service Worker: Activating...');
  // Claim clients immediately
  event.waitUntil(self.clients.claim());
});

// Fetch event - pass through all requests without caching
self.addEventListener('fetch', (event) => {
  // Simply pass through all requests to the network
  // No caching as per requirements
  event.respondWith(fetch(event.request));
});
