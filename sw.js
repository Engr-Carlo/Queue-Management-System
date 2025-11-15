// Service Worker for Background Queue Monitoring (Non-PWA Version)
// This runs in background without requiring app installation

const CACHE_NAME = 'queue-system-v1';
const API_BASE_URL = 'https://qms-coe-backend.onrender.com'; // Replace with your actual API URL

// Install service worker
self.addEventListener('install', (event) => {
  console.log('[SW] Service Worker installing for background notifications');
  self.skipWaiting();
});

// Activate service worker
self.addEventListener('activate', (event) => {
  console.log('[SW] Service Worker activated for background monitoring');
  event.waitUntil(clients.claim());
});

// Background queue checking function
async function checkQueueStatusInBackground(queueId) {
  try {
    const response = await fetch(`${API_BASE_URL}/queue/${queueId}/status`);
    if (!response.ok) return null;
    
    const statusData = await response.json();
    
    // If queue is called, send notification
    if (statusData.is_called) {
      await sendNotificationToUser(statusData);
    }
    
    return statusData;
  } catch (error) {
    console.error('Background queue check failed:', error);
    return null;
  }
}

// Send notification to user
async function sendNotificationToUser(statusData) {
  try {
    // Show browser notification
    const notification = new Notification('Queue Alert!', {
      body: `Your queue number is being called! Please proceed to the office.`,
      icon: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNjQiIGhlaWdodD0iNjQiIHZpZXdCb3g9IjAgMCA2NCA2NCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjY0IiBoZWlnaHQ9IjY0IiByeD0iMTYiIGZpbGw9IiNEQzI2MjYiLz4KPHN2ZyB4PSIxNiIgeT0iMTYiIHdpZHRoPSIzMiIgaGVpZ2h0PSIzMiIgdmlld0JveD0iMCAwIDI0IDI0IiBmaWxsPSJ3aGl0ZSI+CjxwYXRoIGQ9Im0xMiAyIDMuMDkgNi4yNkwyMiA5bC0xLjUxIDMuNzQgNCA0LTMuNzQgMS41MUw5IDIybC00LTQgMy43NC0xLjUxTDIgMTJsMy4wOS02LjI2TDEyIDJ6Ii8+Cjwvc3ZnPgo8L3N2Zz4K',
      badge: 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzIiIGhlaWdodD0iMzIiIHZpZXdCb3g9IjAgMCAzMiAzMiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHJlY3Qgd2lkdGg9IjMyIiBoZWlnaHQ9IjMyIiByeD0iOCIgZmlsbD0iI0RDMjYyNiIvPgo8dGV4dCB4PSIxNiIgeT0iMjAiIHRleHQtYW5jaG9yPSJtaWRkbGUiIGZpbGw9IndoaXRlIiBmb250LXNpemU9IjE0Ij7wn5qoPC90ZXh0Pgo8L3N2Zz4K',
      vibrate: [200, 100, 200, 100, 200],
      requireInteraction: true,
      actions: [
        {
          action: 'view',
          title: 'View Queue'
        }
      ]
    });
    
    // Handle notification click
    notification.onclick = () => {
      clients.openWindow(`/queue-status.html?id=${statusData.queue_id || ''}`);
      notification.close();
    };
    
    console.log('🔔 Background notification sent successfully');
    
  } catch (error) {
    console.error('Failed to send background notification:', error);
  }
}

// Listen for messages from main page
self.addEventListener('message', async (event) => {
  const { type, queueId } = event.data;
  
  if (type === 'START_MONITORING' && queueId) {
    console.log(`[SW] Starting background monitoring for queue: ${queueId}`);
    
    // Start periodic background checking
    setInterval(async () => {
      await checkQueueStatusInBackground(queueId);
    }, 15000); // Check every 15 seconds
    
    // Send confirmation back to main page
    event.ports[0].postMessage({ 
      type: 'MONITORING_STARTED',
      success: true 
    });
  }
});

// Background sync for offline support
self.addEventListener('sync', (event) => {
  if (event.tag === 'queue-check') {
    console.log('[SW] Background sync: Checking queue status');
    // Implement queue checking logic here
  }
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  
  if (event.action === 'view') {
    // Open the queue status page
    event.waitUntil(
      clients.openWindow('/queue-status.html')
    );
  }
});
