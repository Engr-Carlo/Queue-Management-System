// API Configuration - Auto-detect environment
function getApiBaseUrl() {
    // Check if we're on localhost or local network
    const hostname = window.location.hostname;
    
    if (hostname === 'localhost' || hostname === '127.0.0.1') {
        return 'http://localhost:5000';
    } else if (hostname.startsWith('192.168.') || hostname.startsWith('10.') || hostname.startsWith('172.')) {
        return 'http://192.168.118.164:5000';
    } else {
        // For production - Replace this with your actual Railway URL
        return 'https://YOUR_RAILWAY_URL_HERE'; // Replace with your Railway URL
    }
}

// Use this in your fetch calls
const API_BASE_URL = getApiBaseUrl();

console.log('Using API Base URL:', API_BASE_URL);
