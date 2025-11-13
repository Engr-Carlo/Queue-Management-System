// API Configuration - Vercel Deployment
const API_BASE_URL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost:3000'  // Local development
    : '';  // Use relative path for Vercel deployment (same domain)

console.log('Using API Base URL:', API_BASE_URL);
