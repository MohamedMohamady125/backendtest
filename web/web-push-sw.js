// web-push-sw.js - Service Worker for Push Notifications
console.log('🔧 Service Worker loaded');

// Handle push notification events
self.addEventListener('push', function(event) {
    console.log('📨 Push notification received:', event);
    
    let notificationData = {
        title: 'HFA Notification',
        body: 'You have a new message',
        icon: '/icons/Icon-192.png',
        badge: '/icons/Icon-96.png',
        image: '/icons/Icon-512.png',
        // ✅ ADD: Custom HFA sound for ALL notifications
        sound: '/sounds/hfasound.mp3',
        vibrate: [200, 100, 200], // Vibration pattern
        tag: 'hfa-notification',
        renotify: true,
        requireInteraction: false, // Auto-dismiss after few seconds
        actions: [
            {
                action: 'open',
                title: 'Open App',
                icon: '/icons/open.png'
            },
            {
                action: 'dismiss',
                title: 'Dismiss',
                icon: '/icons/dismiss.png'
            }
        ],
        data: {
            url: '/',
            timestamp: new Date().getTime()
        }
    };

    // Parse the push data if available
    if (event.data) {
        try {
            const pushData = event.data.text();
            console.log('📝 Push data:', pushData);
            
            // Update notification with actual data
            notificationData.body = pushData;
            
            // Customize based on message type, but keep same HFA sound
            if (pushData.includes('💬')) {
                notificationData.title = 'New Thread Message';
                notificationData.tag = 'thread-message';
                // ✅ Same HFA sound for thread messages
                notificationData.sound = '/sounds/hfasound.mp3';
            } else if (pushData.includes('🎽')) {
                notificationData.title = 'Gear Update';
                notificationData.tag = 'gear-update';
                // ✅ Same HFA sound for gear updates
                notificationData.sound = '/sounds/hfasound.mp3';
            } else {
                notificationData.title = 'HFA Notification';
                notificationData.tag = 'general';
                // ✅ Same HFA sound for general notifications
                notificationData.sound = '/sounds/hfasound.mp3';
            }
            
        } catch (e) {
            console.error('❌ Error parsing push data:', e);
        }
    }

    // Show the notification with custom HFA sound
    event.waitUntil(
        self.registration.showNotification(notificationData.title, notificationData)
            .then(() => {
                console.log('✅ Notification displayed with custom HFA sound');
            })
            .catch(err => {
                console.error('❌ Error showing notification:', err);
            })
    );
});

// Handle notification click events
self.addEventListener('notificationclick', function(event) {
    console.log('👆 Notification clicked:', event);
    
    event.notification.close();
    
    if (event.action === 'open' || !event.action) {
        // Open the app
        event.waitUntil(
            clients.matchAll({
                type: 'window',
                includeUncontrolled: true
            }).then(function(clientList) {
                // If app is already open, focus it
                for (let i = 0; i < clientList.length; i++) {
                    let client = clientList[i];
                    if (client.url.includes(self.location.origin)) {
                        return client.focus();
                    }
                }
                
                // Otherwise open new window
                return clients.openWindow('/');
            })
        );
    } else if (event.action === 'dismiss') {
        // Just close the notification (already handled above)
        console.log('🗑️ Notification dismissed');
    }
});

// Handle notification close events
self.addEventListener('notificationclose', function(event) {
    console.log('❌ Notification closed:', event);
});

// Handle background sync (optional)
self.addEventListener('sync', function(event) {
    console.log('🔄 Background sync:', event);
    if (event.tag === 'background-sync') {
        event.waitUntil(doBackgroundSync());
    }
});

function doBackgroundSync() {
    // Sync data when device comes back online
    return Promise.resolve();
}

// Install event
self.addEventListener('install', function(event) {
    console.log('📦 Service Worker installing');
    self.skipWaiting();
});

// Activate event
self.addEventListener('activate', function(event) {
    console.log('✅ Service Worker activated');
    event.waitUntil(self.clients.claim());
});